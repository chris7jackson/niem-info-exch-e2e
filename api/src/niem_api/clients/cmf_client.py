#!/usr/bin/env python3
"""
NIEM CMF Tool Client

A low-level client wrapper for the NIEM Common Model Format (CMF) command-line tool.
Handles tool detection, command execution, and basic availability checks.

This client is pure infrastructure - it contains no business logic.
For CMF-related business operations (XSD conversion, JSON schema generation),
use the services/cmf_tool.py module.
"""

import logging
import os
import subprocess
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# CMF tool configuration
# Check for environment variable first, then fall back to default path
_CMF_PATH_ENV = os.getenv("CMF_TOOL_PATH")

if _CMF_PATH_ENV:
    # Use environment variable if set
    CMF_TOOL_PATH = _CMF_PATH_ENV
    logger.debug(f"Using CMF_TOOL_PATH from environment: {CMF_TOOL_PATH}")
else:
    # Default: Go up 4 levels from clients/cmf_client.py to get to api/ directory
    # File is at: api/src/niem_api/clients/cmf_client.py -> need 4 .parent to reach api/
    # In Docker, the container is always Linux, so always use the shell script (not .bat)
    _CMF_SCRIPT_NAME = "cmftool"
    _CMF_DEFAULT_PATH = Path(__file__).parent.parent.parent.parent / f"third_party/niem-cmf/cmftool-1.0/bin/{_CMF_SCRIPT_NAME}"

    if _CMF_DEFAULT_PATH.exists():
        CMF_TOOL_PATH = str(_CMF_DEFAULT_PATH)
        logger.debug(f"Using default CMF tool path: {CMF_TOOL_PATH}")
    else:
        CMF_TOOL_PATH = None
        logger.warning(f"CMF tool not found at default path ({_CMF_DEFAULT_PATH}) and CMF_TOOL_PATH not set")

CMF_TIMEOUT = 30  # Default command timeout in seconds

# Security: Allowlist of valid CMF tool subcommands
# Only these commands can be executed via run_cmf_command()
ALLOWED_CMF_COMMANDS = {
    "x2m",      # XSD to CMF conversion
    "m2jmsg",   # CMF to JSON Schema message conversion
    "xval",     # XML validation
    "version",  # Get CMF tool version
    "help",     # Help command
}

# Security: Allowlist of valid CMF tool flags
# Only these flags are allowed in command arguments
ALLOWED_CMF_FLAGS = {
    "-o", "--output",           # Output file specification
    "-s", "--schema",           # Schema file specification
    "-f", "--file",             # Input file specification
    "-h", "--help",             # Help flag
    "-v", "--version",          # Version flag
    "--niem-version",           # NIEM version specification
    "--no-validation",          # Skip validation
}


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
        raise CMFError(f"Failed to get CMF version: {str(e)}") from e


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


def parse_cmf_validation_output(stdout: str, stderr: str, filename: str) -> dict[str, Any]:
    """
    Parse CMF tool validation output into structured error information.

    The CMF xval tool outputs validation errors with markers like [error], [warning], etc.
    This function extracts those into structured ValidationError objects.

    Args:
        stdout: Standard output from CMF command
        stderr: Standard error from CMF command
        filename: File being validated (for context)

    Returns:
        Dictionary with:
        - errors: List of error dictionaries
        - warnings: List of warning dictionaries
        - has_errors: Boolean indicating if errors were found

    Example output line:
        [error] file.xml:42:15: cvc-complex-type.2.4.a: Invalid content
    """
    import re

    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []

    # Combine stdout and stderr for parsing
    combined_output = (stdout or "") + "\n" + (stderr or "")

    # Pattern to match CMF error/warning lines
    # Format: [severity] filename:line:column: message
    # Or: [severity] message (without location)
    pattern = r'\[(error|warning|info)\]\s+(?:([^:]+):(\d+):(\d+):\s*)?(.+)'

    for line in combined_output.split('\n'):
        line = line.strip()
        if not line:
            continue

        match = re.match(pattern, line, re.IGNORECASE)
        if match:
            severity = match.group(1).lower()
            file_ref = match.group(2) or filename
            line_num = int(match.group(3)) if match.group(3) else None
            column = int(match.group(4)) if match.group(4) else None
            message = match.group(5).strip()

            error_dict = {
                "file": file_ref,
                "line": line_num,
                "column": column,
                "message": message,
                "severity": severity,
                "rule": None,  # CMF doesn't always provide rule IDs
                "context": None
            }

            if severity == "error":
                errors.append(error_dict)
            elif severity == "warning":
                warnings.append(error_dict)

    # If no structured errors found but output exists, create a generic error
    # But skip if output indicates success (e.g., "No errors found", "Validation successful")
    if not errors and not warnings and combined_output.strip():
        output_lower = combined_output.lower()
        # Check for actual error indicators, but exclude success messages
        has_error_indicator = (
            "[error]" in output_lower or
            ("error" in output_lower and "no error" not in output_lower)
        )
        # Don't create error if output indicates success
        is_success = any(phrase in output_lower for phrase in [
            "validation successful", "no errors", "successful"
        ])

        if has_error_indicator and not is_success:
            errors.append({
                "file": filename,
                "line": None,
                "column": None,
                "message": combined_output.strip()[:500],  # Limit message length
                "severity": "error",
                "rule": None,
                "context": None
            })

    return {
        "errors": errors,
        "warnings": warnings,
        "has_errors": len(errors) > 0
    }


