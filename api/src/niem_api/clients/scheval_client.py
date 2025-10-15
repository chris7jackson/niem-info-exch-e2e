#!/usr/bin/env python3
"""
NIEM Schematron Evaluation (SCHEval) Tool Client

A low-level client wrapper for the NIEM Schematron evaluation command-line tool.
Handles tool detection, command execution, and output parsing for schematron validation.

This client is pure infrastructure - it contains no business logic.
For schematron validation business operations, use the services/domain/schema/scheval_validator.py module.
"""

import json
import logging
import os
import re
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)

# Scheval tool configuration
# Check for environment variable first, then fall back to default path
_SCHEVAL_PATH_ENV = os.getenv("SCHEVAL_TOOL_PATH")

if _SCHEVAL_PATH_ENV:
    # Use environment variable if set
    SCHEVAL_TOOL_PATH = _SCHEVAL_PATH_ENV
    logger.debug(f"Using SCHEVAL_TOOL_PATH from environment: {SCHEVAL_TOOL_PATH}")
else:
    # Default: Go up 4 levels from clients/scheval_client.py to get to api/ directory
    # File is at: api/src/niem_api/clients/scheval_client.py -> need 4 .parent to reach api/
    _SCHEVAL_DEFAULT_PATH = Path(__file__).parent.parent.parent.parent / "third_party/niem-scheval/scheval-1.0/bin/scheval"

    if _SCHEVAL_DEFAULT_PATH.exists():
        SCHEVAL_TOOL_PATH = str(_SCHEVAL_DEFAULT_PATH)
        logger.debug(f"Using default scheval tool path: {SCHEVAL_TOOL_PATH}")
    else:
        SCHEVAL_TOOL_PATH = None
        logger.warning("Scheval tool not found at default path and SCHEVAL_TOOL_PATH not set")

SCHEVAL_TIMEOUT = 60  # Default command timeout in seconds (schematron can be slow)

# Security: Allowlist of valid scheval tool flags
# No subcommands for scheval - it's a single-purpose tool
# Only these flags are allowed in command arguments
ALLOWED_SCHEVAL_FLAGS = {
    "-s", "--schema",       # Apply rules from this schematron file
    "-x", "--xslt",         # Apply rules from this compiled schematron file
    "-o", "--output",       # Write output to this file
    "--svrl",               # Write output in SVRL format
    "--compile",            # Compile schema and write output in XSLT format
    "-c", "--catalog",      # Provide this XML catalog file as $xml-catalog parameter
    "-k", "--keep",         # Keep temporary files
    "-d", "--debug",        # Turn on debug logging
    "-h", "--help",         # Display usage message
}


class SchevalError(Exception):
    """
    Exception raised when scheval tool operations fail.

    Used for:
    - Tool not found/unavailable
    - Command execution failures
    - Timeout errors
    - Invalid responses
    """
    pass


def is_scheval_available() -> bool:
    """
    Check if scheval tool is available and executable.

    Returns:
        True if scheval tool binary exists and can be executed, False otherwise

    Example:
        ```python
        if is_scheval_available():
            result = run_scheval_command(["-s", "rules.sch", "input.xml"])
        else:
            print("Scheval tool not installed")
        ```

    Note:
        This only checks file existence, not actual executability or Java runtime.
        For full verification, try running a simple command like `get_scheval_version()`.
    """
    if not SCHEVAL_TOOL_PATH:
        return False

    scheval_path = Path(SCHEVAL_TOOL_PATH)
    exists = scheval_path.exists() and scheval_path.is_file()

    if exists:
        logger.debug(f"Scheval tool found at: {SCHEVAL_TOOL_PATH}")
    else:
        logger.debug(f"Scheval tool not found at: {SCHEVAL_TOOL_PATH}")

    return exists


def get_scheval_version() -> str:
    """
    Get the version of the installed scheval tool.

    Returns:
        Version string (e.g., "1.0")

    Raises:
        SchevalError: If scheval tool is not available or version check fails

    Example:
        ```python
        try:
            version = get_scheval_version()
            print(f"Using scheval tool version: {version}")
        except SchevalError as e:
            print(f"Scheval tool error: {e}")
        ```
    """
    if not is_scheval_available():
        raise SchevalError("Scheval tool not available")

    try:
        # Scheval doesn't have a version command, so we'll extract from --help
        result = run_scheval_command(["--help"], timeout=5)
        if result["returncode"] == 0:
            # Try to extract version from help output
            # Look for "version X.X" pattern
            version_match = re.search(r'version\s+([\d.]+)', result["stdout"], re.IGNORECASE)
            if version_match:
                return version_match.group(1)
            # Look for "Schematron Evaluation (SCHEval) tool, version X.X" pattern
            version_match = re.search(r'SCHEval[^\d]*([\d.]+)', result["stdout"], re.IGNORECASE)
            if version_match:
                return version_match.group(1)
            # Default to 1.0 if we can't extract version
            return "1.0"
        else:
            raise SchevalError(f"Version check failed: {result['stderr']}")
    except Exception as e:
        logger.error(f"Failed to get scheval version: {e}")
        raise SchevalError(f"Failed to get scheval version: {str(e)}")


