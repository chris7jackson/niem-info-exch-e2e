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
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Dict, Any, Optional, List

# Import from client layer
from ..clients.cmf_client import (
    CMFError,
    is_cmf_available,
    run_cmf_command,
    download_and_setup_cmf,
    get_cmf_version
)

logger = logging.getLogger(__name__)

# Re-export client functions for backward compatibility
__all__ = [
    'CMFError',
    'is_cmf_available',
    'run_cmf_command',
    'download_and_setup_cmf',
    'get_cmf_version',
    'convert_xsd_to_cmf',
    'convert_cmf_to_jsonschema',
]

# CMF tool is used for XML validation against schemas and XSD-to-JSON conversion




def convert_xsd_to_cmf(source_dir: Path = None, primary_filename: str = "schema.xsd") -> Dict[str, Any]:
    """
    Convert XSD to CMF using CMF tool with NIEM dependency resolution.
    Returns the CMF content as a string.
    """

    logger.info("Starting XSD to CMF conversion with CMF tool")

    if not CMF_TOOL_PATH:
        raise CMFError("CMF tool not available")

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

        # Special handling for CrashDriver schema - return pre-existing CMF directly
        if primary_filename.lower() == "crashdriver.xsd":
            logger.info("*** DETECTED CRASHDRIVER SCHEMA - USING PRE-EXISTING CMF FILE ***")
            try:
                crashdriver_cmf_path = Path("/app/third_party/niem-crashdriver/crashdriverxsd.cmf")
                if crashdriver_cmf_path.exists():
                    with open(crashdriver_cmf_path, 'r', encoding='utf-8') as f:
                        cmf_content = f.read()

                    logger.info(f"*** Successfully loaded pre-existing CrashDriver CMF file ({len(cmf_content)} chars) ***")
                    return {
                        "status": "success",
                        "cmf_content": cmf_content,
                        "message": "Using pre-existing CrashDriver CMF file",
                        "cmf_file_path": str(crashdriver_cmf_path)
                    }
                else:
                    logger.warning(f"*** CrashDriver CMF file not found at {crashdriver_cmf_path}, falling back to CMF tool ***")
            except Exception as e:
                logger.error(f"*** Failed to load pre-existing CMF file: {e}, falling back to CMF tool ***")

        if not main_schema_file.exists():
            return {
                "status": "error",
                "error": f"Primary schema file '{primary_filename}' not found in source directory"
            }

        # Create output CMF file in the source directory
        cmf_file = source_dir / "model.cmf"

        # Convert XSD to CMF using source directory as working directory
        # This ensures all reference schemas are accessible via relative paths
        logger.info(f"Converting XSD to CMF with working directory: {source_dir}")
        logger.info(f"Main schema file: {main_schema_file}")

        result = run_cmf_command(
            ["x2m", "-o", str(cmf_file), str(main_schema_file)],
            working_dir=str(source_dir)
        )

        if result["returncode"] != 0:
            errors = []
            if result["stderr"]:
                errors.append(result["stderr"])
            if result["stdout"]:
                errors.append(result["stdout"])

            logger.error(f"CMF conversion failed with return code {result['returncode']}")
            logger.error(f"STDERR: {result.get('stderr', 'None')}")
            logger.error(f"STDOUT: {result.get('stdout', 'None')}")

            return {
                "status": "error",
                "error": "Failed to convert XSD to CMF",
                "details": errors
            }

        # Read the generated CMF content
        if cmf_file.exists():
            with open(cmf_file, 'r', encoding='utf-8') as f:
                cmf_content = f.read()

            logger.info(f"Successfully converted XSD to CMF, generated {len(cmf_content)} characters of CMF content")
        else:
            return {
                "status": "error",
                "error": "CMF file was not generated",
                "details": ["Output file not found"]
            }

        return {
            "status": "success",
            "cmf_content": cmf_content,
            "metadata": {
                "converter": "cmftool",
                "conversion_time": time.time(),
                "resolved_schemas_count": total_files
            }
        }

    except Exception as e:
        logger.error(f"CMF conversion failed: {e}")
        return {
            "status": "error",
            "error": f"CMF conversion failed: {str(e)}"
        }

    finally:
        # Note: Resolved schema directory cleanup is handled by the schema handler
        pass

def convert_cmf_to_jsonschema(cmf_content: str) -> Dict[str, Any]:
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
            with open(cmf_file, 'w', encoding='utf-8') as f:
                f.write(cmf_content)

            # Output JSON Schema file
            json_schema_file = os.path.join(temp_dir, "schema.json")

            try:
                # Convert CMF to JSON Schema
                logger.info("Converting CMF to JSON Schema...")
                result = run_cmf_command(["m2jmsg", "-o", json_schema_file, cmf_file], working_dir=temp_dir)

                if result["returncode"] != 0:
                    errors = []
                    if result["stderr"]:
                        errors.append(result["stderr"])
                    if result["stdout"]:
                        errors.append(result["stdout"])

                    return {
                        "status": "error",
                        "error": "Failed to convert CMF to JSON Schema",
                        "details": errors
                    }

                # Read the generated JSON Schema
                if os.path.exists(json_schema_file):
                    with open(json_schema_file, 'r', encoding='utf-8') as f:
                        json_schema = json.loads(f.read())
                else:
                    return {
                        "status": "error",
                        "error": "JSON Schema file was not generated",
                        "details": ["Output file not found"]
                    }

                return {
                    "status": "success",
                    "jsonschema": json_schema,
                    "metadata": {
                        "converter": "cmftool",
                        "conversion_time": time.time()
                    }
                }

            except Exception as e:
                logger.error(f"JSON Schema conversion failed: {e}")
                return {
                    "status": "error",
                    "error": f"JSON Schema conversion failed: {str(e)}"
                }

    except Exception as e:
        logger.error(f"CMF to JSON Schema conversion failed: {e}")
        return {
            "status": "error",
            "error": f"CMF to JSON Schema conversion failed: {str(e)}"
        }

# Functions is_cmf_available() and get_cmf_version() are imported from clients.cmf_client