def _validate_cmf_command(cmd: list) -> None:
    """
    Validate CMF command arguments against allowlist to prevent command injection.

    This enforces a strict allowlist policy:
    1. First argument must be a valid CMF subcommand
    2. Flags must be in the allowed flags list
    3. File paths must not contain path traversal sequences

    Args:
        cmd: Command arguments to validate

    Raises:
        CMFError: If command contains disallowed arguments or suspicious patterns

    Security:
        This function is critical for preventing command injection attacks.
        All user-controlled input to run_cmf_command() must pass through this validation.
    """
    if not cmd or len(cmd) == 0:
        raise CMFError("Command cannot be empty")

    # Security: First argument must be a valid CMF subcommand from allowlist
    subcommand = cmd[0]
    if subcommand not in ALLOWED_CMF_COMMANDS:
        raise CMFError(f"Invalid CMF subcommand: {subcommand}. Allowed: {', '.join(ALLOWED_CMF_COMMANDS)}")

    # Security: Validate remaining arguments
    i = 1
    while i < len(cmd):
        arg = cmd[i]

        if not isinstance(arg, str):
            raise CMFError(f"All command arguments must be strings, got {type(arg)}")

        # Check if it's a flag
        if arg.startswith("-"):
            if arg not in ALLOWED_CMF_FLAGS:
                raise CMFError(f"Invalid CMF flag: {arg}. Allowed: {', '.join(ALLOWED_CMF_FLAGS)}")
        else:
            # It's a file path or value - validate it
            # Security: Reject absolute paths (they should be relative to working_dir)
            if arg.startswith("/"):
                raise CMFError(f"Absolute paths not allowed in command arguments: {arg}")

            # Security: Reject path traversal sequences
            if ".." in arg:
                raise CMFError(f"Path traversal sequences not allowed: {arg}")

            # Security: Basic filename validation - must end with expected extensions or be simple values
            # Allow: filenames, relative paths within working dir
            # Reject: shell metacharacters
            dangerous_chars = [";", "|", "&", "$", "`", "(", ")", "<", ">", "\n", "\r"]
            for char in dangerous_chars:
                if char in arg:
                    raise CMFError(f"Dangerous character '{char}' found in argument: {arg}")

        i += 1


def run_cmf_command(
    cmd: list,
    timeout: int = CMF_TIMEOUT,
    working_dir: str | None = None
) -> dict[str, Any]:
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
        # Security: Validate command against allowlist to prevent command injection
        _validate_cmf_command(cmd)

        # Build command: Run platform-specific script directly
        # Windows uses cmftool.bat, Unix/Mac uses cmftool shell script
        # Both are executable and don't require 'sh' wrapper
        full_cmd = [CMF_TOOL_PATH] + cmd
        logger.info(f"Running CMF command: {' '.join(full_cmd)}")

        # Set working directory with security validation
        if working_dir is None:
            working_dir = Path(CMF_TOOL_PATH).parent.parent
        else:
            # Security: Resolve and validate working directory
            working_dir_path = Path(working_dir).resolve()

            # Ensure working directory exists and is a directory
            if not working_dir_path.exists():
                raise CMFError(f"Working directory does not exist: {working_dir_path}")
            if not working_dir_path.is_dir():
                raise CMFError(f"Working directory is not a directory: {working_dir_path}")

            # Security: Ensure working directory is within /tmp or /app (expected safe zones)
            # nosec B108 - Intentional hardcoded path for security validation
            allowed_prefixes = [Path("/tmp").resolve(), Path("/app").resolve()]
            if os.getenv("HOME"):
                allowed_prefixes.append(Path(os.getenv("HOME")).resolve())

            is_safe = any(
                str(working_dir_path).startswith(str(prefix))
                for prefix in allowed_prefixes
            )

            if not is_safe:
                logger.error(f"Working directory outside allowed paths: {working_dir_path}")
                raise CMFError(f"Working directory not in allowed locations: {working_dir_path}")

            working_dir = str(working_dir_path)

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
    except subprocess.TimeoutExpired as e:
        logger.error(f"CMF command timed out after {timeout} seconds")
        raise CMFError(f"Operation timed out after {timeout} seconds") from e
    except Exception as e:
        logger.error(f"CMF command execution failed: {e}")
        raise CMFError(f"Command execution failed: {e}") from e
