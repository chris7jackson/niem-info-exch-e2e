#!/usr/bin/env python3
"""
Utility functions for reading environment variables with cross-platform support.

Handles Windows CRLF line endings and other whitespace issues that can occur
when .env files are edited on different operating systems.
"""

import os
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


def getenv_clean(key: str, default: str = None, strip: bool = True) -> Optional[str]:
    """Get environment variable with automatic cleaning of line endings and whitespace.

    This function handles common issues with .env files:
    - Windows CRLF line endings (\r\n)
    - Unix LF line endings (\n)
    - Trailing/leading whitespace
    - Carriage returns (\r)

    Args:
        key: Environment variable name
        default: Default value if variable is not set
        strip: If True, strip whitespace and line endings (default: True)

    Returns:
        Cleaned environment variable value, or default if not set

    Example:
        >>> # .env file has: SKIP_JSON_VALIDATION=true\r\n
        >>> value = getenv_clean("SKIP_JSON_VALIDATION", "false")
        >>> # Returns: "true" (without \r\n)
    """
    raw_value = os.getenv(key, default)
    
    if raw_value is None:
        return None
    
    if not strip:
        return raw_value
    
    # Clean the value: strip whitespace and remove line endings
    cleaned = raw_value.strip().rstrip("\r\n")
    
    # Log warning if cleaning changed the value (indicates line ending issues)
    if raw_value != cleaned:
        logger.warning(
            f"Environment variable {key} had trailing whitespace/line endings: "
            f"raw={repr(raw_value)}, cleaned={repr(cleaned)}"
        )
    
    return cleaned


def getenv_bool(key: str, default: bool = False) -> bool:
    """Get environment variable as boolean with automatic cleaning.

    Handles line endings and converts string values to boolean:
    - "true", "True", "TRUE", "1", "yes", "Yes" → True
    - "false", "False", "FALSE", "0", "no", "No" → False
    - Empty string or None → default value

    Args:
        key: Environment variable name
        default: Default boolean value if variable is not set

    Returns:
        Boolean value

    Example:
        >>> # .env file has: SKIP_JSON_VALIDATION=true\r\n
        >>> value = getenv_bool("SKIP_JSON_VALIDATION", False)
        >>> # Returns: True (cleaned and converted)
    """
    raw_value = getenv_clean(key, None)
    
    if raw_value is None:
        return default
    
    # Convert to boolean
    cleaned_lower = raw_value.lower()
    if cleaned_lower in ("true", "1", "yes", "on"):
        return True
    elif cleaned_lower in ("false", "0", "no", "off", ""):
        return False
    else:
        logger.warning(
            f"Environment variable {key} has unexpected boolean value: {repr(raw_value)}. "
            f"Using default: {default}"
        )
        return default


def getenv_int(key: str, default: int) -> int:
    """Get environment variable as integer with automatic cleaning.

    Args:
        key: Environment variable name
        default: Default integer value if variable is not set or invalid

    Returns:
        Integer value

    Example:
        >>> # .env file has: MAX_FILES=10\r\n
        >>> value = getenv_int("MAX_FILES", 5)
        >>> # Returns: 10 (cleaned and converted)
    """
    raw_value = getenv_clean(key, None)
    
    if raw_value is None:
        return default
    
    try:
        return int(raw_value)
    except ValueError:
        logger.warning(
            f"Environment variable {key} is not a valid integer: {repr(raw_value)}. "
            f"Using default: {default}"
        )
        return default


def getenv_list(key: str, default: list[str] = None, separator: str = ",") -> list[str]:
    """Get environment variable as list with automatic cleaning.

    Splits the value by separator and cleans each item.

    Args:
        key: Environment variable name
        default: Default list value if variable is not set
        separator: Separator character (default: ",")

    Returns:
        List of cleaned strings

    Example:
        >>> # .env file has: CORS_ORIGINS=http://localhost:3000,http://localhost:8080\r\n
        >>> value = getenv_list("CORS_ORIGINS", ["http://localhost:3000"])
        >>> # Returns: ["http://localhost:3000", "http://localhost:8080"]
    """
    if default is None:
        default = []
    
    raw_value = getenv_clean(key, None)
    
    if raw_value is None or raw_value == "":
        return default
    
    # Split and clean each item
    items = [item.strip() for item in raw_value.split(separator) if item.strip()]
    return items if items else default

