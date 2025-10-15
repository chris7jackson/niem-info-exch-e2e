#!/usr/bin/env python3
"""
NIEM Message Translation (NIEMTran) Tool Client

A low-level client wrapper for the NIEM Message Translation command-line tool.
Handles tool detection, command execution, and basic availability checks.

This client is pure infrastructure - it contains no business logic.
For NIEMTran-related business operations (XML to JSON conversion),
use the services/niemtran_service.py module.
"""

import logging
import os
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

# NIEMTran tool configuration
# Check for environment variable first, then fall back to default path
_NIEMTRAN_PATH_ENV = os.getenv("NIEMTRAN_TOOL_PATH")

if _NIEMTRAN_PATH_ENV:
    # Use environment variable if set
    NIEMTRAN_TOOL_PATH = _NIEMTRAN_PATH_ENV
    logger.debug(f"Using NIEMTRAN_TOOL_PATH from environment: {NIEMTRAN_TOOL_PATH}")
else:
    # Default: Go up 4 levels from clients/niemtran_client.py to get to api/ directory
    # File is at: api/src/niem_api/clients/niemtran_client.py -> need 4 .parent to reach api/
    _NIEMTRAN_DEFAULT_PATH = Path(__file__).parent.parent.parent.parent / "third_party/niem-tran/niemtran-1.0/bin/niemtran"

    if _NIEMTRAN_DEFAULT_PATH.exists():
        NIEMTRAN_TOOL_PATH = str(_NIEMTRAN_DEFAULT_PATH)
        logger.debug(f"Using default NIEMTran tool path: {NIEMTRAN_TOOL_PATH}")
    else:
        NIEMTRAN_TOOL_PATH = None
        logger.warning("NIEMTran tool not found at default path and NIEMTRAN_TOOL_PATH not set")

NIEMTRAN_TIMEOUT = 60  # Default command timeout in seconds

# Security: Allowlist of valid NIEMTran tool subcommands
# Only these commands can be executed via run_niemtran_command()
ALLOWED_NIEMTRAN_COMMANDS = {
    "x2j",      # XML to JSON conversion
    "version",  # Get NIEMTran tool version
    "help",     # Help command
}

# Security: Allowlist of valid NIEMTran tool flags
# Only these flags are allowed in command arguments
ALLOWED_NIEMTRAN_FLAGS = {
    "-c", "--context",      # Generate complete @context in result
    "--curi",               # Include "@context:" URI pair in result
    "-f", "--force",        # Overwrite existing .json files
    "-h", "--help",         # Help flag
    "-v", "--version",      # Version flag
}


class NIEMTranError(Exception):
    """
    Exception raised when NIEMTran tool operations fail.

    Used for:
    - Tool not found/unavailable
    - Command execution failures
    - Timeout errors
    - Invalid responses
    """
    pass


def is_niemtran_available() -> bool:
    """
    Check if NIEMTran tool is available and executable.

    Returns:
        True if NIEMTran tool binary exists and can be executed, False otherwise

    Example:
        ```python
        if is_niemtran_available():
            result = run_niemtran_command(["x2j", "--help"])
        else:
            print("NIEMTran tool not installed")
        ```

    Note:
        This only checks file existence, not actual executability or Java runtime.
        For full verification, try running a simple command like `get_niemtran_version()`.
    """
    if not NIEMTRAN_TOOL_PATH:
        return False

    niemtran_path = Path(NIEMTRAN_TOOL_PATH)
    exists = niemtran_path.exists() and niemtran_path.is_file()

    if exists:
        logger.debug(f"NIEMTran tool found at: {NIEMTRAN_TOOL_PATH}")
    else:
        logger.debug(f"NIEMTran tool not found at: {NIEMTRAN_TOOL_PATH}")

    return exists


def get_niemtran_version() -> str:
    """
    Get the version of the installed NIEMTran tool.

    Returns:
        Version string (e.g., "1.0")

    Raises:
        NIEMTranError: If NIEMTran tool is not available or version command fails

    Example:
        ```python
        try:
            version = get_niemtran_version()
            print(f"Using NIEMTran tool version: {version}")
        except NIEMTranError as e:
            print(f"NIEMTran tool error: {e}")
        ```
    """
    if not is_niemtran_available():
        raise NIEMTranError("NIEMTran tool not available")

    try:
        result = run_niemtran_command(["version"], timeout=5)
        if result["returncode"] == 0:
            # Extract version from output
            version = result["stdout"].strip()
            return version if version else "unknown"
        else:
            raise NIEMTranError(f"Version check failed: {result['stderr']}")
    except Exception as e:
        logger.error(f"Failed to get NIEMTran version: {e}")
        raise NIEMTranError(f"Failed to get NIEMTran version: {str(e)}")


async def download_and_setup_niemtran() -> bool:
    """
    Check if NIEMTran tool is available at expected mount points.

    This is called during application startup to verify NIEMTran tool availability.
    In the current architecture, the NIEMTran tool is pre-installed and mounted into
    the container, so this just validates the mount.

    Returns:
        True if NIEMTran tool is available, False otherwise

    Note:
        This function is async for consistency with other startup tasks,
        but the actual check is synchronous.
    """
    if is_niemtran_available():
        logger.info(f"NIEMTran tool available at mounted path: {NIEMTRAN_TOOL_PATH}")
        return True
    else:
        logger.warning(f"NIEMTran tool not found at expected path: {NIEMTRAN_TOOL_PATH}")
        return False


