#!/usr/bin/env python3

import hashlib
import json
import logging
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml
from fastapi import HTTPException, UploadFile
from minio import Minio
from minio.error import S3Error

import xml.etree.ElementTree as ET

from ..clients.s3_client import upload_file
from ..clients.scheval_client import is_scheval_available
from ..models.models import SchevalIssue, SchevalReport, SchemaResponse
from ..services.cmf_tool import (
    convert_cmf_to_jsonschema,
    convert_xsd_to_cmf,
    is_cmf_available,
)
from ..services.domain.schema.scheval_validator import SchevalValidator

logger = logging.getLogger(__name__)


def _detect_niem_schema_type(xsd_content: str) -> str:
    """
    Detect NIEM schema type from ct:conformanceTargets attribute.

    Args:
        xsd_content: The XSD file content as string

    Returns:
        Schema type: 'ref', 'ext', 'sub', or 'sub' (default if unknown)
    """
    try:
        # Parse the XSD to find conformanceTargets attribute
        root = ET.fromstring(xsd_content.encode('utf-8'))

        # Define namespace for conformance targets
        ct_ns = (
            "https://docs.oasis-open.org/niemopen/ns/specification/"
            "conformanceTargets/6.0/"
        )

        # Get conformanceTargets attribute
        conformance_attr = root.get(f"{{{ct_ns}}}conformanceTargets")

        if not conformance_attr:
            logger.warning(
                "No ct:conformanceTargets attribute found in schema, "
                "defaulting to subset"
            )
            return "sub"

        # Parse space-separated conformance target URIs
        targets = conformance_attr.split()

        # Check for schema type fragment identifiers (priority: ref > ext > sub)
        for target in targets:
            if "#ReferenceSchemaDocument" in target:
                logger.info("Detected ReferenceSchemaDocument conformance target")
                return "ref"

        for target in targets:
            if "#ExtensionSchemaDocument" in target:
                logger.info("Detected ExtensionSchemaDocument conformance target")
                return "ext"

        for target in targets:
            if "#SubsetSchemaDocument" in target:
                logger.info("Detected SubsetSchemaDocument conformance target")
                return "sub"

        # Found conformanceTargets but no recognized schema type
        logger.warning(
            f"Unknown conformance targets: {conformance_attr}, "
            f"defaulting to subset"
        )
        return "sub"

    except ET.ParseError as e:
        logger.error(f"Failed to parse XSD for schema type detection: {e}")
        return "sub"
    except Exception as e:
        logger.error(f"Unexpected error during schema type detection: {e}")
        return "sub"


def _extract_schema_imports(xsd_content: str) -> list[dict[str, Any]]:
    """Extract import declarations from XSD content.

    Args:
        xsd_content: XSD content as string

    Returns:
        List of import dictionaries with namespace and schema_location
    """
    import xml.etree.ElementTree as ET

    imports = []
    try:
        root = ET.fromstring(xsd_content)
        for elem in root.iter():
            if elem.tag.endswith('}import') or elem.tag == 'import':
                namespace = elem.get('namespace', '')
                schema_location = elem.get('schemaLocation', '')
                if schema_location:
                    imports.append({
                        'namespace': namespace,
                        'schema_location': schema_location
                    })
    except Exception as e:
        logger.warning(f"Failed to parse schema imports: {e}")

    return imports


def _read_local_schemas(source_dir: Path) -> dict[str, str]:
    """Read all local XSD schemas from source directory.

    Args:
        source_dir: Directory containing schema files

    Returns:
        Dictionary mapping filename to content
    """
    local_schemas = {}
    if source_dir and source_dir.exists():
        for xsd_file in source_dir.glob("*.xsd"):
            try:
                with open(xsd_file, encoding='utf-8') as f:
                    local_schemas[xsd_file.name] = f.read()
            except Exception as e:
                logger.warning(f"Failed to read local schema {xsd_file}: {e}")
    return local_schemas


def _setup_resolved_directory(source_dir: Path, schema_filename: str, xsd_content: str) -> Path:
    """Create and populate resolved directory with local schemas.

    Args:
        source_dir: Source directory containing schemas
        schema_filename: Primary schema filename
        xsd_content: Primary schema content

    Returns:
        Path to resolved directory
    """
    import shutil
    import tempfile

    resolved_dir = Path(tempfile.mkdtemp(prefix="schema_with_niem_"))

    if source_dir and source_dir.exists():
        # Copy all XSD files, preserving directory structure
        for schema_file in source_dir.rglob("*.xsd"):
            rel_path = schema_file.relative_to(source_dir)
            target_path = resolved_dir / rel_path

            target_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(schema_file, target_path)
            logger.info(f"Added local schema: {rel_path}")

            if str(rel_path).startswith('niem/'):
                logger.debug(f"Added NIEM schema to correct path: {rel_path}")
            else:
                logger.debug(f"Added main/local schema: {rel_path}")
    else:
        # Single schema case
        main_schema_path = resolved_dir / schema_filename
        with open(main_schema_path, 'w', encoding='utf-8') as f:
            f.write(xsd_content)
        logger.info(f"Added main schema: {schema_filename}")

    return resolved_dir






