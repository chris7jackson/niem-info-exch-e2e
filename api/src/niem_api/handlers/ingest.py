#!/usr/bin/env python3

import json
import logging
from typing import Any

from fastapi import HTTPException, UploadFile
from minio import Minio

from ..clients.neo4j_client import Neo4jClient

logger = logging.getLogger(__name__)

def _get_schema_id(s3: Minio, schema_id: str | None) -> str:
    """Get schema ID, using provided or active schema.

    Args:
        s3: MinIO client
        schema_id: Optional schema ID

    Returns:
        Schema ID to use
    """
    if schema_id:
        return schema_id

    from .schema import get_active_schema_id
    active_schema_id = get_active_schema_id(s3)
    if not active_schema_id:
        raise HTTPException(status_code=400, detail="No active schema found and no schema_id provided")
    return active_schema_id


def _load_mapping_from_s3(s3: Minio, schema_id: str) -> dict[str, Any]:
    """Load mapping YAML from S3.

    Args:
        s3: MinIO client
        schema_id: Schema ID

    Returns:
        Mapping dictionary
    """
    from ..clients.s3_client import get_yaml_content
    try:
        return get_yaml_content(s3, "niem-schemas", f"{schema_id}/mapping.yaml")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load mapping.yaml: {str(e)}") from e


async def _download_schema_files(s3: Minio, schema_id: str) -> str:
    """Download schema XSD files from S3 to temporary directory.

    Args:
        s3: MinIO client
        schema_id: Schema ID

    Returns:
        Path to temporary directory containing schema files
    """
    import tempfile
    from pathlib import Path

    from ..clients.s3_client import download_file

    temp_dir = tempfile.mkdtemp(prefix="schema_validation_")
    logger.info(f"Downloading schema files for {schema_id} to {temp_dir}")

    try:
        # List all objects in the schema folder
        objects = s3.list_objects("niem-schemas", prefix=f"{schema_id}/source/", recursive=True)

        xsd_count = 0
        for obj in objects:
            if obj.object_name.endswith('.xsd'):
                # Download the file using helper
                content = await download_file(s3, "niem-schemas", obj.object_name)

                # Create subdirectories if needed
                relative_path = obj.object_name.replace(f"{schema_id}/source/", "")
                target_path = Path(temp_dir) / relative_path
                target_path.parent.mkdir(parents=True, exist_ok=True)

                # Write file
                with open(target_path, 'wb') as f:
                    f.write(content)

                xsd_count += 1
                logger.debug(f"Downloaded schema file: {relative_path}")

        logger.info(f"Downloaded {xsd_count} XSD schema files")
        return temp_dir

    except Exception as e:
        logger.error(f"Failed to download schema files: {e}")
        # Clean up on error
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise HTTPException(status_code=500, detail=f"Failed to download schema files: {str(e)}") from e

