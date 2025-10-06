#!/usr/bin/env python3

import hashlib
import json
import logging
import os
import yaml
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Any, Optional

import httpx
from fastapi import HTTPException, UploadFile
from minio import Minio
from minio.error import S3Error

from ..models.models import SchemaResponse, NiemNdrReport, NiemNdrViolation
from ..clients.s3_client import upload_file
from ..services.domain.schema import NiemNdrValidator
from ..services.cmf_tool import convert_xsd_to_cmf, convert_cmf_to_jsonschema, is_cmf_available

logger = logging.getLogger(__name__)


def _extract_schema_imports(xsd_content: str) -> List[Dict[str, Any]]:
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


def _read_local_schemas(source_dir: Path) -> Dict[str, str]:
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
                with open(xsd_file, 'r', encoding='utf-8') as f:
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
    import tempfile
    import shutil

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






def _create_error_response(error_type: str, error_msg: str, imports: List[Dict[str, Any]]) -> Dict[str, Any]:
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


def _validate_schema_dependencies(source_dir: Path, schema_filename: str, xsd_content: str) -> Dict[str, Any]:
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
                    with open(xsd_file, 'r', encoding='utf-8') as f:
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
        from ..models.models import ImportValidationReport, FileImportInfo, ImportInfo, NamespaceUsage

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
            "total_imports": len(validation_result.get('missing_imports', [])) + len(validation_result.get('missing_namespaces', [])),
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


async def _validate_and_read_files(files: List[UploadFile], file_paths: List[str] = None) -> tuple[Dict[str, bytes], Dict[str, str], UploadFile, str]:
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

    for file, path in zip(files, file_paths):
        if not file.filename.endswith('.xsd'):
            raise HTTPException(status_code=400, detail=f"File {file.filename} must have .xsd extension")

        content = await file.read()
        # Store by filename for backward compatibility, but track the path
        file_contents[file.filename] = content
        file_path_map[file.filename] = path
        total_size += len(content)

    # Use the first file as the primary schema for ID generation
    primary_file = files[0]

    # Validate total file size (configurable limit, defaults to 20MB)
    max_file_size_mb = int(os.getenv("MAX_SCHEMA_FILE_SIZE_MB", "20"))
    max_file_size_bytes = max_file_size_mb * 1024 * 1024
    if total_size > max_file_size_bytes:
        raise HTTPException(status_code=400, detail=f"Total file size exceeds {max_file_size_mb}MB limit")

    # Generate schema ID with timestamp for uniqueness based on all files
    timestamp = datetime.now(timezone.utc).isoformat()
    all_content = b''.join(file_contents.values()) + b''.join(f.filename.encode() for f in files)
    schema_id = hashlib.sha256(all_content + timestamp.encode()).hexdigest()

    return file_contents, file_path_map, primary_file, schema_id


