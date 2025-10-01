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
        List of import dictionaries with namespace, schema_location, and is_niem flags
    """
    import xml.etree.ElementTree as ET

    NIEM_INDICATORS = [
        'docs.oasis-open.org/niemopen',
        'niem.gov',
        'release.niem.gov'
    ]

    # Load catalog mappings
    catalog_path = Path(__file__).parent.parent.parent.parent.parent / 'third_party' / 'niem-xsd' / 'xml-catalog.xml'
    catalog_map = {}

    try:
        if catalog_path.exists():
            catalog_tree = ET.parse(catalog_path)
            catalog_root = catalog_tree.getroot()
            ns = {'cat': 'urn:oasis:names:tc:entity:xmlns:xml:catalog'}

            for uri_elem in catalog_root.findall('cat:uri', ns):
                name = uri_elem.get('name', '')
                uri = uri_elem.get('uri', '')
                if name and uri:
                    catalog_map[name] = uri
    except Exception as e:
        logger.warning(f"Failed to load XML catalog: {e}")

    imports = []
    try:
        root = ET.fromstring(xsd_content)
        for elem in root.iter():
            if elem.tag.endswith('}import') or elem.tag == 'import':
                namespace = elem.get('namespace', '')
                schema_location = elem.get('schemaLocation', '')
                if schema_location:
                    is_niem = any(indicator in namespace for indicator in NIEM_INDICATORS) if namespace else False
                    needs_fetch = is_niem and namespace not in catalog_map

                    imports.append({
                        'namespace': namespace,
                        'schema_location': schema_location,
                        'is_niem': is_niem,
                        'needs_fetch': needs_fetch,
                        'local_path': catalog_map.get(namespace)
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


def _resolve_niem_dependencies(source_dir: Path, schema_filename: str, xsd_content: str, resolved_dir: Path, skip_niem_resolution: bool) -> Dict[str, Any]:
    """Resolve NIEM dependencies and get statistics.

    Args:
        source_dir: Source directory
        schema_filename: Primary schema filename
        xsd_content: Primary schema content
        resolved_dir: Directory to copy NIEM schemas to
        skip_niem_resolution: Whether to skip NIEM resolution

    Returns:
        Dictionary with copied files and statistics
    """
    from ..services.domain.schema import resolve_niem_schema_dependencies, get_treeshaking_statistics

    if skip_niem_resolution:
        logger.info("Skipping NIEM dependency resolution - using only uploaded files")
        return {
            "copied_files": {},
            "stats": {"required_files": 0, "total_niem_files": 0, "space_savings_percent": 100}
        }

    # Prepare file contents for NIEM analysis
    file_contents_for_niem = {}
    if source_dir and source_dir.exists():
        for xsd_file in source_dir.glob("*.xsd"):
            try:
                with open(xsd_file, 'r', encoding='utf-8') as f:
                    file_contents_for_niem[xsd_file.name] = f.read()
            except Exception as e:
                logger.warning(f"Failed to read {xsd_file} for NIEM analysis: {e}")
    else:
        file_contents_for_niem[schema_filename] = xsd_content

    # Resolve dependencies
    copied_niem_files = resolve_niem_schema_dependencies(file_contents_for_niem, resolved_dir)
    treeshaking_stats = get_treeshaking_statistics(copied_niem_files)

    logger.info(f"Treeshaking analysis: using {treeshaking_stats.get('required_files', 0)}/{treeshaking_stats.get('total_niem_files', 0)} NIEM schemas ({treeshaking_stats.get('space_savings_percent', 0)}% reduction)")

    return {
        "copied_files": copied_niem_files,
        "stats": treeshaking_stats
    }


def _generate_niem_search_paths(resolved_dir: Path, schema_location: str, is_niem: bool) -> List[Path]:
    """Generate possible search paths for a schema import.

    Args:
        resolved_dir: Resolved directory containing schemas
        schema_location: Schema location from import
        is_niem: Whether this is a NIEM schema

    Returns:
        List of possible paths to check
    """
    possible_paths = [
        resolved_dir / schema_location,  # Direct path
        resolved_dir / "niem" / schema_location,  # Under niem/ prefix
        resolved_dir / schema_location.lstrip('../'),  # Remove ../ prefix
    ]

    if is_niem:
        filename = Path(schema_location).name
        possible_paths.extend([
            resolved_dir / "niem" / "domains" / filename,
            resolved_dir / "niem" / "utility" / filename,
            resolved_dir / "niem" / "adapters" / filename,
            resolved_dir / "niem" / "external" / filename,
            resolved_dir / "niem" / filename,  # Root level like niem-core.xsd
        ])

    return possible_paths


def _validate_imports(imports: List[Dict[str, Any]], resolved_dir: Path, skip_niem_resolution: bool) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[str]]:
    """Validate schema imports and categorize them.

    Args:
        imports: List of import declarations
        resolved_dir: Directory containing resolved schemas
        skip_niem_resolution: Whether NIEM resolution was skipped

    Returns:
        Tuple of (satisfied_imports, missing_imports, blocking_issues)
    """
    satisfied_imports = []
    missing_imports = []
    blocking_issues = []

    if skip_niem_resolution:
        # Assume all imports are satisfied when skipping NIEM resolution
        for imp in imports:
            satisfied_imports.append({
                'schema_location': imp['schema_location'],
                'namespace': imp['namespace'],
                'status': 'assumed_uploaded',
                'path': 'uploaded_files'
            })
        logger.info(f"Skipped validation for {len(imports)} imports - assuming all required files were uploaded")
        return satisfied_imports, missing_imports, blocking_issues

    # Perform actual validation
    for imp in imports:
        schema_location = imp['schema_location']
        possible_paths = _generate_niem_search_paths(resolved_dir, schema_location, imp['is_niem'])

        found_path = None
        for path in possible_paths:
            if path.exists():
                found_path = path
                break

        if found_path:
            satisfied_imports.append({
                'schema_location': schema_location,
                'namespace': imp['namespace'],
                'status': 'found',
                'path': str(found_path.relative_to(resolved_dir))
            })
        else:
            missing_import = {
                'schema_location': schema_location,
                'namespace': imp['namespace'],
                'status': 'missing',
                'is_niem': imp['is_niem']
            }
            missing_imports.append(missing_import)

            if imp['is_niem']:
                blocking_issues.append(f"NIEM schema not found: {schema_location}")

    return satisfied_imports, missing_imports, blocking_issues


def _build_validation_summary(satisfied_imports: List[Dict[str, Any]], missing_imports: List[Dict[str, Any]], blocking_issues: List[str], imports: List[Dict[str, Any]], skip_niem_resolution: bool) -> str:
    """Build validation summary message.

    Args:
        satisfied_imports: List of satisfied imports
        missing_imports: List of missing imports
        blocking_issues: List of blocking issues
        imports: Original list of imports
        skip_niem_resolution: Whether NIEM resolution was skipped

    Returns:
        Summary string
    """
    if skip_niem_resolution:
        return f"Skipped NIEM resolution - assuming {len(imports)} dependencies are provided"

    summary = f"Found {len(satisfied_imports)}/{len(imports)} dependencies"
    if missing_imports:
        summary += f", {len(missing_imports)} missing"
    if blocking_issues:
        summary += f", {len(blocking_issues)} blocking"

    return summary


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


def _validate_schema_dependencies(xsd_content: str, schema_filename: str, source_dir: Path, skip_niem_resolution: bool = False) -> Dict[str, Any]:
    """Validate schema dependencies and create a detailed report.

    Args:
        xsd_content: XSD content as string
        schema_filename: Name of the schema file
        source_dir: Directory containing the schema file
        skip_niem_resolution: If True, skip NIEM dependency resolution

    Returns:
        Dictionary with validation results and dependency report
    """
    logger.error("*** DEBUG: _validate_schema_dependencies function called ***")

    try:
        # Step 1: Extract imports from schema
        imports = _extract_schema_imports(xsd_content)

        # Step 2: Read local schemas
        local_schemas = _read_local_schemas(source_dir)

        # Step 3: Setup resolved directory
        logger.error("*** DEBUG: About to create comprehensive schema directory ***")
        try:
            resolved_dir = _setup_resolved_directory(source_dir, schema_filename, xsd_content)

            logger.error("*** DEBUG: About to start treeshaking - this is the key point ***")

            # Step 4: Resolve NIEM dependencies
            niem_result = _resolve_niem_dependencies(source_dir, schema_filename, xsd_content, resolved_dir, skip_niem_resolution)

            # Step 5: Validate imports
            satisfied_imports, missing_imports, blocking_issues = _validate_imports(imports, resolved_dir, skip_niem_resolution)

            # Step 6: Build summary and determine if conversion can proceed
            can_convert = len(blocking_issues) == 0 or skip_niem_resolution
            summary = _build_validation_summary(satisfied_imports, missing_imports, blocking_issues, imports, skip_niem_resolution)

            return {
                "can_convert": can_convert,
                "summary": summary,
                "total_imports": len(imports),
                "satisfied_imports": satisfied_imports,
                "missing_imports": missing_imports,
                "blocking_issues": blocking_issues,
                "resolved_schemas_count": len(local_schemas) if source_dir else 1,
                "temp_path": resolved_dir
            }

        except Exception as e:
            logger.error(f"Failed to mount NIEM dependencies: {e}")
            return _create_error_response("NIEM mounting failed", str(e), imports)

    except Exception as e:
        logger.error(f"Failed to validate schema dependencies: {e}")
        return _create_error_response("Validation failed", str(e), [])


async def _validate_and_read_files(files: List[UploadFile]) -> tuple[Dict[str, bytes], UploadFile, str]:
    """Validate and read uploaded files.

    Args:
        files: List of uploaded XSD files

    Returns:
        Tuple of (file_contents, primary_file, schema_id)
    """
    if not files:
        raise HTTPException(status_code=400, detail="No files provided")

    file_contents = {}
    total_size = 0

    for file in files:
        if not file.filename.endswith('.xsd'):
            raise HTTPException(status_code=400, detail=f"File {file.filename} must have .xsd extension")

        content = await file.read()
        file_contents[file.filename] = content
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

    return file_contents, primary_file, schema_id


async def _validate_niem_ndr(primary_content: bytes, primary_filename: str) -> NiemNdrReport:
    """Validate NIEM NDR conformance.

    Args:
        primary_content: Primary schema file content
        primary_filename: Primary schema filename

    Returns:
        NIEM NDR validation report
    """
    logger.error(f"*** DEBUG: About to run NDR validation on {primary_filename}")
    ndr_validator = NiemNdrValidator()
    ndr_result = await ndr_validator.validate_xsd_conformance(primary_content.decode())
    logger.error(f"*** DEBUG: NDR validation result: {ndr_result}")

    # Convert NDR result to model
    ndr_violations = [
        NiemNdrViolation(**violation) for violation in ndr_result.get("violations", [])
    ]
    niem_ndr_report = NiemNdrReport(
        status=ndr_result["status"],
        message=ndr_result["message"],
        conformance_target=ndr_result["conformance_target"],
        violations=ndr_violations,
        summary=ndr_result.get("summary", {})
    )

    # Check if NIEM validation failed - reject upload if validation fails
    if ndr_result["status"] == "fail":
        error_messages = [v["message"] for v in ndr_result.get("violations", []) if v["type"] == "error"]
        violation_summary = f"Found {ndr_result['summary']['error_count']} NIEM NDR violations"
        if error_messages:
            violation_summary += f": {'; '.join(error_messages)}"

        raise HTTPException(
            status_code=400,
            detail=f"Schema upload rejected due to NIEM NDR validation failures. {violation_summary}"
        )

    # Check if validation encountered an error
    if ndr_result["status"] == "error":
        raise HTTPException(
            status_code=500,
            detail=f"NIEM NDR validation error: {ndr_result['message']}"
        )

    return niem_ndr_report


def _handle_crashdriver_cmf() -> Dict[str, Any] | None:
    """Handle special case for CrashDriver schema using pre-existing CMF file.

    Returns:
        CMF conversion result or None if not CrashDriver
    """
    logger.error("*** DETECTED CRASHDRIVER SCHEMA - USING PRE-EXISTING CMF FILE ***")
    print("*** PRINT: DETECTED CRASHDRIVER SCHEMA - USING PRE-EXISTING CMF FILE ***")
    try:
        crashdriver_cmf_path = Path("/app/third_party/niem-crashdriver/crashdriverxsd.cmf")
        logger.error(f"*** Looking for CMF file at: {crashdriver_cmf_path} ***")
        print(f"*** PRINT: Looking for CMF file at: {crashdriver_cmf_path} ***")
        if crashdriver_cmf_path.exists():
            with open(crashdriver_cmf_path, 'r', encoding='utf-8') as f:
                cmf_content = f.read()

            logger.error("*** Successfully loaded pre-existing CrashDriver CMF file ***")
            print("*** PRINT: Successfully loaded pre-existing CrashDriver CMF file ***")
            return {
                "status": "success",
                "cmf_content": cmf_content,
                "message": "Using pre-existing CrashDriver CMF file"
            }
        else:
            logger.error(f"*** CrashDriver CMF file not found at {crashdriver_cmf_path}, falling back to XSD conversion ***")
            print(f"*** PRINT: CrashDriver CMF file not found at {crashdriver_cmf_path}, falling back to XSD conversion ***")
            return None
    except Exception as e:
        logger.error(f"*** Failed to load pre-existing CMF file: {e}, falling back to XSD conversion ***")
        print(f"*** PRINT: Failed to load pre-existing CMF file: {e}, falling back to XSD conversion ***")
        return None


async def _convert_to_cmf(
    file_contents: Dict[str, bytes],
    primary_file: UploadFile,
    primary_content: bytes,
    skip_niem_resolution: bool
) -> tuple[Dict[str, Any] | None, Dict[str, Any] | None]:
    """Convert XSD to CMF and optionally to JSON Schema.

    Args:
        file_contents: Dictionary of filename to file content
        primary_file: Primary uploaded file
        primary_content: Primary file content
        skip_niem_resolution: Skip NIEM dependency resolution

    Returns:
        Tuple of (cmf_conversion_result, json_schema_conversion_result)
    """
    print(f"*** PRINT: Starting CMF conversion section for {primary_file.filename} ***")
    logger.error(f"*** DEBUG: CMF tool available: {is_cmf_available()} ***")
    print(f"*** PRINT: CMF tool available: {is_cmf_available()} ***")

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

        # Write all uploaded schema files to temp directory
        for filename, content in file_contents.items():
            schema_file_path = temp_path / filename
            with open(schema_file_path, 'w', encoding='utf-8') as f:
                f.write(content.decode())
            logger.info(f"Created temporary schema file: {schema_file_path}")

        # Validate dependencies and create dependency report for primary schema
        logger.error("*** DEBUG: About to call _validate_schema_dependencies ***")
        dependency_report = _validate_schema_dependencies(
            primary_content.decode(), primary_file.filename, temp_path, skip_niem_resolution
        )
        logger.error("*** DEBUG: _validate_schema_dependencies completed ***")
        logger.info(f"Dependency validation: {dependency_report['summary']}")

        # Get the resolved directory path for cleanup
        resolved_temp_path = dependency_report.get("temp_path", temp_path)

        try:
            # Only proceed with CMF conversion if critical dependencies are satisfied
            logger.error(f"*** DEBUG: dependency_report can_convert: {dependency_report.get('can_convert', 'NOT_SET')} ***")
            print(f"*** PRINT: dependency_report can_convert: {dependency_report.get('can_convert', 'NOT_SET')} ***")

            if not dependency_report["can_convert"]:
                logger.error(f"Cannot convert to CMF: {dependency_report['blocking_issues']}")
                blocking_issues_str = ', '.join(dependency_report['blocking_issues'])
                raise HTTPException(
                    status_code=400,
                    detail=f"Schema upload failed: Missing critical dependencies - {blocking_issues_str}"
                )

            logger.info("All critical dependencies satisfied, proceeding with CMF conversion")
            logger.error(f"*** DEBUG: Primary file name: '{primary_file.filename}' ***")

            # Check if this is a CrashDriver schema and use pre-existing CMF file
            cmf_conversion_result = None
            if primary_file.filename.lower() == "crashdriver.xsd":
                cmf_conversion_result = _handle_crashdriver_cmf()

            # Fall back to XSD conversion if CrashDriver CMF not found
            if cmf_conversion_result is None:
                cmf_conversion_result = convert_xsd_to_cmf(
                    resolved_temp_path, primary_file.filename
                )

            logger.error(f"*** DEBUG: CMF conversion result: {cmf_conversion_result.get('status') if cmf_conversion_result else 'None'} ***")

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
    cmf_conversion_result: Dict[str, Any] | None,
    json_schema_conversion_result: Dict[str, Any] | None
) -> None:
    """Store all schema-related files in MinIO.

    Args:
        s3: MinIO client
        schema_id: Generated schema ID
        file_contents: Original XSD file contents
        cmf_conversion_result: CMF conversion result
        json_schema_conversion_result: JSON Schema conversion result
    """
    # Store all original XSD files in MinIO
    for filename, content in file_contents.items():
        await upload_file(s3, "niem-schemas", f"{schema_id}/{filename}", content, "application/xml")

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
            logger.warning(f"Mapping has critical validation issues - check coverage_validation section in mapping.yaml")

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
    skip_niem_resolution: bool = False
) -> SchemaResponse:
    """Handle XSD schema upload and validation - supports multiple related XSD files

    Args:
        files: List of uploaded XSD files
        s3: MinIO client for storage
        skip_niem_resolution: If True, only use uploaded files without NIEM dependency resolution
    """
    try:
        logger.error(f"*** DEBUG: skip_niem_resolution parameter = {skip_niem_resolution} ***")

        # Step 1: Validate and read files
        file_contents, primary_file, schema_id = await _validate_and_read_files(files)
        primary_content = file_contents[primary_file.filename]
        timestamp = datetime.now(timezone.utc).isoformat()

        # Step 2: Validate NIEM NDR conformance
        niem_ndr_report = await _validate_niem_ndr(primary_content, primary_file.filename)

        # Step 3: Convert to CMF and JSON Schema
        cmf_conversion_result, json_schema_conversion_result = await _convert_to_cmf(
            file_contents, primary_file, primary_content, skip_niem_resolution
        )

        # Step 4: Store all schema files
        await _store_schema_files(s3, schema_id, file_contents, cmf_conversion_result, json_schema_conversion_result)

        # Step 5: Generate and store mapping YAML
        await _generate_and_store_mapping(s3, schema_id, cmf_conversion_result)

        # Step 6: Store metadata and mark as active
        await _store_schema_metadata(s3, schema_id, primary_file, file_contents, timestamp)


        return SchemaResponse(
            schema_id=schema_id,
            niem_ndr_report=niem_ndr_report,
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