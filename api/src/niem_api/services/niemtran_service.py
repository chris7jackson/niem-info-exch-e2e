#!/usr/bin/env python3
"""
NIEMTran Service

Business logic for NIEM XML to JSON conversion operations.
Handles temporary file management, conversion orchestration, and result processing.
"""

import json
import logging
import tempfile
from pathlib import Path
from typing import Dict, Any, Optional

from ..clients.niemtran_client import run_niemtran_command, is_niemtran_available, NIEMTranError

logger = logging.getLogger(__name__)


async def convert_xml_to_json(
    xml_content: bytes, cmf_content: str, context_uri: Optional[str] = None
) -> Dict[str, Any]:
    """
    Convert NIEM XML content to JSON using NIEMTran tool.

    This service handles:
    1. Creating temporary files for XML and CMF inputs
    2. Running the NIEMTran x2j command
    3. Reading and parsing the resulting JSON
    4. Cleaning up temporary files
    5. Error handling and reporting

    The complete @context is always included in the conversion result.

    Args:
        xml_content: XML file content as bytes
        cmf_content: CMF model content as string
        context_uri: Optional URI to include as "@context:" URI pair

    Returns:
        Dictionary with:
        - success: bool - whether conversion succeeded
        - json_content: dict - parsed JSON content (if successful)
        - json_string: str - formatted JSON string (if successful)
        - error: str - error message (if failed)
        - stderr: str - NIEMTran stderr output (if failed)

    Raises:
        NIEMTranError: If NIEMTran tool is not available
    """
    if not is_niemtran_available():
        raise NIEMTranError("NIEMTran tool is not available")

    # Create temporary directory for conversion
    with tempfile.TemporaryDirectory(prefix="niemtran_") as temp_dir:
        temp_path = Path(temp_dir)

        try:
            # Write XML content to temporary file
            xml_file = temp_path / "input.xml"
            xml_file.write_bytes(xml_content)
            logger.info(f"Wrote XML input to temporary file: {xml_file}")

            # Write CMF content to temporary file
            cmf_file = temp_path / "model.cmf"
            cmf_file.write_text(cmf_content, encoding="utf-8")
            logger.info(f"Wrote CMF model to temporary file: {cmf_file}")

            # Build NIEMTran command
            cmd = ["x2j"]

            # Always include complete @context
            cmd.append("--context")

            # Add optional context URI
            if context_uri:
                cmd.extend(["--curi", context_uri])

            # Add CMF model and XML input files
            cmd.extend(["model.cmf", "input.xml"])

            logger.info(f"Running NIEMTran conversion with command: {cmd}")

            # Run conversion
            result = run_niemtran_command(cmd, timeout=60, working_dir=str(temp_path))

            # Check if conversion succeeded
            if result["returncode"] != 0:
                error_msg = result["stderr"] or result["stdout"] or "Unknown error"
                logger.error(f"NIEMTran conversion failed: {error_msg}")
                return {
                    "success": False,
                    "error": f"Conversion failed: {error_msg}",
                    "stderr": result["stderr"],
                    "stdout": result["stdout"],
                }

            # Read the generated JSON file
            # NIEMTran creates input.json from input.xml
            json_file = temp_path / "input.json"

            if not json_file.exists():
                logger.error("NIEMTran did not create output JSON file")
                return {
                    "success": False,
                    "error": "Conversion completed but output file was not created",
                    "stderr": result["stderr"],
                    "stdout": result["stdout"],
                }

            # Read and parse JSON content
            json_string = json_file.read_text(encoding="utf-8")
            json_content = json.loads(json_string)

            logger.info("Successfully converted XML to JSON")

            return {
                "success": True,
                "json_content": json_content,
                "json_string": json_string,
                "message": "XML successfully converted to JSON",
            }

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse generated JSON: {e}")
            return {"success": False, "error": f"Generated JSON is invalid: {str(e)}"}
        except Exception as e:
            logger.error(f"Unexpected error during conversion: {e}")
            return {"success": False, "error": f"Unexpected error: {str(e)}"}