def _validate_xml_content(xml_content: str, schema_dir: str, filename: str) -> None:
    """Validate XML content against XSD schemas using CMF tool.

    Args:
        xml_content: XML content to validate
        schema_dir: Directory containing XSD schema files
        filename: File being validated (for logging purposes)

    Raises:
        HTTPException: If validation fails (with structured error details in response)
    """
    from pathlib import Path

    from ..clients.cmf_client import CMFError, parse_cmf_validation_output, run_cmf_command
    from ..models.models import ValidationError, ValidationResult

    logger.info(f"Validating XML file {filename} against XSD schemas")

    schema_path = Path(schema_dir)

    # Write XML content to file in the schema directory
    xml_file = schema_path / filename
    try:
        with open(xml_file, 'w', encoding='utf-8') as f:
            f.write(xml_content)

        # Find all XSD files in schema directory
        xsd_files = list(schema_path.rglob("*.xsd"))

        if not xsd_files:
            logger.warning(f"No XSD files found in {schema_dir}, skipping validation")
            return

        logger.info(f"Found {len(xsd_files)} XSD schema files for validation")

        # Build xval command with relative paths from schema_dir
        cmd = ["xval"]
        for xsd_file in xsd_files:
            rel_path = xsd_file.relative_to(schema_path)
            cmd.extend(["--schema", str(rel_path)])

        xml_rel_path = xml_file.relative_to(schema_path)
        cmd.extend(["--file", str(xml_rel_path)])

        # Run XSD validation command with schema_dir as working directory
        result = run_cmf_command(cmd, working_dir=schema_dir)

        # Parse validation output into structured errors
        parsed = parse_cmf_validation_output(result["stdout"], result["stderr"], filename)

        # IMPORTANT: xval returns exit code 0 even when validation fails
        # Check both return code AND parsed errors
        validation_failed = result["returncode"] != 0 or parsed["has_errors"]

        if validation_failed:
            # Build structured error response
            error_list = parsed["errors"]
            warning_list = parsed["warnings"]

            # Create ValidationResult for structured response
            validation_result = ValidationResult(
                valid=False,
                errors=[ValidationError(**err) for err in error_list],
                warnings=[ValidationError(**warn) for warn in warning_list],
                summary=f"Validation failed with {len(error_list)} error(s) and {len(warning_list)} warning(s)"
            )

            # Build detailed error message for logging
            error_details = []
            for err in error_list[:5]:  # Show first 5 errors
                loc = f"{err['file']}"
                if err['line']:
                    loc += f":{err['line']}"
                if err['column']:
                    loc += f":{err['column']}"
                error_details.append(f"  - {loc}: {err['message']}")

            error_summary = f"Validation failed for {filename}"
            if error_details:
                error_summary += ":\n" + "\n".join(error_details)
                if len(error_list) > 5:
                    error_summary += f"\n  ... and {len(error_list) - 5} more error(s)"

            logger.error(error_summary)

            # Return structured validation result in HTTPException detail
            raise HTTPException(
                status_code=400,
                detail={
                    "message": f"Validation error: {filename}",
                    "validation_result": validation_result.model_dump()
                }
            )

        logger.info(f"Successfully validated {filename} against XSD schemas")

    except HTTPException:
        # Re-raise HTTPException from validation failure (already has detail message)
        raise
    except CMFError as e:
        logger.error(f"CMF tool error during validation: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "message": f"CMF tool error: {str(e)}",
                "validation_result": None
            }
        ) from e
    except Exception as e:
        logger.error(f"Unexpected error during XML validation: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "message": f"Validation error: {str(e)}",
                "validation_result": None
            }
        ) from e
    finally:
        # Clean up XML file from schema directory
        if xml_file.exists():
            xml_file.unlink()
            logger.debug(f"Cleaned up XML file: {filename}")


def _download_json_schema_from_s3(s3: Minio, schema_id: str) -> dict[str, Any]:
    """Download JSON Schema from S3.

    Args:
        s3: MinIO client
        schema_id: Schema ID

    Returns:
        JSON Schema dictionary

    Raises:
        HTTPException: If JSON Schema not found
    """
    from ..clients.s3_client import get_json_content
    from .schema import get_schema_metadata

    try:
        # Get schema metadata to determine the JSON schema filename
        metadata = get_schema_metadata(s3, schema_id)
        if not metadata:
            raise HTTPException(
                status_code=404,
                detail=f"Schema metadata not found for schema {schema_id}"
            )

        # Extract base name from primary filename and construct JSON schema filename
        # Handle both forward slashes (Unix/Mac) and backslashes (Windows)
        primary_filename = metadata.get("primary_filename", "")
        filename_only = primary_filename.replace('\\', '/').split('/')[-1]
        base_name = filename_only.rsplit('.xsd', 1)[0] if filename_only.endswith('.xsd') else filename_only
        json_filename = f"{base_name}.json"

        json_schema = get_json_content(s3, "niem-schemas", f"{schema_id}/{json_filename}")
        logger.info(f"Downloaded JSON Schema {json_filename} for schema {schema_id}")
        return json_schema
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=404,
            detail=(
                f"JSON Schema not found for schema {schema_id}. "
                f"Schema may not have been converted to JSON format: {str(e)}"
            )
        ) from e


