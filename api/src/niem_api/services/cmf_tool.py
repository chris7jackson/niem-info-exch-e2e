#!/usr/bin/env python3
"""
CMF Tool Business Logic

Handles business operations using the CMF tool:
- XSD to CMF conversion
- CMF to JSON Schema conversion

Low-level CMF tool wrapper functions are in clients/cmf_client.py
"""

import json
import logging
import os
import tempfile
import time
from pathlib import Path
from typing import Any

# Import from client layer
from ..clients.cmf_client import (
    CMF_TOOL_PATH,
    CMFError,
    download_and_setup_cmf,
    get_cmf_version,
    is_cmf_available,
    run_cmf_command,
)

logger = logging.getLogger(__name__)

# Re-export client functions for backward compatibility
__all__ = [
    "CMFError",
    "is_cmf_available",
    "run_cmf_command",
    "download_and_setup_cmf",
    "get_cmf_version",
    "CMF_TOOL_PATH",
    "convert_xsd_to_cmf",
    "convert_cmf_to_jsonschema",
]

# CMF tool is used for XML validation against schemas and XSD-to-JSON conversion


def _fix_reference_objects_structure(schema: dict) -> dict:
    """
    Fix the JSON schema structure to properly handle NIEM reference objects.

    The cmftool m2jmsg command may incorrectly place metadata properties directly
    in the main type. This function moves them into an exch:ReferenceObjects
    wrapper as per NIEM JSON-LD conventions.

    Args:
        schema: The JSON schema dictionary to fix

    Returns:
        Fixed JSON schema dictionary
    """
    import copy

    # Work on a deep copy to avoid modifying the original
    schema = copy.deepcopy(schema)

    # Find types that need fixing (typically exch:CrashDriverInfoType and similar)
    # We look for types that have both metadata properties and other content
    metadata_props = ["nc:Metadata", "priv:PrivacyMetadata"]

    # Track if we made any changes
    changes_made = False

    # Create a list of items to iterate over (avoids modifying dict during iteration)
    for type_name, type_def in list(schema.get("definitions", {}).items()):
        if not isinstance(type_def, dict):
            continue

        properties = type_def.get("properties", {})

        # Check if this type has metadata properties that should be wrapped
        has_metadata = any(prop in properties for prop in metadata_props)
        has_other_props = any(prop not in metadata_props for prop in properties.keys())

        # Only fix if we have both metadata and other properties
        # (pure metadata types don't need wrapping)
        # Also check that it's not already the ReferenceObjectType itself
        if has_metadata and has_other_props and "exch:" in type_name and type_name != "exch:ReferenceObjectType":
            logger.info(f"Fixing reference objects structure in {type_name}")

            # Extract metadata properties
            metadata_to_move = {}
            for prop in metadata_props:
                if prop in properties:
                    metadata_to_move[prop] = properties.pop(prop)

            # Only create ReferenceObjects if we actually moved something
            if metadata_to_move:
                changes_made = True

                # Create or get the ReferenceObjectType
                ref_obj_type_name = "exch:ReferenceObjectType"
                if ref_obj_type_name not in schema.get("definitions", {}):
                    schema["definitions"][ref_obj_type_name] = {
                        "description": "A data type for objects that do not apply to their parent (and appear only by reference).",
                        "type": "object",
                        "properties": {},
                    }

                # Add metadata properties to ReferenceObjectType
                # (merge with existing properties if any)
                existing_ref_props = schema["definitions"][ref_obj_type_name].get("properties", {})
                existing_ref_props.update(metadata_to_move)
                schema["definitions"][ref_obj_type_name]["properties"] = existing_ref_props

                # Add ReferenceObjects property to the main type if not already present
                if "exch:ReferenceObjects" not in properties:
                    properties["exch:ReferenceObjects"] = {"$ref": "#/properties/exch:ReferenceObjects"}

                # Ensure the property is defined at the top level
                if "properties" not in schema:
                    schema["properties"] = {}

                if "exch:ReferenceObjects" not in schema["properties"]:
                    schema["properties"]["exch:ReferenceObjects"] = {
                        "description": "Objects that do not apply to their parent (and appear only by reference).",
                        "$ref": f"#/definitions/{ref_obj_type_name}",
                    }

                logger.info(f"Moved {len(metadata_to_move)} metadata properties to ReferenceObjects")

    # Log if no changes were needed
    if not changes_made:
        logger.info("Schema already has correct reference objects structure, no changes needed")

    return schema


