#!/usr/bin/env python3

import json
import logging
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Dict, Any, Optional

from .niem_dependency_resolver import create_resolved_schema_directory

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


async def validate_xml_with_cmf(xml_content: str, xsd_schema: str) -> Dict[str, Any]:
    """
    Validate XML document against XSD schema using CMF xval command with NIEM dependency resolution.
    """
    logger.info("Starting XML validation with CMF tool")

    if not CMF_TOOL_PATH:
        raise CMFError("CMF tool not available")

    # Resolve NIEM dependencies for the schema
    try:
        schema_dir = await create_resolved_schema_directory(xsd_schema, "schema.xsd")
        logger.info(f"Created resolved schema directory with dependencies: {schema_dir}")
    except Exception as e:
        logger.warning(f"Failed to resolve NIEM dependencies, falling back to single schema: {e}")
        # Fallback to original behavior
        return await _validate_xml_single_schema(xml_content, xsd_schema)

    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            # Write XML content to temporary file
            xml_file = os.path.join(temp_dir, "document.xml")
            with open(xml_file, 'w', encoding='utf-8') as f:
                f.write(xml_content)

            # Use the main schema file from resolved directory
            main_schema_file = schema_dir / "schema.xsd"

            # Use xval command to validate XML against XSD with all dependencies
            result = run_cmf_command(["xval", "--schema", str(main_schema_file), "--file", xml_file], working_dir=str(schema_dir))

            if result["returncode"] == 0:
                # Success - XML is valid
                return {
                    "status": "valid",
                    "report": {
                        "errors": [],
                        "warnings": [],
                        "valid": True
                    }
                }
            else:
                # Parse errors from stderr and stdout
                errors = []
                if result["stderr"]:
                    errors.append(result["stderr"])
                if result["stdout"]:
                    # Filter out informational messages
                    stdout_lines = [line for line in result["stdout"].split('\n')
                                  if line.strip() and not line.startswith('INFO')]
                    if stdout_lines:
                        errors.extend(stdout_lines)

                return {
                    "status": "invalid",
                    "report": {
                        "errors": errors if errors else ["XML validation failed"],
                        "warnings": [],
                        "valid": False
                    }
                }

    except CMFError as e:
        return {
            "status": "invalid",
            "report": {
                "errors": [str(e)],
                "warnings": [],
                "valid": False
            }
        }
    finally:
        # Clean up resolved schema directory
        if 'schema_dir' in locals() and schema_dir.exists():
            shutil.rmtree(schema_dir)
            logger.debug(f"Cleaned up resolved schema directory: {schema_dir}")


async def convert_xsd_to_jsonschema_with_cmf(xsd_content: str) -> Dict[str, Any]:
    """
    Convert XSD to JSON Schema using CMF tool (x2m + m2jmsg commands) with NIEM dependency resolution.
    """
    logger.info("Starting XSD to JSON Schema conversion with CMF tool")

    if not CMF_TOOL_PATH:
        raise CMFError("CMF tool not available")

    # Resolve NIEM dependencies for the schema
    try:
        schema_dir = await create_resolved_schema_directory(xsd_content, "schema.xsd")
        logger.info(f"Created resolved schema directory with dependencies: {schema_dir}")
    except Exception as e:
        logger.warning(f"Failed to resolve NIEM dependencies, falling back to single schema: {e}")
        # Fallback to original behavior
        return await _convert_xsd_single_schema(xsd_content)

    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            # Use the main schema file from resolved directory
            main_schema_file = schema_dir / "schema.xsd"

            # Intermediate CMF file
            cmf_file = os.path.join(temp_dir, "model.cmf")

            # Output JSON Schema file
            json_schema_file = os.path.join(temp_dir, "schema.json")

            try:
                # Step 1: Convert XSD to CMF
                logger.info("Converting XSD to CMF...")
                result = run_cmf_command(["x2m", "-o", cmf_file, str(main_schema_file)], working_dir=str(schema_dir))

                if result["returncode"] != 0:
                    errors = []
                    if result["stderr"]:
                        errors.append(result["stderr"])
                    if result["stdout"]:
                        errors.append(result["stdout"])

                    return {
                        "status": "error",
                        "error": "Failed to convert XSD to CMF",
                        "details": errors
                    }

                # Step 2: Convert CMF to JSON Schema
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
                        "version": "mounted",
                        "converted_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                    }
                }

            except CMFError as e:
                return {
                    "status": "error",
                    "error": str(e),
                    "details": []
                }

    finally:
        # Clean up resolved schema directory
        if 'schema_dir' in locals() and schema_dir.exists():
            shutil.rmtree(schema_dir)
            logger.debug(f"Cleaned up resolved schema directory: {schema_dir}")


async def _validate_xml_single_schema(xml_content: str, xsd_schema: str) -> Dict[str, Any]:
    """Fallback validation without dependency resolution"""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Write XML content to temporary file
        xml_file = os.path.join(temp_dir, "document.xml")
        with open(xml_file, 'w', encoding='utf-8') as f:
            f.write(xml_content)

        # Write XSD schema to temporary file
        xsd_file = os.path.join(temp_dir, "schema.xsd")
        with open(xsd_file, 'w', encoding='utf-8') as f:
            f.write(xsd_schema)

        try:
            # Use xval command to validate XML against XSD
            result = run_cmf_command(["xval", "--schema", xsd_file, "--file", xml_file], working_dir=temp_dir)

            if result["returncode"] == 0:
                return {
                    "status": "valid",
                    "report": {
                        "errors": [],
                        "warnings": [],
                        "valid": True
                    }
                }
            else:
                errors = []
                if result["stderr"]:
                    errors.append(result["stderr"])
                if result["stdout"]:
                    stdout_lines = [line for line in result["stdout"].split('\n')
                                  if line.strip() and not line.startswith('INFO')]
                    if stdout_lines:
                        errors.extend(stdout_lines)

                return {
                    "status": "invalid",
                    "report": {
                        "errors": errors if errors else ["XML validation failed"],
                        "warnings": [],
                        "valid": False
                    }
                }

        except CMFError as e:
            return {
                "status": "invalid",
                "report": {
                    "errors": [str(e)],
                    "warnings": [],
                    "valid": False
                }
            }


async def _convert_xsd_single_schema(xsd_content: str) -> Dict[str, Any]:
    """Fallback conversion without dependency resolution"""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Write XSD content to temporary file
        xsd_file = os.path.join(temp_dir, "schema.xsd")
        with open(xsd_file, 'w', encoding='utf-8') as f:
            f.write(xsd_content)

        # Intermediate CMF file
        cmf_file = os.path.join(temp_dir, "model.cmf")

        # Output JSON Schema file
        json_schema_file = os.path.join(temp_dir, "schema.json")

        try:
            # Step 1: Convert XSD to CMF
            result = run_cmf_command(["x2m", "-o", cmf_file, xsd_file], working_dir=temp_dir)

            if result["returncode"] != 0:
                errors = []
                if result["stderr"]:
                    errors.append(result["stderr"])
                if result["stdout"]:
                    errors.append(result["stdout"])

                return {
                    "status": "error",
                    "error": "Failed to convert XSD to CMF",
                    "details": errors
                }

            # Step 2: Convert CMF to JSON Schema
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
                    "version": "mounted",
                    "converted_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                }
            }

        except CMFError as e:
            return {
                "status": "error",
                "error": str(e),
                "details": []
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