def _create_error_response(error_type: str, error_msg: str, imports: list[dict[str, Any]]) -> dict[str, Any]:
    """Create standardized error response.

    Args:
        error_type: Type of error (for logging)
        error_msg: Error message
        imports: List of imports (for context)

    Returns:
        Error response dictionary
    """
    return {
        "can_convert": False,
        "summary": f"{error_type}: {error_msg}",
        "total_imports": len(imports),
        "satisfied_imports": [],
        "missing_imports": imports,
        "blocking_issues": [f"{error_type}: {error_msg}"],
        "resolved_schemas_count": 0
    }


def _validate_schema_dependencies(source_dir: Path, schema_filename: str, xsd_content: str) -> dict[str, Any]:
    """Validate schema dependencies within uploaded files only.

    Args:
        source_dir: Directory containing the schema files
        schema_filename: Name of the primary schema file
        xsd_content: Primary XSD content as string

    Returns:
        Dictionary with validation results and temp directory path
    """
    logger.info("Validating schema dependencies within uploaded files")

    try:
        # Step 1: Setup resolved directory with all uploaded files
        resolved_dir = _setup_resolved_directory(source_dir, schema_filename, xsd_content)

        # Step 2: Read all uploaded schemas using relative paths as keys
        uploaded_schemas = {}
        if source_dir and source_dir.exists():
            for xsd_file in source_dir.rglob("*.xsd"):
                try:
                    # Use relative path as key to match import schemaLocation references
                    rel_path = str(xsd_file.relative_to(source_dir))
                    with open(xsd_file, encoding='utf-8') as f:
                        uploaded_schemas[rel_path] = f.read()
                    logger.info(f"Read schema with key: {rel_path}")
                except Exception as e:
                    logger.warning(f"Failed to read {xsd_file}: {e}")
        else:
            uploaded_schemas[schema_filename] = xsd_content

        # Step 3: Validate dependencies using the new resolver
        from ..services.domain.schema import validate_schema_dependencies
        validation_result = validate_schema_dependencies(uploaded_schemas)

        # Step 4: Build ImportValidationReport from file_details
        from ..models.models import FileImportInfo, ImportInfo, ImportValidationReport, NamespaceUsage

        file_import_infos = []
        total_imports_count = 0
        total_namespaces_count = 0

        for file_detail in validation_result.get('file_details', []):
            # Build ImportInfo objects
            imports = [
                ImportInfo(
                    schema_location=imp['schema_location'],
                    namespace=imp.get('namespace', ''),
                    status=imp['status'],
                    expected_filename=imp.get('expected_filename')
                )
                for imp in file_detail.get('imports', [])
            ]
            total_imports_count += len(imports)

            # Build NamespaceUsage objects
            namespaces = [
                NamespaceUsage(
                    prefix=ns['prefix'],
                    namespace_uri=ns['namespace_uri'],
                    status=ns['status']
                )
                for ns in file_detail.get('namespaces_used', [])
            ]
            total_namespaces_count += len(namespaces)

            file_import_infos.append(FileImportInfo(
                filename=file_detail['filename'],
                imports=imports,
                namespaces_used=namespaces
            ))

        import_validation_report = ImportValidationReport(
            status='pass' if validation_result['valid'] else 'fail',
            files=file_import_infos,
            summary=validation_result['summary'],
            total_files=validation_result['total_schemas'],
            total_imports=total_imports_count,
            total_namespaces=total_namespaces_count,
            missing_count=validation_result.get('total_missing_count', 0)
        )

        # Step 5: Build legacy response for backward compatibility
        can_convert = validation_result['valid']
        missing_deps = []
        blocking_issues = []

        # Format missing imports for response
        for missing_import in validation_result.get('missing_imports', []):
            missing_deps.append({
                'schema_location': missing_import['schema_location'],
                'source_file': missing_import['source_file'],
                'status': 'missing'
            })
            blocking_issues.append(
                f"Missing schema: {missing_import['expected_filename']} "
                f"(imported by {missing_import['source_file']} as {missing_import['schema_location']})"
            )

        # Format missing namespaces for response
        for missing_ns in validation_result.get('missing_namespaces', []):
            missing_deps.append({
                'namespace': missing_ns['namespace_uri'],
                'prefix': missing_ns['prefix'],
                'source_file': missing_ns['source_file'],
                'status': 'missing'
            })
            blocking_issues.append(
                f"Missing schema for namespace {missing_ns['namespace_uri']} "
                f"(used as {missing_ns['prefix']}: in {missing_ns['source_file']})"
            )

        return {
            "can_convert": can_convert,
            "summary": validation_result['summary'],
            "total_imports": (
                len(validation_result.get('missing_imports', []))
                + len(validation_result.get('missing_namespaces', []))
            ),
            "satisfied_imports": [],
            "missing_imports": missing_deps,
            "blocking_issues": blocking_issues,
            "resolved_schemas_count": validation_result['total_schemas'],
            "temp_path": resolved_dir,
            "import_validation_report": import_validation_report
        }

    except Exception as e:
        logger.error(f"Failed to validate schema dependencies: {e}")
        return {
            "can_convert": False,
            "summary": f"Validation failed: {str(e)}",
            "total_imports": 0,
            "satisfied_imports": [],
            "missing_imports": [],
            "blocking_issues": [f"Validation failed: {str(e)}"],
            "resolved_schemas_count": 0,
            "temp_path": None
        }