async def _validate_all_niem_ndr(file_contents: Dict[str, bytes]) -> NiemNdrReport:
    """Validate NIEM NDR conformance for all uploaded files.

    Args:
        file_contents: Dictionary mapping filename to file content

    Returns:
        Aggregated NIEM NDR validation report
    """
    logger.info(f"Running NDR validation on {len(file_contents)} files")
    ndr_validator = NiemNdrValidator()

    # Aggregate results across all files
    all_violations = []
    total_error_count = 0
    total_warning_count = 0
    total_info_count = 0
    has_failures = False
    has_errors = False

    # Validate each file
    for filename, content in file_contents.items():
        logger.info(f"Validating {filename} against NIEM NDR rules")
        try:
            ndr_result = await ndr_validator.validate_xsd_conformance(content.decode())

            # Track overall status
            if ndr_result["status"] == "fail":
                has_failures = True
            if ndr_result["status"] == "error":
                has_errors = True

            # Add file context to violations
            for violation in ndr_result.get("violations", []):
                violation_with_file = violation.copy()
                violation_with_file["file"] = filename
                all_violations.append(violation_with_file)

            # Aggregate counts
            summary = ndr_result.get("summary", {})
            total_error_count += summary.get("error_count", 0)
            total_warning_count += summary.get("warning_count", 0)
            total_info_count += summary.get("info_count", 0)

        except Exception as e:
            logger.error(f"Failed to validate {filename}: {e}")
            has_errors = True
            all_violations.append({
                "type": "error",
                "rule": "validation_error",
                "message": f"Failed to validate {filename}: {str(e)}",
                "location": filename,
                "file": filename
            })
            total_error_count += 1

    # Determine overall status
    if has_errors:
        status = "error"
    elif has_failures or total_error_count > 0:
        status = "fail"
    else:
        status = "pass"

    # Build aggregated summary
    aggregated_summary = {
        "total_violations": len(all_violations),
        "error_count": total_error_count,
        "warning_count": total_warning_count,
        "info_count": total_info_count,
        "files_validated": len(file_contents)
    }

    # Convert violations to model
    ndr_violations = [
        NiemNdrViolation(**violation) for violation in all_violations
    ]

    message = f"Validated {len(file_contents)} files"
    if total_error_count > 0:
        message += f", found {total_error_count} errors"
    if total_warning_count > 0:
        message += f", {total_warning_count} warnings"

    niem_ndr_report = NiemNdrReport(
        status=status,
        message=message,
        conformance_target="all",
        violations=ndr_violations,
        summary=aggregated_summary
    )

    # Check if NIEM validation failed - reject upload if validation fails
    if status == "fail":
        error_messages = [v["message"] for v in all_violations if v["type"] == "error"]
        violation_summary = f"Found {total_error_count} NIEM NDR violations across {len(file_contents)} files"
        if error_messages:
            violation_summary += f": {'; '.join(error_messages[:3])}"  # Show first 3 errors
            if len(error_messages) > 3:
                violation_summary += f" ... and {len(error_messages) - 3} more"

        raise HTTPException(
            status_code=400,
            detail=f"Schema upload rejected due to NIEM NDR validation failures. {violation_summary}"
        )

    # Check if validation encountered an error
    if status == "error":
        raise HTTPException(
            status_code=500,
            detail=f"NIEM NDR validation error: {message}"
        )

    return niem_ndr_report