def convert_xsd_to_cmf(source_dir: Path = None, primary_filename: str = "schema.xsd") -> dict[str, Any]:
    """
    Convert XSD to CMF using CMF tool with NIEM dependency resolution.
    Returns the CMF content as a string.
    """

    logger.info("Starting XSD to CMF conversion with CMF tool")

    if not CMF_TOOL_PATH:
        raise CMFError("CMF tool not available")

    # Security: Validate primary_filename to prevent path traversal
    if not primary_filename or not isinstance(primary_filename, str):
        raise CMFError("Invalid primary filename")

    # Security: Ensure filename doesn't contain path traversal sequences
    if ".." in primary_filename:
        raise CMFError(f"Filename must not contain '..' sequences: {primary_filename}")

    # Normalize path separators to forward slashes for consistency
    # Keep the relative path intact since files are stored with directory structure preserved
    primary_filename = primary_filename.replace("\\", "/")
    logger.info(f"Primary filename for CMF conversion: {primary_filename}")

    # Use the pre-resolved directory from schema handler (already contains local files + all NIEM schemas)
    logger.info(f"Using pre-resolved directory with all schemas: {source_dir}")

    # List all files in source directory for debugging
    schema_files = list(source_dir.rglob("*.xsd"))
    logger.info(f"Pre-resolved directory contains {len(schema_files)} XSD files")

    try:
        # Use the pre-resolved directory directly - it should already contain only required dependencies
        logger.info("Using pre-resolved directory directly for CMF conversion (should contain only required schemas)")

        # Count files for verification
        total_files = len(list(source_dir.rglob("*.xsd")))
        logger.info(f"Using {total_files} schemas from pre-resolved directory for CMF conversion")

        # Main schema file should be in the source directory
        main_schema_file = source_dir / primary_filename

        if not main_schema_file.exists():
            return {
                "status": "error",
                "error": f"Primary schema file '{primary_filename}' not found in source directory",
            }

        # For deeply nested primary files, change working directory to the file's parent
        # This avoids issues with cmftool resolving nested paths with spaces
        primary_file_parent = main_schema_file.parent
        primary_file_name = main_schema_file.name

        # Create output CMF file in the primary file's directory (cmftool writes to cwd)
        cmf_file = primary_file_parent / "model.cmf"

        # Convert XSD to CMF using primary file's parent directory as working directory
        # This ensures cmftool can resolve imports relative to the primary file's location
        # IMPORTANT: Use just the filename (not nested path) to avoid cmftool path issues
        logger.info(f"Converting XSD to CMF with working directory: {primary_file_parent}")
        logger.info(f"Primary schema file (name only): {primary_file_name}")
        logger.info(f"Primary schema file (absolute): {main_schema_file}")

        result = run_cmf_command(["x2m", "-o", "model.cmf", primary_file_name], working_dir=str(primary_file_parent))

        if result["returncode"] != 0:
            errors = []
            if result["stderr"]:
                errors.append(result["stderr"])
            if result["stdout"]:
                errors.append(result["stdout"])

            logger.error(f"CMF conversion failed with return code {result['returncode']}")
            logger.error(f"STDERR: {result.get('stderr', 'None')}")
            logger.error(f"STDOUT: {result.get('stdout', 'None')}")

            return {"status": "error", "error": "Failed to convert XSD to CMF", "details": errors}

        # Read the generated CMF content
        if cmf_file.exists():
            with open(cmf_file, encoding="utf-8") as f:
                cmf_content = f.read()

            logger.info(f"Successfully converted XSD to CMF, generated {len(cmf_content)} characters of CMF content")
        else:
            return {"status": "error", "error": "CMF file was not generated", "details": ["Output file not found"]}

        return {
            "status": "success",
            "cmf_content": cmf_content,
            "metadata": {"converter": "cmftool", "conversion_time": time.time(), "resolved_schemas_count": total_files},
        }

    except Exception as e:
        logger.error(f"CMF conversion failed: {e}")
        return {"status": "error", "error": f"CMF conversion failed: {str(e)}"}

    finally:
        # Note: Resolved schema directory cleanup is handled by the schema handler
        pass


def convert_cmf_to_jsonschema(cmf_content: str) -> dict[str, Any]:
    """
    Convert CMF content to JSON Schema using CMF tool (m2jmsg command).
    """
    logger.info("Starting CMF to JSON Schema conversion")

    if not CMF_TOOL_PATH:
        raise CMFError("CMF tool not available")

    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            # Write CMF content to temporary file
            cmf_file = os.path.join(temp_dir, "model.cmf")
            with open(cmf_file, "w", encoding="utf-8") as f:
                f.write(cmf_content)

            # Output JSON Schema file
            json_schema_file = os.path.join(temp_dir, "schema.json")

            try:
                # Convert CMF to JSON Schema
                # Security: Use relative paths (just filenames) since we're in temp_dir
                logger.info("Converting CMF to JSON Schema using cmftool m2jmsg...")
                result = run_cmf_command(["m2jmsg", "-o", "schema.json", "model.cmf"], working_dir=temp_dir)

                logger.info(f"CMF to JSON Schema conversion completed with return code: {result['returncode']}")
                if result["stdout"]:
                    logger.info(f"STDOUT: {result['stdout']}")
                if result["stderr"]:
                    logger.info(f"STDERR: {result['stderr']}")

                if result["returncode"] != 0:
                    errors = []
                    if result["stderr"]:
                        errors.append(result["stderr"])
                    if result["stdout"]:
                        errors.append(result["stdout"])

                    logger.error(f"CMF to JSON Schema conversion failed with errors: {errors}")
                    return {"status": "error", "error": "Failed to convert CMF to JSON Schema", "details": errors}

                # Read the generated JSON Schema
                if os.path.exists(json_schema_file):
                    with open(json_schema_file, encoding="utf-8") as f:
                        json_schema = json.loads(f.read())
                else:
                    return {
                        "status": "error",
                        "error": "JSON Schema file was not generated",
                        "details": ["Output file not found"],
                    }

                # Apply fix for NIEM reference objects structure
                # This is a workaround for cmftool m2jmsg incorrectly handling metadata
                logger.info("Applying NIEM reference objects structure fix to generated schema")
                json_schema = _fix_reference_objects_structure(json_schema)

                return {
                    "status": "success",
                    "jsonschema": json_schema,
                    "metadata": {
                        "converter": "cmftool",
                        "conversion_time": time.time(),
                        "post_processed": True,
                        "fix_applied": "reference_objects_structure",
                    },
                }

            except Exception as e:
                logger.error(f"JSON Schema conversion failed: {e}")
                return {"status": "error", "error": f"JSON Schema conversion failed: {str(e)}"}

    except Exception as e:
        logger.error(f"CMF to JSON Schema conversion failed: {e}")
        return {"status": "error", "error": f"CMF to JSON Schema conversion failed: {str(e)}"}