def _validate_json_content(json_content: str, json_schema: dict[str, Any], filename: str) -> None:
    """Validate NIEM JSON content against JSON Schema.

    NIEM JSON uses JSON-LD features (@context, @id, @type) with NIEM conventions.
    Validation checks JSON syntax, schema compliance, and optionally NIEM JSON structure.

    Args:
        json_content: NIEM JSON content to validate
        json_schema: JSON Schema object (generated from XSD via CMF tool)
        filename: File being validated (for logging purposes)

    Raises:
        HTTPException: If validation fails (with structured error details in response)
    """
    from jsonschema import Draft7Validator

    from ..models.models import ValidationError, ValidationResult

    logger.info(f"Validating NIEM JSON file {filename} against JSON Schema")

    try:
        # Parse JSON content
        data = json.loads(json_content)

        # Check NIEM JSON compliance (uses JSON-LD features)
        if "@context" not in data:
            logger.warning(f"JSON file {filename} missing @context - NIEM JSON should include namespace context")
            # Don't fail, just warn - schema validation will catch structural issues
        else:
            # Check for common NIEM namespaces in context
            context = data["@context"]
            if isinstance(context, dict):
                niem_prefixes = ["nc", "j", "structures"]
                found_niem = any(prefix in context for prefix in niem_prefixes)
                if not found_niem:
                    logger.info(
                        f"JSON file {filename} has @context but no common NIEM "
                        f"namespace prefixes (nc, j, structures)"
                    )

        # Validate against JSON Schema - collect ALL errors instead of stopping at first
        validator = Draft7Validator(json_schema)
        validation_errors = list(validator.iter_errors(data))

        if validation_errors:
            # Build list of all validation errors
            errors = []
            for err in validation_errors:
                json_path = ".".join(str(p) for p in err.path) if err.path else "root"
                error = ValidationError(
                    file=filename,
                    line=None,  # JSON Schema validation doesn't provide line numbers
                    column=None,
                    message=err.message,
                    severity="error",
                    rule=err.validator,  # e.g., "required", "type", "pattern"
                    context=json_path
                )
                errors.append(error)

            validation_result = ValidationResult(
                valid=False,
                errors=errors,
                warnings=[],
                summary=f"Validation failed with {len(errors)} error(s) and 0 warning(s)"
            )

            logger.error(f"JSON Schema validation failed for {filename} with {len(errors)} error(s)")
            for err in errors[:10]:  # Log first 10 errors
                logger.error(f"  - {err.context}: {err.message}")
            if len(errors) > 10:
                logger.error(f"  ... and {len(errors) - 10} more error(s)")

            raise HTTPException(
                status_code=400,
                detail={
                    "message": f"Validation error: {filename}",
                    "validation_result": validation_result.model_dump()
                }
            )

        logger.info(f"Successfully validated {filename} against JSON Schema")

    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON syntax in {filename}: {e}")
        error = ValidationError(
            file=filename,
            line=e.lineno if hasattr(e, 'lineno') else None,
            column=e.colno if hasattr(e, 'colno') else None,
            message=f"Invalid JSON syntax: {e.msg}",
            severity="error",
            rule="json_syntax",
            context=None
        )
        validation_result = ValidationResult(
            valid=False,
            errors=[error],
            warnings=[],
            summary=f"JSON syntax error in {filename}"
        )
        raise HTTPException(
            status_code=400,
            detail={
                "message": f"Invalid JSON syntax: {filename}",
                "validation_result": validation_result.model_dump()
            }
        ) from e

    except HTTPException:
        # Re-raise HTTPException from validation (already has proper detail)
        raise
    except Exception as e:
        logger.error(f"Unexpected error during JSON validation: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "message": f"Validation error: {str(e)}",
                "validation_result": None
            }
        ) from e


def _clean_cypher_statement(statement: str) -> str:
    """Clean Cypher statement by removing comments.

    Args:
        statement: Raw Cypher statement

    Returns:
        Cleaned statement
    """
    clean_lines = []
    for line in statement.split('\n'):
        line = line.strip()
        if line and not line.startswith('//'):
            clean_lines.append(line)
    return '\n'.join(clean_lines)


def _execute_cypher_statements(cypher_statements: str, neo4j_client) -> int:
    """Execute Cypher statements in Neo4j.

    Args:
        cypher_statements: Cypher statements to execute
        neo4j_client: Neo4j client

    Returns:
        Number of statements executed
    """
    statements_executed = 0
    statements = [stmt.strip() for stmt in cypher_statements.split(';') if stmt.strip()]

    for statement in statements:
        if statement:
            clean_statement = _clean_cypher_statement(statement)
            if clean_statement:
                neo4j_client.query(clean_statement)
                statements_executed += 1

    return statements_executed