def _validate_niemtran_command(cmd: list) -> None:
    """
    Validate NIEMTran command arguments against allowlist to prevent command injection.

    This enforces a strict allowlist policy:
    1. First argument must be a valid NIEMTran subcommand
    2. Flags must be in the allowed flags list
    3. File paths must not contain path traversal sequences

    Args:
        cmd: Command arguments to validate

    Raises:
        NIEMTranError: If command contains disallowed arguments or suspicious patterns

    Security:
        This function is critical for preventing command injection attacks.
        All user-controlled input to run_niemtran_command() must pass through this validation.
    """
    if not cmd or len(cmd) == 0:
        raise NIEMTranError("Command cannot be empty")

    # Security: First argument must be a valid NIEMTran subcommand from allowlist
    subcommand = cmd[0]
    if subcommand not in ALLOWED_NIEMTRAN_COMMANDS:
        raise NIEMTranError(f"Invalid NIEMTran subcommand: {subcommand}. Allowed: {', '.join(ALLOWED_NIEMTRAN_COMMANDS)}")

    # Security: Validate remaining arguments
    i = 1
    while i < len(cmd):
        arg = cmd[i]

        if not isinstance(arg, str):
            raise NIEMTranError(f"All command arguments must be strings, got {type(arg)}")

        # Check if it's a flag
        if arg.startswith("-"):
            if arg not in ALLOWED_NIEMTRAN_FLAGS:
                raise NIEMTranError(f"Invalid NIEMTran flag: {arg}. Allowed: {', '.join(ALLOWED_NIEMTRAN_FLAGS)}")
        else:
            # It's a file path or value - validate it
            # Security: Reject absolute paths (they should be relative to working_dir)
            if arg.startswith("/"):
                raise NIEMTranError(f"Absolute paths not allowed in command arguments: {arg}")

            # Security: Reject path traversal sequences
            if ".." in arg:
                raise NIEMTranError(f"Path traversal sequences not allowed: {arg}")

            # Security: Basic filename validation - must end with expected extensions or be simple values
            # Allow: filenames, relative paths within working dir
            # Reject: shell metacharacters
            dangerous_chars = [";", "|", "&", "$", "`", "(", ")", "<", ">", "\n", "\r"]
            for char in dangerous_chars:
                if char in arg:
                    raise NIEMTranError(f"Dangerous character '{char}' found in argument: {arg}")

        i += 1


def run_niemtran_command(
    cmd: list,
    timeout: int = NIEMTRAN_TIMEOUT,
    working_dir: Optional[str] = None
) -> Dict[str, Any]:
    """
    Execute a NIEMTran tool command with timeout and safety checks.

    This is the core execution primitive for all NIEMTran operations.
    Handles process management, timeouts, and error capture.

    Args:
        cmd: Command arguments to pass to NIEMTran tool (e.g., ["x2j", "model.cmf", "message.xml"])
        timeout: Maximum execution time in seconds (default: 60)
        working_dir: Working directory for command execution. If None, uses NIEMTran tool's parent directory.

    Returns:
        Dictionary with keys:
        - returncode: Process exit code (int)
        - stdout: Standard output (str)
        - stderr: Standard error (str)

    Raises:
        NIEMTranError: If NIEMTran tool is unavailable, command times out, or execution fails

    Example:
        ```python
        # Convert XML to JSON
        result = run_niemtran_command([
            "x2j",
            "model.cmf",
            "message.xml"
        ], timeout=60)

        if result["returncode"] == 0:
            print("Conversion successful")
        else:
            print(f"Conversion failed: {result['stderr']}")
        ```

    Note:
        - Command output is captured (not streamed)
        - Working directory defaults to NIEMTran tool installation directory
        - Subprocess runs in text mode (UTF-8 encoding)
    """
    if not NIEMTRAN_TOOL_PATH:
        raise NIEMTranError("NIEMTran tool not available. Please ensure it's properly installed.")

    try:
        # Security: Validate command against allowlist to prevent command injection
        _validate_niemtran_command(cmd)

        # Use 'sh' to invoke niemtran for cross-platform compatibility (Windows mounts)
        full_cmd = ["sh", NIEMTRAN_TOOL_PATH] + cmd
        logger.info(f"Running NIEMTran command: {' '.join(full_cmd)}")

        # Set working directory with security validation
        if working_dir is None:
            working_dir = Path(NIEMTRAN_TOOL_PATH).parent.parent
        else:
            # Security: Resolve and validate working directory
            working_dir_path = Path(working_dir).resolve()

            # Ensure working directory exists and is a directory
            if not working_dir_path.exists():
                raise NIEMTranError(f"Working directory does not exist: {working_dir_path}")
            if not working_dir_path.is_dir():
                raise NIEMTranError(f"Working directory is not a directory: {working_dir_path}")

            # Security: Ensure working directory is within /tmp or /app (expected safe zones)
            allowed_prefixes = [Path("/tmp").resolve(), Path("/app").resolve()]
            if os.getenv("HOME"):
                allowed_prefixes.append(Path(os.getenv("HOME")).resolve())

            is_safe = any(
                str(working_dir_path).startswith(str(prefix))
                for prefix in allowed_prefixes
            )

            if not is_safe:
                logger.error(f"Working directory outside allowed paths: {working_dir_path}")
                raise NIEMTranError(f"Working directory not in allowed locations: {working_dir_path}")

            working_dir = str(working_dir_path)

        result = subprocess.run(
            full_cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=working_dir
        )

        logger.debug(f"NIEMTran command result: returncode={result.returncode}")
        if result.stdout:
            logger.debug(f"NIEMTran stdout: {result.stdout}")
        if result.stderr:
            logger.debug(f"NIEMTran stderr: {result.stderr}")

        return {
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr
        }
    except subprocess.TimeoutExpired:
        logger.error(f"NIEMTran command timed out after {timeout} seconds")
        raise NIEMTranError(f"Operation timed out after {timeout} seconds")
    except Exception as e:
        logger.error(f"NIEMTran command execution failed: {e}")
        raise NIEMTranError(f"Command execution failed: {e}")