async def _validate_and_read_files(
    files: list[UploadFile], file_paths: list[str] = None
) -> tuple[dict[str, bytes], dict[str, str], UploadFile, str]:
    """Validate and read uploaded files.

    Args:
        files: List of uploaded XSD files
        file_paths: List of relative file paths (preserves directory structure)

    Returns:
        Tuple of (file_contents, file_path_map, primary_file, schema_id)
    """
    if not files:
        raise HTTPException(status_code=400, detail="No files provided")

    file_contents = {}
    file_path_map = {}  # Maps filename -> relative path
    total_size = 0

    # If no paths provided, use just filenames
    if not file_paths:
        file_paths = [file.filename for file in files]

    if len(files) != len(file_paths):
        raise HTTPException(status_code=400, detail="Number of files and paths must match")

    # Filter to only XSD files, log warning if non-XSD files are present
    xsd_files = []
    xsd_paths = []
    non_xsd_count = 0

    for file, path in zip(files, file_paths, strict=False):
        if not file.filename.endswith('.xsd'):
            logger.warning(f"Ignoring non-XSD file: {file.filename}")
            non_xsd_count += 1
            continue

        xsd_files.append(file)
        xsd_paths.append(path)

    if non_xsd_count > 0:
        logger.info(f"Filtered out {non_xsd_count} non-XSD file(s), processing {len(xsd_files)} XSD file(s)")

    if not xsd_files:
        raise HTTPException(status_code=400, detail="No XSD files found in upload")

    # Process only XSD files
    for file, path in zip(xsd_files, xsd_paths, strict=False):
        content = await file.read()
        # Store by filename for backward compatibility, but track the path
        file_contents[file.filename] = content
        file_path_map[file.filename] = path
        total_size += len(content)

    # Use the first XSD file as the primary schema for ID generation
    primary_file = xsd_files[0]

    # Validate total file size (configurable limit, defaults to 20MB)
    max_file_size_mb = int(os.getenv("MAX_SCHEMA_FILE_SIZE_MB", "20"))
    max_file_size_bytes = max_file_size_mb * 1024 * 1024
    if total_size > max_file_size_bytes:
        raise HTTPException(status_code=400, detail=f"Total file size exceeds {max_file_size_mb}MB limit")

    # Generate schema ID with timestamp for uniqueness based on all files
    timestamp = datetime.now(UTC).isoformat()
    all_content = b''.join(file_contents.values()) + b''.join(f.filename.encode() for f in files)
    schema_id = hashlib.sha256(all_content + timestamp.encode()).hexdigest()

    return file_contents, file_path_map, primary_file, schema_id