async def _store_processed_files(
    s3: Minio, content: bytes, filename: str, cypher_statements: str, file_type: str = "xml"
) -> None:
    """Store data files and Cypher files after successful processing.

    Args:
        s3: MinIO client
        content: File content
        filename: Original filename
        cypher_statements: Generated Cypher statements
        file_type: Type of file ("xml" or "json")
    """
    import hashlib
    import time

    from ..clients.s3_client import upload_file

    # Generate unique filename with timestamp
    timestamp = int(time.time())
    file_hash = hashlib.md5(content).hexdigest()[:8]
    base_filename = f"{file_type}/{timestamp}_{file_hash}_{filename}"

    # Determine content type
    content_type = "application/json" if file_type == "json" else "application/xml"

    # Store data file
    try:
        await upload_file(s3, "niem-data", base_filename, content, content_type)
        logger.info(f"Stored {file_type.upper()} file in niem-data after successful ingestion: {base_filename}")
    except Exception as e:
        logger.warning(
            f"Graph ingestion succeeded but failed to store {file_type.upper()} "
            f"file {filename} in niem-data: {e}"
        )

    # Store generated Cypher statements alongside the data file in the same folder
    try:
        logger.info(f"About to store Cypher file for {filename}")
        cypher_filename = f"{file_type}/{timestamp}_{file_hash}_{filename}.cypher"
        cypher_content = cypher_statements.encode('utf-8')
        logger.info(f"Cypher content length: {len(cypher_content)} bytes, filename: {cypher_filename}")
        await upload_file(s3, "niem-data", cypher_filename, cypher_content, "text/plain")
        logger.info(f"Stored Cypher file in niem-data: {cypher_filename}")
    except Exception as e:
        logger.error(f"Graph ingestion succeeded but failed to store Cypher file {filename} in niem-data: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")


def _create_success_result(filename: str, statements_executed: int, stats: dict[str, Any]) -> dict[str, Any]:
    """Create success result dictionary.

    Args:
        filename: Processed filename
        statements_executed: Number of statements executed
        stats: Processing statistics

    Returns:
        Success result dictionary
    """
    return {
        "filename": filename,
        "status": "success",
        "statements_executed": statements_executed,
        "nodes_created": stats.get("nodes_count", 0),
        "relationships_created": stats.get("edges_count", 0) + stats.get("contains_count", 0)
    }


def _create_error_result(filename: str, error_msg: str, validation_result: dict[str, Any] = None) -> dict[str, Any]:
    """Create error result dictionary.

    Args:
        filename: Failed filename
        error_msg: Error message
        validation_result: Optional structured validation result

    Returns:
        Error result dictionary
    """
    result = {
        "filename": filename,
        "status": "failed",
        "error": error_msg
    }
    if validation_result:
        result["validation_details"] = validation_result
    return result


async def _process_single_file(
    file: UploadFile,
    mapping: dict[str, Any],
    neo4j_client,
    s3: Minio,
    schema_dir: str
) -> tuple[dict[str, Any], int]:
    """Process a single XML file.

    Args:
        file: Uploaded file
        mapping: Schema mapping
        neo4j_client: Neo4j client
        s3: MinIO client
        schema_dir: Directory containing XSD schema files

    Returns:
        Tuple of (result_dict, statements_executed)
    """
    try:
        content = await file.read()
        xml_content = content.decode('utf-8')

        # Validate XML against XSD schemas
        _validate_xml_content(xml_content, schema_dir, file.filename)

        # Use import_xml_to_cypher service to generate Cypher
        cypher_statements, stats = _generate_cypher_from_xml(
            xml_content, mapping, file.filename
        )

        if not cypher_statements:
            return _create_error_result(file.filename, "No Cypher statements generated from XML"), 0

        # Execute Cypher statements in Neo4j
        try:
            statements_executed = _execute_cypher_statements(cypher_statements, neo4j_client)

            # Store XML file in MinIO after successful ingestion
            await _store_processed_files(s3, content, file.filename, cypher_statements)

            result = _create_success_result(file.filename, statements_executed, stats)
            logger.info(f"Successfully ingested {file.filename}: {statements_executed} Cypher statements executed")
            return result, statements_executed

        except Exception as e:
            logger.error(f"Failed to execute Cypher for {file.filename}: {e}")
            return _create_error_result(file.filename, f"Cypher execution failed: {str(e)}"), 0

    except HTTPException as e:
        # HTTPException from validation - extract detail message and validation result
        if hasattr(e, 'detail') and isinstance(e.detail, dict):
            error_msg = e.detail.get('message', str(e.detail))
            validation_result = e.detail.get('validation_result')

            # If no validation_result but message indicates validation failure, provide helpful default
            if not validation_result and 'validation' in error_msg.lower():
                error_msg = f"{error_msg}. CMF validation failed - check that the XML conforms to the active schema."
        else:
            error_msg = e.detail if hasattr(e, 'detail') else str(e)
            validation_result = None

            # Provide helpful default message for validation errors
            if 'validation' in error_msg.lower() and not validation_result:
                error_msg = f"{error_msg}. Check that the XML file conforms to the active schema."

        logger.error(f"Failed to process file {file.filename}: {error_msg}")
        return _create_error_result(file.filename, error_msg, validation_result), 0
    except Exception as e:
        logger.error(f"Failed to process file {file.filename}: {e}")
        error_msg = f"{str(e)}. Unexpected error during processing."
        return _create_error_result(file.filename, error_msg), 0