async def download_and_setup_scheval() -> bool:
    """
    Check if scheval tool is available at expected mount points.

    This is called during application startup to verify scheval tool availability.
    In the current architecture, the scheval tool is pre-installed and mounted into
    the container, so this just validates the mount.

    Returns:
        True if scheval tool is available, False otherwise

    Note:
        This function is async for consistency with other startup tasks,
        but the actual check is synchronous.
    """
    if is_scheval_available():
        logger.info(f"Scheval tool available at mounted path: {SCHEVAL_TOOL_PATH}")
        return True
    else:
        logger.warning(f"Scheval tool not found at expected path: {SCHEVAL_TOOL_PATH}")
        return False


def parse_scheval_validation_output(stdout: str, stderr: str, filename: str) -> Dict[str, Any]:
    """
    Parse scheval validation output into structured error information.

    The scheval tool outputs validation errors with line/column numbers in a structured format:
        WARN  file.xsd:20:55 -- Rule 7-10: Message here
        ERROR file.xsd:42:15 -- Rule 9-5: Another message

    This function extracts those into structured ValidationError objects.

    Args:
        stdout: Standard output from scheval command
        stderr: Standard error from scheval command
        filename: File being validated (for context)

    Returns:
        Dictionary with:
        - errors: List of error dictionaries with file, line, column, message, severity, rule
        - warnings: List of warning dictionaries with file, line, column, message, severity, rule
        - info: List of info dictionaries
        - has_errors: Boolean indicating if errors were found

    Example scheval output line:
        WARN  7-10.xsd:20:55 -- Rule 7-10: A Property object having an AbstractIndicator...
        ERROR example.xsd:42:15 -- Rule 9-5: Invalid attribute usage
    """
    errors: List[Dict[str, Any]] = []
    warnings: List[Dict[str, Any]] = []
    info: List[Dict[str, Any]] = []

    # Combine stdout and stderr for parsing
    combined_output = (stdout or "") + "\n" + (stderr or "")

    # Pattern to match scheval output lines
    # Format: SEVERITY  filename:line:column -- Rule ID: message
    # Or: SEVERITY  filename:line:column -- message (without Rule ID)
    pattern = r'^(WARN|ERROR|INFO)\s+([^:]+):(\d+):(\d+)\s+--\s+(.+)$'

    for line in combined_output.split('\n'):
        line = line.strip()
        if not line:
            continue

        match = re.match(pattern, line, re.IGNORECASE)
        if match:
            severity = match.group(1).lower()
            file_ref = match.group(2)
            line_num = int(match.group(3))
            column = int(match.group(4))
            full_message = match.group(5).strip()

            # Extract rule ID if present (e.g., "Rule 7-10: Message" -> rule="Rule 7-10", message="Message")
            rule = None
            message = full_message
            rule_match = re.match(r'Rule\s+([\d-]+):\s+(.+)', full_message)
            if rule_match:
                rule = f"Rule {rule_match.group(1)}"
                message = rule_match.group(2).strip()

            error_dict = {
                "file": file_ref,
                "line": line_num,
                "column": column,
                "message": message,
                "severity": severity,
                "rule": rule,
                "context": None
            }

            if severity == "error":
                errors.append(error_dict)
            elif severity == "warn":
                warnings.append(error_dict)
            elif severity == "info":
                info.append(error_dict)

    # If no structured errors found but output exists, check for Java errors or exceptions
    if not errors and not warnings and combined_output.strip():
        # Check for Java exceptions or fatal errors
        if any(keyword in combined_output for keyword in ["Exception", "Error:", "FATAL", "error"]):
            # Create a generic error for Java exceptions or tool errors
            errors.append({
                "file": filename,
                "line": None,
                "column": None,
                "message": combined_output.strip()[:500],  # Limit message length
                "severity": "error",
                "rule": None,
                "context": "Tool execution error"
            })

    return {
        "errors": errors,
        "warnings": warnings,
        "info": info,
        "has_errors": len(errors) > 0
    }


