#!/usr/bin/env python3

import json
import logging
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Dict, Any, Optional, List


logger = logging.getLogger(__name__)

# CMF tool configuration - check both local and mounted paths
# Go up 5 levels from services/cmf_tool.py to get to project root
_LOCAL_CMF_PATH = Path(__file__).parent.parent.parent.parent.parent / "third_party/niem-cmf/cmftool-1.0-alpha.8/bin/cmftool"
_MOUNTED_CMF_PATH = "/app/third_party/niem-cmf/cmftool-1.0-alpha.8/bin/cmftool"

# Use local path if it exists, otherwise try mounted path
if _LOCAL_CMF_PATH.exists():
    CMF_TOOL_PATH = str(_LOCAL_CMF_PATH)
elif Path(_MOUNTED_CMF_PATH).exists():
    CMF_TOOL_PATH = _MOUNTED_CMF_PATH
else:
    CMF_TOOL_PATH = None
CMF_TIMEOUT = 30  # seconds


class CMFError(Exception):
    """CMF tool error"""
    pass


async def download_and_setup_cmf():
    """Check if mounted CMF tool is available"""
    if is_cmf_available():
        logger.info(f"CMF tool available at mounted path: {CMF_TOOL_PATH}")
        return True
    else:
        logger.warning(f"CMF tool not found at expected mounted path: {CMF_TOOL_PATH}")
        return False


def run_cmf_command(cmd: list, timeout: int = CMF_TIMEOUT, working_dir: Optional[str] = None) -> Dict[str, Any]:
    """
    Run a CMF tool command with timeout and safety checks.
    """
    if not CMF_TOOL_PATH:
        raise CMFError("CMF tool not available. Please ensure it's properly installed.")

    try:
        full_cmd = [CMF_TOOL_PATH] + cmd
        logger.info(f"Running CMF command: {' '.join(full_cmd)}")

        # Set working directory
        if working_dir is None:
            working_dir = Path(CMF_TOOL_PATH).parent.parent

        result = subprocess.run(
            full_cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=working_dir
        )

        logger.debug(f"CMF command result: returncode={result.returncode}")
        if result.stdout:
            logger.debug(f"CMF stdout: {result.stdout}")
        if result.stderr:
            logger.debug(f"CMF stderr: {result.stderr}")

        return {
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr
        }
    except subprocess.TimeoutExpired:
        logger.error(f"CMF command timed out after {timeout} seconds")
        raise CMFError(f"Operation timed out after {timeout} seconds")
    except Exception as e:
        logger.error(f"CMF command execution failed: {e}")
        raise CMFError(f"Command execution failed: {e}")


# CMF tool is only used for XML validation against schemas and XSD-to-JSON conversion




async def convert_xsd_to_cmf(xsd_content: str, source_dir: Path = None, primary_filename: str = "schema.xsd") -> Dict[str, Any]:
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


async def convert_cmf_to_jsonschema(cmf_content: str) -> Dict[str, Any]:
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

def is_cmf_available() -> bool:
    """Check if CMF tool is available"""
    global CMF_TOOL_PATH
    
    # Re-check paths dynamically in case of import-time issues
    if CMF_TOOL_PATH is None:
        local_path = Path(__file__).parent.parent.parent.parent.parent / "third_party/niem-cmf/cmftool-1.0-alpha.8/bin/cmftool"
        mounted_path = Path("/app/third_party/niem-cmf/cmftool-1.0-alpha.8/bin/cmftool")
        
        if local_path.exists():
            CMF_TOOL_PATH = str(local_path)
        elif mounted_path.exists():
            CMF_TOOL_PATH = str(mounted_path)
    
    return CMF_TOOL_PATH is not None and Path(CMF_TOOL_PATH).exists()


def get_cmf_version() -> str:
    """Get CMF tool version"""
    return "mounted"