#!/usr/bin/env python3
"""
Simplified Senzing Initialization Script

Ensures Senzing SQLite configuration exists on API startup.
"""

import os
import logging
import sys
from pathlib import Path

logger = logging.getLogger(__name__)


def initialize_senzing():
    """
    Simplified Senzing initialization - ensures SQLite configuration exists.

    Returns:
        True if Senzing is available, False otherwise
    """
    logger.info("Checking Senzing configuration...")

    # Check license
    license_path = Path(os.getenv("SENZING_LICENSE_PATH", "/app/secrets/senzing/g2.lic"))
    if not license_path.exists():
        # Try local development path
        license_path = Path("./api/secrets/senzing/g2.lic")

    if license_path.exists():
        logger.info(f"✓ Senzing license found at {license_path}")
    else:
        logger.info("✗ No Senzing license - using text-based entity matching")
        return False

    # Setup SQLite configuration
    try:
        # Import configuration helper
        sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "config"))
        from senzing_simple_config import ensure_sqlite_setup

        config = ensure_sqlite_setup()
        logger.info(f"✓ Senzing SQLite configured at {config['db_path']}")
        return True

    except Exception as e:
        logger.warning(f"Failed to setup Senzing configuration: {e}")
        logger.info("Will use text-based entity matching as fallback")
        return False


if __name__ == "__main__":
    # Run initialization when script is executed
    senzing_available = initialize_senzing()
    sys.exit(0 if senzing_available else 1)