async def handle_xml_ingest(
    files: list[UploadFile],
    s3: Minio,
    schema_id: str = None
) -> dict[str, Any]:
    """Handle XML file ingestion to Neo4j using import_xml_to_cypher service"""
    logger.info(f"Starting XML ingestion for {len(files)} files using import_xml_to_cypher service")

    schema_dir = None
    try:
        # Step 1: Get schema ID (use provided or get active)
        schema_id = _get_schema_id(s3, schema_id)

        # Step 2: Load mapping specification
        mapping = _load_mapping_from_s3(s3, schema_id)

        # Step 3: Download schema files for validation
        schema_dir = await _download_schema_files(s3, schema_id)

        # Step 4: Process files
        results = []
        total_statements_executed = 0
        total_nodes = 0
        total_relationships = 0

        # Initialize Neo4j client
        neo4j_client = Neo4jClient()

        try:
            for file in files:
                result, statements_executed = await _process_single_file(
                    file, mapping, neo4j_client, s3, schema_dir
                )
                results.append(result)
                total_statements_executed += statements_executed
                total_nodes += result.get("nodes_created", 0)
                total_relationships += result.get("relationships_created", 0)

        finally:
            neo4j_client.driver.close()

        return {
            "schema_id": schema_id,
            "files_processed": len(files),
            "total_nodes_created": total_nodes,
            "total_relationships_created": total_relationships,
            "total_statements_executed": total_statements_executed,
            "results": results
        }

    except Exception as e:
        import traceback
        logger.error(f"XML ingestion failed: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        if isinstance(e, HTTPException):
            raise
        raise HTTPException(status_code=500, detail=f"XML ingestion failed: {str(e)}") from e
    finally:
        # Clean up schema directory
        if schema_dir:
            import shutil
            try:
                shutil.rmtree(schema_dir, ignore_errors=True)
                logger.info(f"Cleaned up schema directory: {schema_dir}")
            except Exception as e:
                logger.warning(f"Failed to clean up schema directory: {e}")


async def _process_single_json_file(
    file: UploadFile,
    mapping: dict[str, Any],
    json_schema: dict[str, Any],
    neo4j_client,
    s3: Minio
) -> tuple[dict[str, Any], int]:
    """Process a single NIEM JSON file.

    Args:
        file: Uploaded file
        mapping: Schema mapping
        json_schema: JSON Schema for validation
        neo4j_client: Neo4j client
        s3: MinIO client

    Returns:
        Tuple of (result_dict, statements_executed)
    """
    try:
        content = await file.read()
        json_content = content.decode('utf-8')

        # Validate NIEM JSON against JSON Schema
        _validate_json_content(json_content, json_schema, file.filename)

        # Generate Cypher from NIEM JSON
        cypher_statements, stats = _generate_cypher_from_json(
            json_content, mapping, file.filename
        )

        if not cypher_statements:
            return _create_error_result(file.filename, "No Cypher statements generated from NIEM JSON"), 0

        # Execute Cypher statements in Neo4j
        try:
            statements_executed = _execute_cypher_statements(cypher_statements, neo4j_client)

            # Store NIEM JSON file in MinIO after successful ingestion
            await _store_processed_files(s3, content, file.filename, cypher_statements, file_type="json")

            result = _create_success_result(file.filename, statements_executed, stats)
            logger.info(f"Successfully ingested {file.filename}: {statements_executed} Cypher statements executed")
            return result, statements_executed

        except Exception as e:
            logger.error(f"Failed to execute Cypher for {file.filename}: {e}")
            return _create_error_result(file.filename, f"Cypher execution failed: {str(e)}"), 0

    except HTTPException as e:
        # HTTPException from validation - extract detail message and validation result
        if hasattr(e, 'detail') and isinstance(e.detail, dict):
            error_msg = e.detail.get('message', str(e.detail))
            validation_result = e.detail.get('validation_result')

            # If no validation_result but message indicates validation failure, provide helpful default
            if not validation_result and 'validation' in error_msg.lower():
                error_msg = (
                    f"{error_msg}. NIEM JSON validation failed - check that the JSON "
                    f"conforms to the active schema."
                )
        else:
            error_msg = e.detail if hasattr(e, 'detail') else str(e)
            validation_result = None

            # Provide helpful default message for validation errors
            if 'validation' in error_msg.lower() and not validation_result:
                error_msg = f"{error_msg}. Check that the NIEM JSON file conforms to the active schema."

        logger.error(f"Failed to process file {file.filename}: {error_msg}")
        return _create_error_result(file.filename, error_msg, validation_result), 0
    except Exception as e:
        logger.error(f"Failed to process file {file.filename}: {e}")
        error_msg = f"{str(e)}. Unexpected error during processing."
        return _create_error_result(file.filename, error_msg), 0


async def handle_json_ingest(
    files: list[UploadFile],
    s3: Minio,
    schema_id: str = None
) -> dict[str, Any]:
    """Handle NIEM JSON file ingestion to Neo4j using json_to_graph service.

    NIEM JSON uses JSON-LD features (@context, @id, @type) with NIEM-specific conventions
    for property names and references. Files are validated against JSON Schema (generated
    from XSD by CMF tool) and converted to Cypher using the same mapping as XML.
    """
    logger.info(f"Starting NIEM JSON ingestion for {len(files)} files using json_to_graph service")

    try:
        # Step 1: Get schema ID (use provided or get active)
        schema_id = _get_schema_id(s3, schema_id)

        # Step 2: Validate JSON Schema exists for this schema
        from .schema import get_schema_metadata
        metadata = get_schema_metadata(s3, schema_id)
        if not metadata or not metadata.get("json_schema_filename"):
            raise HTTPException(
                status_code=400,
                detail=(
                    "JSON schema is not available for this schema. "
                    "The JSON schema was not successfully converted during XSD upload, "
                    "likely due to CMF tool conversion issues. "
                    "Please re-upload the XSD schema or use XML ingestion instead."
                )
            )

        # Step 3: Load mapping specification
        mapping = _load_mapping_from_s3(s3, schema_id)

        # Step 4: Download JSON Schema for validation
        json_schema = _download_json_schema_from_s3(s3, schema_id)

        # Step 5: Process files
        results = []
        total_statements_executed = 0
        total_nodes = 0
        total_relationships = 0

        # Initialize Neo4j client
        neo4j_client = Neo4jClient()

        try:
            for file in files:
                result, statements_executed = await _process_single_json_file(
                    file, mapping, json_schema, neo4j_client, s3
                )
                results.append(result)
                total_statements_executed += statements_executed
                total_nodes += result.get("nodes_created", 0)
                total_relationships += result.get("relationships_created", 0)

        finally:
            neo4j_client.driver.close()

        return {
            "schema_id": schema_id,
            "files_processed": len(files),
            "total_nodes_created": total_nodes,
            "total_relationships_created": total_relationships,
            "total_statements_executed": total_statements_executed,
            "results": results
        }

    except Exception as e:
        import traceback
        logger.error(f"NIEM JSON ingestion failed: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        if isinstance(e, HTTPException):
            raise
        raise HTTPException(status_code=500, detail=f"NIEM JSON ingestion failed: {str(e)}") from e

def _generate_cypher_from_xml(xml_content: str, mapping: dict[str, Any], filename: str) -> tuple[str, dict[str, Any]]:
    """
    Generate Cypher statements from XML content using the import_xml_to_cypher service.

    Args:
        xml_content: Raw XML content as string
        mapping: Mapping dictionary (YAML format)
        filename: Source filename for provenance

    Returns:
        Tuple of (cypher_statements, stats)
    """
    try:
        from ..services.domain.xml_to_graph import generate_for_xml_content

        # Generate Cypher statements using in-memory processing (no temporary files needed)
        cypher_statements, nodes, contains, edges = generate_for_xml_content(xml_content, mapping, filename)

        # Create stats dictionary from the returned data
        stats = {
            "nodes_created": len(nodes),
            "nodes_count": len(nodes),
            "containment_edges": len(contains),
            "contains_count": len(contains),
            "reference_edges": len(edges),
            "edges_count": len(edges)
        }

        logger.info(
            f"Generated Cypher for {filename}: {stats['nodes_created']} nodes, "
            f"{stats['containment_edges']} containment relationships, "
            f"{stats['reference_edges']} reference/association edges"
        )

        return cypher_statements, stats

    except Exception as e:
        logger.error(f"Failed to generate Cypher from XML {filename}: {e}")
        raise


def _generate_cypher_from_json(json_content: str, mapping: dict[str, Any], filename: str) -> tuple[str, dict[str, Any]]:
    """
    Generate Cypher statements from NIEM JSON content using the json_to_graph service.

    NIEM JSON uses JSON-LD features with NIEM conventions. This applies the same
    mapping rules as XML to ensure consistent graph structures.

    Args:
        json_content: Raw NIEM JSON content as string
        mapping: Mapping dictionary (YAML format, same as XML)
        filename: Source filename for provenance

    Returns:
        Tuple of (cypher_statements, stats)
    """
    try:
        from ..services.domain.json_to_graph import generate_for_json_content

        # Generate Cypher statements from NIEM JSON
        cypher_statements, nodes, contains, edges = generate_for_json_content(json_content, mapping, filename)

        # Create stats dictionary from the returned data
        stats = {
            "nodes_created": len(nodes),
            "nodes_count": len(nodes),
            "containment_edges": len(contains),
            "contains_count": len(contains),
            "reference_edges": len(edges),
            "edges_count": len(edges)
        }

        logger.info(
            f"Generated Cypher for {filename}: {stats['nodes_created']} nodes, "
            f"{stats['containment_edges']} containment relationships, "
            f"{stats['reference_edges']} reference/association edges"
        )

        return cypher_statements, stats

    except Exception as e:
        logger.error(f"Failed to generate Cypher from NIEM JSON {filename}: {e}")
        raise


async def handle_get_uploaded_files(s3: Minio) -> dict[str, Any]:
    """Get list of uploaded data files

    Args:
        s3: MinIO client

    Returns:
        Dictionary with file list and metadata

    Raises:
        HTTPException: If retrieval fails
    """
    try:
        from ..clients.s3_client import list_files

        files = await list_files(s3, "niem-data")

        # Parse filenames to extract original names and metadata
        processed_files = []
        for file_info in files:
            name = file_info["name"]
            # Files are stored as timestamp_hash_originalname.ext
            parts = name.split("_", 2)
            if len(parts) >= 3:
                original_name = parts[2]  # Get the original filename
                processed_files.append({
                    "original_name": original_name,
                    "stored_name": name,
                    "size": file_info["size"],
                    "last_modified": file_info["last_modified"],
                    "content_type": file_info["content_type"]
                })
            else:
                # Fallback for files that don't follow the naming convention
                processed_files.append({
                    "original_name": name,
                    "stored_name": name,
                    "size": file_info["size"],
                    "last_modified": file_info["last_modified"],
                    "content_type": file_info["content_type"]
                })

        # Sort by last modified (newest first)
        processed_files.sort(key=lambda x: x["last_modified"] or "", reverse=True)

        logger.info(f"Retrieved {len(processed_files)} uploaded files")

        return {
            "status": "success",
            "files": processed_files,
            "total_files": len(processed_files)
        }

    except Exception as e:
        logger.error(f"Failed to get uploaded files: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get uploaded files: {str(e)}") from e