async def _convert_to_cmf(
    file_contents: Dict[str, bytes],
    file_path_map: Dict[str, str],
    primary_file: UploadFile,
    primary_content: bytes
) -> tuple[Dict[str, Any] | None, Dict[str, Any] | None]:
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
            # Only proceed with CMF conversion if all dependencies are satisfied
            if not dependency_report["can_convert"]:
                logger.error(f"Cannot convert to CMF: {dependency_report['blocking_issues']}")
                blocking_issues_str = '\n- '.join([''] + dependency_report['blocking_issues'])
                raise HTTPException(
                    status_code=400,
                    detail=f"Schema upload failed: Missing required dependencies. Please upload all referenced schema files:{blocking_issues_str}"
                )

            logger.info("All dependencies satisfied, proceeding with CMF conversion")

            # Convert XSD to CMF using resolved temp path with primary file's relative path
            cmf_conversion_result = convert_xsd_to_cmf(
                resolved_temp_path, primary_file_path
            )

            logger.info(f"CMF conversion result: {cmf_conversion_result.get('status') if cmf_conversion_result else 'None'}")

            if cmf_conversion_result.get("status") != "success":
                error_msg = cmf_conversion_result.get('error', 'Unknown CMF conversion error')
                error_details = cmf_conversion_result.get('details', [])

                # Log detailed error information
                logger.error(f"XSD to CMF conversion failed: {error_msg}")
                if error_details:
                    for detail in error_details:
                        logger.error(f"CMF Error Detail: {detail}")

                # Create user-friendly error message
                detail_msg = f"Schema upload failed: CMF conversion error - {error_msg}"
                if error_details:
                    # Include first few lines of error details for context
                    detail_summary = error_details[0][:500] if error_details[0] else ""
                    if len(detail_summary) > 0:
                        detail_msg += f"\n\nError details: {detail_summary}"
                        if len(error_details[0]) > 500:
                            detail_msg += "... (truncated)"

                raise HTTPException(
                    status_code=400,
                    detail=detail_msg
                )

            # Add dependency report to CMF result
            cmf_conversion_result["dependency_report"] = dependency_report
            cmf_conversion_result["import_validation_report"] = dependency_report.get("import_validation_report")

            # Convert CMF to JSON Schema
            json_schema_conversion_result = None
            try:
                cmf_content = cmf_conversion_result["cmf_content"]
                json_schema_conversion_result = convert_cmf_to_jsonschema(cmf_content)
                if json_schema_conversion_result.get("status") != "success":
                    logger.warning(f"CMF to JSON Schema conversion failed: {json_schema_conversion_result.get('error', 'Unknown error')}")
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
    file_contents: Dict[str, bytes],
    file_path_map: Dict[str, str],
    cmf_conversion_result: Dict[str, Any] | None,
    json_schema_conversion_result: Dict[str, Any] | None
) -> None:
    """Store all schema-related files in MinIO.

    Args:
        s3: MinIO client
        schema_id: Generated schema ID
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

    # Store CMF file if conversion succeeded
    if cmf_conversion_result and cmf_conversion_result.get("cmf_content"):
        cmf_content = cmf_conversion_result["cmf_content"].encode('utf-8')
        await upload_file(s3, "niem-schemas", f"{schema_id}/schema.cmf", cmf_content, "application/xml")
        logger.info(f"Successfully converted and stored CMF file for schema {schema_id}")

    # Store JSON Schema file if conversion succeeded
    if json_schema_conversion_result and json_schema_conversion_result.get("jsonschema"):
        json_schema_content = json.dumps(json_schema_conversion_result["jsonschema"], indent=2).encode('utf-8')
        await upload_file(s3, "niem-schemas", f"{schema_id}/schema.json", json_schema_content, "application/json")
        logger.info(f"Successfully converted and stored JSON Schema file for schema {schema_id}")


async def _generate_and_store_mapping(
    s3: Minio,
    schema_id: str,
    cmf_conversion_result: Dict[str, Any] | None
) -> None:
    """Generate mapping YAML from CMF and store it.

    Args:
        s3: MinIO client
        schema_id: Generated schema ID
        cmf_conversion_result: CMF conversion result
    """
    logger.error(f"*** DEBUG: About to check mapping generation. CMF result exists: {cmf_conversion_result is not None}, has CMF content: {cmf_conversion_result.get('cmf_content') is not None if cmf_conversion_result else False} ***")

    if not (cmf_conversion_result and cmf_conversion_result.get("cmf_content")):
        return

    try:
        logger.error("*** DEBUG: Starting mapping generation process ***")
        from ..services.domain.schema import generate_mapping_from_cmf_content
        from ..services.domain.schema import validate_mapping_coverage_from_data

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
        logger.info(f"Mapping stats: {len(mapping_dict.get('namespaces', {}))} namespaces, {len(mapping_dict.get('objects', []))} objects, {len(mapping_dict.get('associations', []))} associations, {len(mapping_dict.get('references', []))} references")
        logger.info(f"Coverage validation: {summary.get('overall_coverage_percentage', 0):.1f}% overall coverage")

        if summary.get("has_critical_issues", False):
            logger.warning("Mapping has critical validation issues - check coverage_validation section in mapping.yaml")

    except Exception as e:
        logger.error(f"Failed to generate mapping YAML: {e}")
        # Mapping generation is required - fail the upload
        raise HTTPException(
            status_code=500,
            detail=f"Schema upload failed: Could not generate required mapping YAML - {str(e)}"
        )


async def _store_schema_metadata(
    s3: Minio,
    schema_id: str,
    primary_file: UploadFile,
    file_contents: Dict[str, bytes],
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
    # Store schema metadata in MinIO
    schema_metadata = {
        "schema_id": schema_id,
        "primary_filename": primary_file.filename,
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
    files: List[UploadFile],
    s3: Minio,
    skip_niem_ndr: bool = False,
    file_paths: List[str] = None
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
        timestamp = datetime.now(timezone.utc).isoformat()

        # Step 2: Validate NIEM NDR conformance for ALL files (unless skipped)
        niem_ndr_report = None
        if not skip_niem_ndr:
            niem_ndr_report = await _validate_all_niem_ndr(file_contents)
        else:
            logger.info("Skipping NIEM NDR validation as requested")

        # Step 3: Convert to CMF and JSON Schema
        cmf_conversion_result, json_schema_conversion_result = await _convert_to_cmf(
            file_contents, file_path_map, primary_file, primary_content
        )

        # Step 4: Store all schema files
        await _store_schema_files(s3, schema_id, file_contents, file_path_map, cmf_conversion_result, json_schema_conversion_result)

        # Step 5: Generate and store mapping YAML
        await _generate_and_store_mapping(s3, schema_id, cmf_conversion_result)

        # Step 6: Store metadata and mark as active
        await _store_schema_metadata(s3, schema_id, primary_file, file_contents, timestamp)

        # Extract import validation report from CMF conversion result
        import_validation_report = cmf_conversion_result.get("import_validation_report")

        return SchemaResponse(
            schema_id=schema_id,
            niem_ndr_report=niem_ndr_report,
            import_validation_report=import_validation_report,
            is_active=True  # Latest uploaded schema is automatically active
        )

    except Exception as e:
        logger.error(f"Schema upload failed: {e}")
        if isinstance(e, HTTPException):
            raise
        raise HTTPException(status_code=500, detail=f"Schema upload failed: {str(e)}")


async def handle_schema_activation(schema_id: str, s3: Minio):
    """Activate a schema by updating the active marker"""
    try:
        # Check if schema exists by looking for its metadata
        try:
            s3.get_object("niem-schemas", f"{schema_id}/metadata.json")
        except S3Error:
            raise HTTPException(status_code=404, detail="Schema not found")

        # Update active schema marker
        timestamp = datetime.now(timezone.utc).isoformat()
        active_schema_marker = {"active_schema_id": schema_id, "updated_at": timestamp}
        active_content = json.dumps(active_schema_marker, indent=2).encode()
        await upload_file(s3, "niem-schemas", "active_schema.json", active_content, "application/json")

        return {"active_schema_id": schema_id}

    except Exception as e:
        logger.error(f"Schema activation failed: {e}")
        if isinstance(e, HTTPException):
            raise
        raise HTTPException(status_code=500, detail=f"Schema activation failed: {str(e)}")


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
                    metadata_obj = s3.get_object("niem-schemas", f"{schema_dir}/metadata.json")
                    metadata = json.loads(metadata_obj.read().decode())

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
        raise HTTPException(status_code=500, detail=f"Failed to get schemas: {str(e)}")


def get_active_schema_id(s3: Minio) -> Optional[str]:
    """Get the currently active schema ID"""
    try:
        active_obj = s3.get_object("niem-schemas", "active_schema.json")
        active_data = json.loads(active_obj.read().decode())
        return active_data.get("active_schema_id")
    except S3Error:
        return None


def get_schema_metadata(s3: Minio, schema_id: str) -> Optional[Dict]:
    """Get metadata for a specific schema"""
    try:
        metadata_obj = s3.get_object("niem-schemas", f"{schema_id}/metadata.json")
        return json.loads(metadata_obj.read().decode())
    except S3Error:
        return None