async def _validate_all_scheval(file_contents: dict[str, bytes]) -> SchevalReport:
    """Validate all files using schematron rules via scheval tool.

    This is the primary NIEM NDR validation method, providing actionable validation
    errors with precise line/column numbers.

    Args:
        file_contents: Dictionary mapping filename to file content

    Returns:
        Aggregated scheval validation report with line/column information
    """
    logger.info(
        f"Running NIEM NDR validation (scheval) on {len(file_contents)} files"
    )

    if not is_scheval_available():
        logger.warning("Scheval tool not available, skipping NIEM NDR validation")
        return SchevalReport(
            status="error",
            message="Scheval tool not available",
            conformance_target="unknown",
            errors=[],
            warnings=[],
            summary={"total_issues": 0, "error_count": 0, "warning_count": 0},
            metadata={"tool_available": False}
        )

    # Detect schema type from the first file's conformance targets
    schema_type = None
    for filename, content in file_contents.items():
        try:
            detected_type = _detect_niem_schema_type(content.decode())
            if detected_type and detected_type in ['ref', 'ext', 'sub']:
                schema_type = detected_type
                logger.info(f"Detected schema type '{schema_type}' from {filename}")
                break
        except Exception as e:
            logger.warning(f"Could not detect schema type from {filename}: {e}")

    # Default to 'sub' (subset - most lenient) if type could not be detected
    if not schema_type:
        schema_type = 'sub'
        logger.warning("Could not detect schema type, defaulting to 'sub' (subset)")

    if schema_type not in ['ref', 'ext', 'sub']:
        schema_type = 'sub'

    # Get path to pre-compiled XSLT file
    xslt_filename = f"{schema_type}Target-6.0.xsl"
    xslt_path = Path("/app/third_party/niem-ndr/sch") / xslt_filename

    if not xslt_path.exists():
        logger.error(f"Pre-compiled XSLT not found: {xslt_path}")
        return SchevalReport(
            status="error",
            message=f"Pre-compiled schematron XSLT not found: {xslt_filename}",
            conformance_target=f"{schema_type}Target",
            errors=[],
            warnings=[],
            summary={"total_issues": 0, "error_count": 0, "warning_count": 0},
            metadata={"xslt_path": str(xslt_path), "xslt_found": False}
        )

    scheval_validator = SchevalValidator()

    # Aggregate results across all files
    all_errors = []
    all_warnings = []
    total_error_count = 0
    total_warning_count = 0
    has_failures = False

    # Validate each file
    for filename, content in file_contents.items():
        logger.info(f"Validating {filename} with scheval using {xslt_filename}")
        try:
            scheval_result = await scheval_validator.validate_xsd_with_schematron(
                content.decode(),
                str(xslt_path),
                use_compiled_xslt=True
            )

            # Track overall status
            if scheval_result["status"] == "fail":
                has_failures = True

            # Add file context to errors and warnings
            for error in scheval_result.get("errors", []):
                error_with_context = error.copy()
                # Update file field if it's just the temp filename
                if error_with_context["file"] in ["schema.xsd", "instance.xml"]:
                    error_with_context["file"] = filename
                all_errors.append(error_with_context)
                total_error_count += 1

            for warning in scheval_result.get("warnings", []):
                warning_with_context = warning.copy()
                # Update file field if it's just the temp filename
                if warning_with_context["file"] in ["schema.xsd", "instance.xml"]:
                    warning_with_context["file"] = filename
                all_warnings.append(warning_with_context)
                total_warning_count += 1

        except Exception as e:
            logger.error(f"Failed to validate {filename} with scheval: {e}")
            has_failures = True
            # Add error for failed validation
            all_errors.append({
                "file": filename,
                "line": 1,
                "column": 1,
                "message": f"Scheval validation failed: {str(e)}",
                "severity": "error",
                "rule": None
            })
            total_error_count += 1

    # Determine overall status
    if has_failures or total_error_count > 0:
        status = "fail"
    else:
        status = "pass"

    # Build message
    message = f"Validated {len(file_contents)} files with scheval"
    if total_error_count > 0:
        message += f", found {total_error_count} errors"
    if total_warning_count > 0:
        message += f", {total_warning_count} warnings"

    # Map schema type to conformance target URI
    conformance_target_map = {
        'ref': 'https://docs.oasis-open.org/niemopen/ns/specification/NDR/6.0/#ReferenceSchemaDocument',
        'ext': 'https://docs.oasis-open.org/niemopen/ns/specification/NDR/6.0/#ExtensionSchemaDocument',
        'sub': 'https://docs.oasis-open.org/niemopen/ns/specification/NDR/6.0/#SubsetSchemaDocument',
    }
    conformance_target = conformance_target_map.get(schema_type, conformance_target_map['sub'])

    # Convert to SchevalIssue objects
    scheval_errors = [SchevalIssue(**error) for error in all_errors]
    scheval_warnings = [SchevalIssue(**warning) for warning in all_warnings]

    scheval_report = SchevalReport(
        status=status,
        message=message,
        conformance_target=conformance_target,
        errors=scheval_errors,
        warnings=scheval_warnings,
        summary={
            "total_issues": total_error_count + total_warning_count,
            "error_count": total_error_count,
            "warning_count": total_warning_count,
            "files_validated": len(file_contents)
        },
        metadata={
            "schema_type": schema_type,
            "xslt_file": xslt_filename,
            "validation_tool": "scheval"
        }
    )

    return scheval_report


