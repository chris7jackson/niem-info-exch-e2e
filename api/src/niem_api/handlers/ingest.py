#!/usr/bin/env python3

import json
import logging
import yaml
from typing import List, Dict, Any

from fastapi import HTTPException, UploadFile
from minio import Minio
from ..services.cmf_tool import is_cmf_available
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


def _load_mapping_from_s3(s3: Minio, schema_id: str) -> Dict[str, Any]:
    """Load mapping YAML from S3.

    Args:
        s3: MinIO client
        schema_id: Schema ID

    Returns:
        Mapping dictionary
    """
    try:
        mapping_response = s3.get_object("niem-schemas", f"{schema_id}/mapping.yaml")
        mapping_content = mapping_response.read().decode('utf-8')
        mapping = yaml.safe_load(mapping_content)
        mapping_response.close()
        mapping_response.release_conn()
        return mapping
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load mapping.yaml: {str(e)}")


def _download_schema_files(s3: Minio, schema_id: str) -> str:
    """Download schema XSD files from S3 to temporary directory.

    Args:
        s3: MinIO client
        schema_id: Schema ID

    Returns:
        Path to temporary directory containing schema files
    """
    import tempfile
    from pathlib import Path

    temp_dir = tempfile.mkdtemp(prefix="schema_validation_")
    logger.info(f"Downloading schema files for {schema_id} to {temp_dir}")

    try:
        # List all objects in the schema folder
        objects = s3.list_objects("niem-schemas", prefix=f"{schema_id}/source/", recursive=True)

        xsd_count = 0
        for obj in objects:
            if obj.object_name.endswith('.xsd'):
                # Download the file
                response = s3.get_object("niem-schemas", obj.object_name)
                content = response.read()
                response.close()
                response.release_conn()

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
        raise HTTPException(status_code=500, detail=f"Failed to download schema files: {str(e)}")

def _validate_xml_content(xml_content: str, schema_dir: str, filename: str) -> None:
    """Validate XML content against XSD schemas using CMF tool.

    Args:
        xml_content: XML content to validate
        schema_dir: Directory containing XSD schema files
        filename: File being validated (for logging purposes)

    Raises:
        HTTPException: If validation fails (with structured error details in response)
    """
    import tempfile
    from pathlib import Path
    from ..clients.cmf_client import run_cmf_command, parse_cmf_validation_output, CMFError
    from ..models.models import ValidationError, ValidationResult

    logger.info(f"Validating XML file {filename} against XSD schemas")

    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            # Write XML content to temporary file
            xml_file = Path(temp_dir) / filename
            with open(xml_file, 'w', encoding='utf-8') as f:
                f.write(xml_content)

            # Find all XSD files in schema directory
            schema_path = Path(schema_dir)
            xsd_files = list(schema_path.rglob("*.xsd"))

            if not xsd_files:
                logger.warning(f"No XSD files found in {schema_dir}, skipping validation")
                return

            logger.info(f"Found {len(xsd_files)} XSD schema files for validation")

            # Build xval command with all schema files
            cmd = ["xval"]
            for xsd_file in xsd_files:
                cmd.extend(["--schema", str(xsd_file)])
            cmd.extend(["--file", str(xml_file)])  # Fixed: convert PosixPath to str

            # Run XSD validation command
            result = run_cmf_command(cmd, working_dir=temp_dir)

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
        )
    except Exception as e:
        logger.error(f"Unexpected error during XML validation: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "message": f"Validation error: {str(e)}",
                "validation_result": None
            }
        )


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


