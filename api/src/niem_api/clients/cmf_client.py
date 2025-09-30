#!/usr/bin/env python3
"""
NIEM CMF Tool Client

A low-level client wrapper for the NIEM Common Model Format (CMF) command-line tool.
Handles tool detection, command execution, and basic availability checks.

This client is pure infrastructure - it contains no business logic.
For CMF-related business operations (XSD conversion, JSON schema generation),
use the services/cmf_tool.py module.
"""

import json
import logging
import os
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

# CMF tool configuration - check both local and mounted paths
# Go up 5 levels from clients/cmf_client.py to get to project root
_LOCAL_CMF_PATH = Path(__file__).parent.parent.parent.parent.parent / "third_party/niem-cmf/cmftool-1.0-alpha.8/bin/cmftool"
_MOUNTED_CMF_PATH = "/app/third_party/niem-cmf/cmftool-1.0-alpha.8/bin/cmftool"

# Use local path if it exists, otherwise try mounted path
if _LOCAL_CMF_PATH.exists():
    CMF_TOOL_PATH = str(_LOCAL_CMF_PATH)
elif Path(_MOUNTED_CMF_PATH).exists():
    CMF_TOOL_PATH = _MOUNTED_CMF_PATH
else:
    CMF_TOOL_PATH = None

CMF_TIMEOUT = 30  # Default command timeout in seconds


class CMFError(Exception):
    """
    Exception raised when CMF tool operations fail.

    Used for:
    - Tool not found/unavailable
    - Command execution failures
    - Timeout errors
    - Invalid responses
    """
    pass


def is_cmf_available() -> bool:
    """
    Check if CMF tool is available and executable.

    Returns:
        True if CMF tool binary exists and can be executed, False otherwise

    Example:
        ```python
        if is_cmf_available():
            result = run_cmf_command(["xval", "--help"])
        else:
            print("CMF tool not installed")
        ```

    Note:
        This only checks file existence, not actual executability or Java runtime.
        For full verification, try running a simple command like `get_cmf_version()`.
    """
    if not CMF_TOOL_PATH:
        return False

    cmf_path = Path(CMF_TOOL_PATH)
    exists = cmf_path.exists() and cmf_path.is_file()

    if exists:
        logger.debug(f"CMF tool found at: {CMF_TOOL_PATH}")
    else:
        logger.debug(f"CMF tool not found at: {CMF_TOOL_PATH}")

    return exists


def get_cmf_version() -> str:
    """
    Get the version of the installed CMF tool.

    Returns:
        Version string (e.g., "1.0-alpha.8")

    Raises:
        CMFError: If CMF tool is not available or version command fails

    Example:
        ```python
        try:
            version = get_cmf_version()
            print(f"Using CMF tool version: {version}")
        except CMFError as e:
            print(f"CMF tool error: {e}")
        ```
    """
    if not is_cmf_available():
        raise CMFError("CMF tool not available")

    try:
        result = run_cmf_command(["version"], timeout=5)
        if result["returncode"] == 0:
            # Extract version from output
            version = result["stdout"].strip()
            return version if version else "unknown"
        else:
            raise CMFError(f"Version check failed: {result['stderr']}")
    except Exception as e:
        logger.error(f"Failed to get CMF version: {e}")
        raise CMFError(f"Failed to get CMF version: {str(e)}")


async def download_and_setup_cmf() -> bool:
    """
    Check if CMF tool is available at expected mount points.

    This is called during application startup to verify CMF tool availability.
    In the current architecture, the CMF tool is pre-installed and mounted into
    the container, so this just validates the mount.

    Returns:
        True if CMF tool is available, False otherwise

    Note:
        This function is async for consistency with other startup tasks,
        but the actual check is synchronous.
    """
    if is_cmf_available():
        logger.info(f"CMF tool available at mounted path: {CMF_TOOL_PATH}")
        return True
    else:
        logger.warning(f"CMF tool not found at expected path: {CMF_TOOL_PATH}")
        return False


def run_cmf_command(
    cmd: list,
    timeout: int = CMF_TIMEOUT,
    working_dir: Optional[str] = None
) -> Dict[str, Any]:
    """
    Execute a CMF tool command with timeout and safety checks.

    This is the core execution primitive for all CMF operations.
    Handles process management, timeouts, and error capture.

    Args:
        cmd: Command arguments to pass to CMF tool (e.g., ["xval", "--schema", "file.xsd"])
        timeout: Maximum execution time in seconds (default: 30)
        working_dir: Working directory for command execution. If None, uses CMF tool's parent directory.

    Returns:
        Dictionary with keys:
        - returncode: Process exit code (int)
        - stdout: Standard output (str)
        - stderr: Standard error (str)

    Raises:
        CMFError: If CMF tool is unavailable, command times out, or execution fails

    Example:
        ```python
        # Validate XML against XSD schemas
        result = run_cmf_command([
            "xval",
            "--schema", "niem-core.xsd",
            "--schema", "jxdm.xsd",
            "--file", "instance.xml"
        ], timeout=60)

        if result["returncode"] == 0:
            print("Validation successful")
        else:
            print(f"Validation failed: {result['stderr']}")
        ```

    Note:
        - Command output is captured (not streamed)
        - Working directory defaults to CMF tool installation directory
        - Subprocess runs in text mode (UTF-8 encoding)
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