def _validate_scheval_command(args: list) -> None:
    """
    Validate scheval command arguments against allowlist to prevent command injection.

    This enforces a strict allowlist policy:
    1. Flags must be in the allowed flags list
    2. File paths must not contain path traversal sequences
    3. No shell metacharacters allowed

    Args:
        args: Command arguments to validate (without the scheval binary itself)

    Raises:
        SchevalError: If command contains disallowed arguments or suspicious patterns

    Security:
        This function is critical for preventing command injection attacks.
        All user-controlled input to run_scheval_command() must pass through this validation.
    """
    if not args:
        raise SchevalError("Command arguments cannot be empty")

    # Security: Validate all arguments
    i = 0
    while i < len(args):
        arg = args[i]

        if not isinstance(arg, str):
            raise SchevalError(f"All command arguments must be strings, got {type(arg)}")

        # Check if it's a flag
        if arg.startswith("-"):
            if arg not in ALLOWED_SCHEVAL_FLAGS:
                raise SchevalError(f"Invalid scheval flag: {arg}. Allowed: {', '.join(ALLOWED_SCHEVAL_FLAGS)}")
        else:
            # It's a file path or value - validate it
            # Security: If it's an absolute path, ensure it's within allowed directories
            if arg.startswith("/"):
                from pathlib import Path as P
                arg_path = P(arg).resolve()
                allowed_prefixes = [P("/tmp").resolve(), P("/app").resolve()]
                if os.getenv("HOME"):
                    allowed_prefixes.append(P(os.getenv("HOME")).resolve())

                is_safe = any(
                    str(arg_path).startswith(str(prefix))
                    for prefix in allowed_prefixes
                )
                if not is_safe:
                    raise SchevalError(f"Absolute path outside allowed directories (/app, /tmp, $HOME): {arg}")

            # Security: Reject path traversal sequences
            if ".." in arg:
                raise SchevalError(f"Path traversal sequences not allowed: {arg}")

            # Security: Basic filename validation
            # Reject shell metacharacters
            dangerous_chars = [";", "|", "&", "$", "`", "(", ")", "<", ">", "\n", "\r", "\\"]
            for char in dangerous_chars:
                if char in arg:
                    raise SchevalError(f"Dangerous character '{char}' found in argument: {arg}")

        i += 1


def run_scheval_command(
    args: list,
    timeout: int = SCHEVAL_TIMEOUT,
    working_dir: Optional[str] = None
) -> Dict[str, Any]:
    """
    Execute a scheval command with timeout and safety checks.

    This is the core execution primitive for all scheval operations.
    Handles process management, timeouts, and error capture.

    Args:
        args: Command arguments to pass to scheval (e.g., ["-s", "rules.sch", "input.xml"])
        timeout: Maximum execution time in seconds (default: 60)
        working_dir: Working directory for command execution. If None, uses scheval tool's parent directory.

    Returns:
        Dictionary with keys:
        - returncode: Process exit code (int)
        - stdout: Standard output (str)
        - stderr: Standard error (str)

    Raises:
        SchevalError: If scheval tool is unavailable, command times out, or execution fails

    Example:
        ```python
        # Validate XML with schematron rules
        result = run_scheval_command([
            "-s", "niem-ndr-rules.sch",
            "-c", "catalog.xml",
            "schema.xsd"
        ], timeout=120)

        if result["returncode"] == 0:
            parsed = parse_scheval_validation_output(result["stdout"], result["stderr"], "schema.xsd")
            if not parsed["has_errors"]:
                print("Validation successful")
        else:
            print(f"Validation failed: {result['stderr']}")
        ```

    Note:
        - Command output is captured (not streamed)
        - Working directory defaults to scheval tool installation directory
        - Subprocess runs in text mode (UTF-8 encoding)
        - Scheval can be slow for large schemas - adjust timeout accordingly
    """
    if not SCHEVAL_TOOL_PATH:
        raise SchevalError("Scheval tool not available. Please ensure it's properly installed.")

    try:
        # Security: Validate command against allowlist to prevent command injection
        _validate_scheval_command(args)

        # Use 'sh' to invoke scheval for cross-platform compatibility (Windows mounts)
        full_cmd = ["sh", SCHEVAL_TOOL_PATH] + args
        logger.info(f"Running scheval command: {' '.join(full_cmd)}")

        # Set working directory with security validation
        if working_dir is None:
            working_dir = Path(SCHEVAL_TOOL_PATH).parent.parent
        else:
            # Security: Resolve and validate working directory
            working_dir_path = Path(working_dir).resolve()

            # Ensure working directory exists and is a directory
            if not working_dir_path.exists():
                raise SchevalError(f"Working directory does not exist: {working_dir_path}")
            if not working_dir_path.is_dir():
                raise SchevalError(f"Working directory is not a directory: {working_dir_path}")

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
                raise SchevalError(f"Working directory not in allowed locations: {working_dir_path}")

            working_dir = str(working_dir_path)

        result = subprocess.run(
            full_cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=working_dir
        )

        logger.debug(f"Scheval command result: returncode={result.returncode}")
        if result.stdout:
            logger.debug(f"Scheval stdout: {result.stdout}")
        if result.stderr:
            logger.debug(f"Scheval stderr: {result.stderr}")

        return {
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr
        }
    except subprocess.TimeoutExpired:
        logger.error(f"Scheval command timed out after {timeout} seconds")
        raise SchevalError(f"Operation timed out after {timeout} seconds")
    except Exception as e:
        logger.error(f"Scheval command execution failed: {e}")
        raise SchevalError(f"Command execution failed: {e}")