async def _store_processed_files(s3: Minio, content: bytes, filename: str, cypher_statements: str) -> None:
    """Store XML and Cypher files after successful processing.

    Args:
        s3: MinIO client
        content: File content
        filename: Original filename
        cypher_statements: Generated Cypher statements
    """
    from ..clients.s3_client import upload_file
    import hashlib
    import time

    # Generate unique filename with timestamp
    timestamp = int(time.time())
    file_hash = hashlib.md5(content).hexdigest()[:8]
    base_filename = f"xml/{timestamp}_{file_hash}_{filename}"

    # Store XML file
    try:
        await upload_file(s3, "niem-data", base_filename, content, "application/xml")
        logger.info(f"Stored XML file in niem-data after successful ingestion: {base_filename}")
    except Exception as e:
        logger.warning(f"Graph ingestion succeeded but failed to store XML file {filename} in niem-data: {e}")

    # Store generated Cypher statements alongside the XML in the same folder
    try:
        logger.info(f"About to store Cypher file for {filename}")
        cypher_filename = f"xml/{timestamp}_{file_hash}_{filename}.cypher"
        cypher_content = cypher_statements.encode('utf-8')
        logger.info(f"Cypher content length: {len(cypher_content)} bytes, filename: {cypher_filename}")
        await upload_file(s3, "niem-data", cypher_filename, cypher_content, "text/plain")
        logger.info(f"Stored Cypher file in niem-data: {cypher_filename}")
    except Exception as e:
        logger.error(f"Graph ingestion succeeded but failed to store Cypher file {filename} in niem-data: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")


def _create_success_result(filename: str, statements_executed: int, stats: Dict[str, Any]) -> Dict[str, Any]:
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


def _create_error_result(filename: str, error_msg: str, validation_result: Dict[str, Any] = None) -> Dict[str, Any]:
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
    mapping: Dict[str, Any],
    neo4j_client,
    s3: Minio,
    schema_dir: str
) -> tuple[Dict[str, Any], int]:
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
    files: List[UploadFile],
    s3: Minio,
    schema_id: str = None
) -> Dict[str, Any]:
    """Handle XML file ingestion to Neo4j using import_xml_to_cypher service"""
    logger.info(f"Starting XML ingestion for {len(files)} files using import_xml_to_cypher service")

    schema_dir = None
    try:
        # Step 1: Get schema ID (use provided or get active)
        schema_id = _get_schema_id(s3, schema_id)

        # Step 2: Load mapping specification
        mapping = _load_mapping_from_s3(s3, schema_id)

        # Step 3: Download schema files for validation
        schema_dir = _download_schema_files(s3, schema_id)

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
        raise HTTPException(status_code=500, detail=f"XML ingestion failed: {str(e)}")
    finally:
        # Clean up schema directory
        if schema_dir:
            import shutil
            try:
                shutil.rmtree(schema_dir, ignore_errors=True)
                logger.info(f"Cleaned up schema directory: {schema_dir}")
            except Exception as e:
                logger.warning(f"Failed to clean up schema directory: {e}")


def handle_json_ingest(
    files: List[UploadFile],
    schema_id: str = None
) -> Dict[str, Any]:
    """Handle JSON file ingestion - currently not supported with import_xml_to_cypher service"""
    logger.warning("JSON ingestion is not currently supported with the import_xml_to_cypher service")

    return {
        "schema_id": schema_id,
        "files_processed": 0,
        "total_statements_executed": 0,
        "results": [
            _create_error_result(file.filename, "JSON ingestion not supported - use XML format instead")
            for file in files
        ]
    }

def _generate_cypher_from_xml(xml_content: str, mapping: Dict[str, Any], filename: str) -> tuple[str, Dict[str, Any]]:
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

        logger.info(f"Generated Cypher for {filename}: {stats['nodes_created']} nodes, {stats['containment_edges']} containment relationships, {stats['reference_edges']} reference/association edges")

        return cypher_statements, stats

    except Exception as e:
        logger.error(f"Failed to generate Cypher from XML {filename}: {e}")
        raise


async def handle_get_uploaded_files(s3: Minio) -> Dict[str, Any]:
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
        raise HTTPException(status_code=500, detail=f"Failed to get uploaded files: {str(e)}")