async def _convert_to_cmf(
    file_contents: dict[str, bytes],
    file_path_map: dict[str, str],
    primary_file: UploadFile,
    primary_content: bytes
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """Convert XSD to CMF and optionally to JSON Schema.

    Args:
        file_contents: Dictionary of filename to file content
        file_path_map: Dictionary of filename to relative path
        primary_file: Primary uploaded file
        primary_content: Primary file content

    Returns:
        Tuple of (cmf_conversion_result, json_schema_conversion_result)
    """
    logger.info(f"Starting CMF conversion for {primary_file.filename}")

    if not is_cmf_available():
        logger.error("CMF tool not available")
        raise HTTPException(
            status_code=500,
            detail="Schema upload failed: CMF tool is not available on this server"
        )

    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Write all uploaded schema files to temp directory WITH directory structure
        for filename, content in file_contents.items():
            # Get the relative path for this file (preserves directory structure)
            relative_path = file_path_map.get(filename, filename)
            schema_file_path = temp_path / relative_path

            # Create parent directories if needed
            schema_file_path.parent.mkdir(parents=True, exist_ok=True)

            with open(schema_file_path, 'w', encoding='utf-8') as f:
                f.write(content.decode())
            logger.info(f"Created temporary schema file: {relative_path}")

        # Validate dependencies within uploaded files
        logger.info("Validating schema dependencies")
        # Get primary file's relative path
        primary_file_path = file_path_map.get(primary_file.filename, primary_file.filename)
        dependency_report = _validate_schema_dependencies(
            temp_path, primary_file_path, primary_content.decode()
        )
        logger.info(f"Dependency validation: {dependency_report['summary']}")

        # Get the resolved directory path for cleanup
        resolved_temp_path = dependency_report.get("temp_path", temp_path)

        try:
            # Check if all dependencies are satisfied
            if not dependency_report["can_convert"]:
                logger.error(f"Cannot convert to CMF: {dependency_report['blocking_issues']}")
                # Return early with dependency report but don't raise exception
                # Let caller combine with NDR validation and decide how to fail
                return {
                    "status": "dependency_failed",
                    "dependency_report": dependency_report,
                    "import_validation_report": dependency_report.get("import_validation_report")
                }, None

            logger.info("All dependencies satisfied, proceeding with CMF conversion")

            # Convert XSD to CMF using resolved temp path with primary file's relative path
            cmf_conversion_result = convert_xsd_to_cmf(
                resolved_temp_path, primary_file_path
            )

            logger.info(
                f"CMF conversion result: "
                f"{cmf_conversion_result.get('status') if cmf_conversion_result else 'None'}"
            )

            if cmf_conversion_result.get("status") != "success":
                error_msg = cmf_conversion_result.get('error', 'Unknown CMF conversion error')
                error_details = cmf_conversion_result.get('details', [])

                # Log detailed error information
                logger.error(f"XSD to CMF conversion failed: {error_msg}")
                if error_details:
                    for detail in error_details:
                        logger.error(f"CMF Error Detail: {detail}")

                # Return CMF error without raising - let caller combine with NDR validation
                cmf_conversion_result["dependency_report"] = dependency_report
                cmf_conversion_result["import_validation_report"] = dependency_report.get("import_validation_report")
                return cmf_conversion_result, None

            # Add dependency report to CMF result
            cmf_conversion_result["dependency_report"] = dependency_report
            cmf_conversion_result["import_validation_report"] = dependency_report.get("import_validation_report")

            # Convert CMF to JSON Schema
            json_schema_conversion_result = None
            try:
                cmf_content = cmf_conversion_result["cmf_content"]
                json_schema_conversion_result = convert_cmf_to_jsonschema(cmf_content)
                if json_schema_conversion_result.get("status") != "success":
                    logger.warning(
                        f"CMF to JSON Schema conversion failed: "
                        f"{json_schema_conversion_result.get('error', 'Unknown error')}"
                    )
                    json_schema_conversion_result = None
            except Exception as e:
                logger.warning(f"CMF to JSON Schema conversion failed: {e}")
                json_schema_conversion_result = None

            return cmf_conversion_result, json_schema_conversion_result

        finally:
            # Clean up the resolved directory if it's different from temp_path
            if 'resolved_temp_path' in locals() and resolved_temp_path and resolved_temp_path != temp_path:
                try:
                    import shutil
                    shutil.rmtree(resolved_temp_path)
                    logger.debug(f"Cleaned up resolved schema directory: {resolved_temp_path}")
                except Exception as cleanup_error:
                    logger.warning(f"Failed to clean up resolved directory {resolved_temp_path}: {cleanup_error}")


async def _store_schema_files(
    s3: Minio,
    schema_id: str,
    primary_filename: str,
    file_contents: dict[str, bytes],
    file_path_map: dict[str, str],
    cmf_conversion_result: dict[str, Any] | None,
    json_schema_conversion_result: dict[str, Any] | None
) -> None:
    """Store all schema-related files in MinIO.

    Args:
        s3: MinIO client
        schema_id: Generated schema ID
        primary_filename: Name of the primary XSD file
        file_contents: Original XSD file contents
        file_path_map: Dictionary of filename to relative path
        cmf_conversion_result: CMF conversion result
        json_schema_conversion_result: JSON Schema conversion result
    """
    # Store all original XSD files in MinIO WITH directory structure
    for filename, content in file_contents.items():
        # Use the relative path to preserve directory structure
        relative_path = file_path_map.get(filename, filename)
        object_path = f"{schema_id}/source/{relative_path}"
        await upload_file(s3, "niem-schemas", object_path, content, "application/xml")
        logger.info(f"Stored schema file: {object_path}")

    # Extract base name from primary filename (remove path and .xsd extension)
    # Handle both forward slashes (Unix/Mac) and backslashes (Windows)
    filename_only = primary_filename.replace('\\', '/').split('/')[-1]
    base_name = filename_only.rsplit('.xsd', 1)[0] if filename_only.endswith('.xsd') else filename_only

    # Store CMF file if conversion succeeded
    if cmf_conversion_result and cmf_conversion_result.get("cmf_content"):
        cmf_content = cmf_conversion_result["cmf_content"].encode('utf-8')
        cmf_filename = f"{base_name}.cmf"
        await upload_file(s3, "niem-schemas", f"{schema_id}/{cmf_filename}", cmf_content, "application/xml")
        logger.info(f"Successfully converted and stored CMF file: {cmf_filename}")

    # Store JSON Schema file if conversion succeeded
    if json_schema_conversion_result and json_schema_conversion_result.get("jsonschema"):
        json_schema_content = json.dumps(json_schema_conversion_result["jsonschema"], indent=2).encode('utf-8')
        json_filename = f"{base_name}.json"
        await upload_file(s3, "niem-schemas", f"{schema_id}/{json_filename}", json_schema_content, "application/json")
        logger.info(f"Successfully converted and stored JSON Schema file: {json_filename}")


async def _generate_and_store_mapping(
    s3: Minio,
    schema_id: str,
    cmf_conversion_result: dict[str, Any] | None
) -> None:
    """Generate mapping YAML from CMF and store it.

    Args:
        s3: MinIO client
        schema_id: Generated schema ID
        cmf_conversion_result: CMF conversion result
    """
    has_cmf_content = (
        cmf_conversion_result.get('cmf_content') is not None
        if cmf_conversion_result else False
    )
    logger.error(
        f"*** DEBUG: About to check mapping generation. CMF result exists: "
        f"{cmf_conversion_result is not None}, has CMF content: {has_cmf_content} ***"
    )

    if not (cmf_conversion_result and cmf_conversion_result.get("cmf_content")):
        return

    try:
        logger.error("*** DEBUG: Starting mapping generation process ***")
        from ..services.domain.schema import generate_mapping_from_cmf_content, validate_mapping_coverage_from_data

        cmf_content = cmf_conversion_result["cmf_content"]
        logger.error(f"*** DEBUG: CMF content length: {len(cmf_content)} ***")

        # Generate mapping using in-memory CMF content (no temp files needed)
        logger.error("*** DEBUG: About to call generate_mapping_from_cmf_content ***")
        mapping_dict = generate_mapping_from_cmf_content(cmf_content)
        logger.error(f"*** DEBUG: Generated mapping dict with {len(mapping_dict)} keys ***")

        # Validate mapping coverage using in-memory data
        logger.error("*** DEBUG: About to validate mapping coverage ***")
        coverage_result = validate_mapping_coverage_from_data(cmf_content, mapping_dict)
        logger.error("*** DEBUG: Coverage validation completed ***")

        # Add coverage information to mapping
        mapping_dict["coverage_validation"] = coverage_result

        # Convert to YAML and store (with coverage info)
        logger.error("*** DEBUG: About to convert to YAML and upload ***")
        mapping_yaml = yaml.dump(mapping_dict, default_flow_style=False, indent=2)
        mapping_content = mapping_yaml.encode('utf-8')
        await upload_file(s3, "niem-schemas", f"{schema_id}/mapping.yaml", mapping_content, "application/x-yaml")
        logger.error("*** DEBUG: Mapping YAML upload completed ***")

        # Log results
        summary = coverage_result.get("summary", {})
        logger.info(f"Successfully generated and stored mapping YAML for schema {schema_id}")
        logger.info(
            f"Mapping stats: {len(mapping_dict.get('namespaces', {}))} namespaces, "
            f"{len(mapping_dict.get('objects', []))} objects, "
            f"{len(mapping_dict.get('associations', []))} associations, "
            f"{len(mapping_dict.get('references', []))} references"
        )
        logger.info(f"Coverage validation: {summary.get('overall_coverage_percentage', 0):.1f}% overall coverage")

        if summary.get("has_critical_issues", False):
            logger.warning("Mapping has critical validation issues - check coverage_validation section in mapping.yaml")

    except Exception as e:
        logger.error(f"Failed to generate mapping YAML: {e}")
        # Mapping generation is required - fail the upload
        raise HTTPException(
            status_code=500,
            detail=f"Schema upload failed: Could not generate required mapping YAML - {str(e)}"
        ) from e


async def _store_schema_metadata(
    s3: Minio,
    schema_id: str,
    primary_file: UploadFile,
    file_contents: dict[str, bytes],
    timestamp: str
) -> None:
    """Store schema metadata and mark as active.

    Args:
        s3: MinIO client
        schema_id: Generated schema ID
        primary_file: Primary uploaded file
        file_contents: All file contents
        timestamp: Upload timestamp
    """
    # Calculate JSON schema and CMF filenames from primary filename
    filename_only = primary_file.filename.replace('\\', '/').split('/')[-1]
    base_name = filename_only.rsplit('.xsd', 1)[0] if filename_only.endswith('.xsd') else filename_only
    json_schema_filename = f"{base_name}.json"
    cmf_filename = f"{base_name}.cmf"

    # Store schema metadata in MinIO
    schema_metadata = {
        "schema_id": schema_id,
        "primary_filename": primary_file.filename,
        "json_schema_filename": json_schema_filename,
        "cmf_filename": cmf_filename,
        "all_filenames": list(file_contents.keys()),
        "uploaded_at": timestamp,
        "known_gaps": "",
        "is_active": True  # Latest uploaded schema is automatically active
    }
    metadata_content = json.dumps(schema_metadata, indent=2).encode()
    await upload_file(s3, "niem-schemas", f"{schema_id}/metadata.json", metadata_content, "application/json")

    # Mark this as the active schema by storing its ID
    active_schema_marker = {"active_schema_id": schema_id, "updated_at": timestamp}
    active_content = json.dumps(active_schema_marker, indent=2).encode()
    await upload_file(s3, "niem-schemas", "active_schema.json", active_content, "application/json")


async def handle_schema_upload(
    files: list[UploadFile],
    s3: Minio,
    skip_niem_ndr: bool = False,
    file_paths: list[str] = None
) -> SchemaResponse:
    """Handle XSD schema upload and validation - supports multiple related XSD files

    Args:
        files: List of uploaded XSD files
        s3: MinIO client for storage
        skip_niem_ndr: If True, skip NIEM NDR validation
        file_paths: List of relative file paths (preserves directory structure)
    """
    try:
        # Step 1: Validate and read files
        file_contents, file_path_map, primary_file, schema_id = await _validate_and_read_files(files, file_paths)
        primary_content = file_contents[primary_file.filename]
        timestamp = datetime.now(UTC).isoformat()

        # Step 2: Validate NIEM NDR conformance using scheval (unless skipped)
        scheval_report = None
        if not skip_niem_ndr:
            scheval_report = await _validate_all_scheval(file_contents)
        else:
            logger.info("Skipping NIEM NDR validation as requested")

        # Step 3: Convert to CMF and JSON Schema
        cmf_conversion_result, json_schema_conversion_result = await _convert_to_cmf(
            file_contents, file_path_map, primary_file, primary_content
        )

        # Step 3.5: Check all validations and fail with combined reports if any failed
        scheval_has_errors = scheval_report and scheval_report.status in (
            "fail",
            "error",
        )
        import_has_errors = cmf_conversion_result and cmf_conversion_result.get(
            "status"
        ) in ("dependency_failed", "fail", "error")

        if scheval_has_errors or import_has_errors:
            # Extract import validation report
            import_validation_report = (
                cmf_conversion_result.get("import_validation_report")
                if cmf_conversion_result else None
            )

            # Build combined error message
            error_parts = []
            if scheval_has_errors:
                scheval_error_count = scheval_report.summary.get("error_count", 0)
                error_parts.append(
                    f"NIEM NDR validation found {scheval_error_count} error(s)"
                )
            if import_has_errors:
                cmf_status = cmf_conversion_result.get("status")
                if cmf_status == "dependency_failed":
                    blocking_issues = (
                        cmf_conversion_result.get("dependency_report", {}).get(
                            "blocking_issues", []
                        )
                    )
                    error_parts.append(
                        f"Missing {len(blocking_issues)} required schema dependencies"
                    )
                else:
                    error_parts.append(
                        f"CMF conversion failed: "
                        f"{cmf_conversion_result.get('error', 'Unknown error')}"
                    )

            combined_message = "Schema upload rejected: " + " and ".join(error_parts)

            # Raise exception with all validation reports
            raise HTTPException(
                status_code=400,
                detail={
                    "message": combined_message,
                    "scheval_report": (
                        scheval_report.model_dump() if scheval_report else None
                    ),
                    "import_validation_report": (
                        import_validation_report.model_dump()
                        if import_validation_report
                        else None
                    ),
                    "cmf_error": (
                        cmf_conversion_result.get("error")
                        if import_has_errors
                        else None
                    ),
                },
            )

        # Step 4: Store all schema files
        await _store_schema_files(
            s3, schema_id, primary_file.filename, file_contents, file_path_map,
            cmf_conversion_result, json_schema_conversion_result
        )

        # Step 5: Generate and store mapping YAML
        await _generate_and_store_mapping(s3, schema_id, cmf_conversion_result)

        # Step 6: Store metadata and mark as active
        await _store_schema_metadata(s3, schema_id, primary_file, file_contents, timestamp)

        # Extract import validation report from CMF conversion result
        import_validation_report = cmf_conversion_result.get("import_validation_report")

        return SchemaResponse(
            schema_id=schema_id,
            scheval_report=scheval_report,
            import_validation_report=import_validation_report,
            is_active=True  # Latest uploaded schema is automatically active
        )

    except Exception as e:
        logger.error(f"Schema upload failed: {e}")
        if isinstance(e, HTTPException):
            raise
        raise HTTPException(status_code=500, detail=f"Schema upload failed: {str(e)}") from e


async def handle_schema_activation(schema_id: str, s3: Minio):
    """Activate a schema by updating the active marker"""
    try:
        # Check if schema exists by looking for its metadata
        try:
            s3.get_object("niem-schemas", f"{schema_id}/metadata.json")
        except S3Error as e:
            raise HTTPException(status_code=404, detail="Schema not found") from e

        # Update active schema marker
        timestamp = datetime.now(UTC).isoformat()
        active_schema_marker = {"active_schema_id": schema_id, "updated_at": timestamp}
        active_content = json.dumps(active_schema_marker, indent=2).encode()
        await upload_file(s3, "niem-schemas", "active_schema.json", active_content, "application/json")

        return {"active_schema_id": schema_id}

    except Exception as e:
        logger.error(f"Schema activation failed: {e}")
        if isinstance(e, HTTPException):
            raise
        raise HTTPException(status_code=500, detail=f"Schema activation failed: {str(e)}") from e


def get_all_schemas(s3: Minio):
    """Get all schemas from MinIO storage"""
    try:
        schemas = []

        # Get active schema ID
        active_schema_id = get_active_schema_id(s3)

        # List all schema directories - handle case where bucket doesn't exist
        try:
            objects = s3.list_objects("niem-schemas", recursive=False)
        except S3Error as e:
            # If bucket doesn't exist, return empty list
            if e.code == "NoSuchBucket":
                logger.info("Schema bucket does not exist, returning empty schema list")
                return []
            else:
                raise

        for obj in objects:
            if obj.object_name.endswith('/') and obj.object_name != "active_schema.json":
                schema_dir = obj.object_name.rstrip('/')

                # Load metadata for this schema
                try:
                    from ..clients.s3_client import get_json_content
                    metadata = get_json_content(s3, "niem-schemas", f"{schema_dir}/metadata.json")

                    # Mark as active if it matches the active schema
                    metadata["active"] = (metadata["schema_id"] == active_schema_id)
                    schemas.append(metadata)

                except S3Error:
                    # Skip schemas without metadata
                    continue

        # Sort by upload time, newest first
        schemas.sort(key=lambda x: x.get("uploaded_at", ""), reverse=True)
        return schemas

    except Exception as e:
        logger.error(f"Failed to get schemas: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get schemas: {str(e)}") from e


def get_active_schema_id(s3: Minio) -> str | None:
    """Get the currently active schema ID"""
    from ..clients.s3_client import get_json_content
    try:
        active_data = get_json_content(s3, "niem-schemas", "active_schema.json")
        return active_data.get("active_schema_id")
    except S3Error:
        return None


def get_schema_metadata(s3: Minio, schema_id: str) -> dict | None:
    """Get metadata for a specific schema"""
    from ..clients.s3_client import get_json_content
    try:
        return get_json_content(s3, "niem-schemas", f"{schema_id}/metadata.json")
    except S3Error:
        return None


async def handle_schema_file_download(schema_id: str, file_type: str, s3: Minio):
    """Download generated schema files (CMF or JSON Schema).

    Args:
        schema_id: Schema ID
        file_type: Type of file to download ('cmf' or 'json')
        s3: MinIO client

    Returns:
        File content as bytes

    Raises:
        HTTPException: If schema not found or file type invalid
    """
    # Validate file type
    if file_type not in ['cmf', 'json']:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type '{file_type}'. Must be 'cmf' or 'json'"
        )

    # Get schema metadata to determine filename
    metadata = get_schema_metadata(s3, schema_id)
    if not metadata:
        raise HTTPException(status_code=404, detail="Schema not found")

    # Determine the filename to download
    if file_type == 'cmf':
        filename = metadata.get('cmf_filename')
    else:  # json
        filename = metadata.get('json_schema_filename')

    if not filename:
        raise HTTPException(
            status_code=404,
            detail=f"No {file_type.upper()} file found for this schema"
        )

    # Download file from MinIO
    from ..clients.s3_client import download_file
    try:
        object_path = f"{schema_id}/{filename}"
        content = await download_file(s3, "niem-schemas", object_path)
        return content, filename
    except S3Error as e:
        logger.error(f"Failed to download {file_type} file for schema {schema_id}: {e}")
        raise HTTPException(
            status_code=404,
            detail=f"{file_type.upper()} file not found in storage"
        ) from e
