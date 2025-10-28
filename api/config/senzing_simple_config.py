#!/usr/bin/env python3
"""
Simplified Senzing Configuration

Creates minimal configuration for Senzing with SQLite database.
Senzing handles most configuration internally after initialization.
"""

import os
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def get_senzing_config_path() -> Path:
    """Get the path for Senzing configuration based on environment."""
    if os.path.exists('/.dockerenv'):
        # Running in Docker
        return Path(os.getenv("SENZING_DATA_DIR", "/data/senzing"))
    else:
        # Local development
        return Path(os.getenv("SENZING_DATA_DIR", "./data/senzing"))


def ensure_sqlite_setup() -> dict:
    """
    Ensure SQLite database and minimal configuration for Senzing.

    Returns:
        Dictionary with configuration paths
    """
    base_dir = get_senzing_config_path()

    # Create necessary directories
    directories = {
        "base": base_dir,
        "db": base_dir / "sqlite",
        "config": base_dir / "config",
        "resources": base_dir / "resources"
    }

    for name, path in directories.items():
        path.mkdir(parents=True, exist_ok=True)
        logger.debug(f"Ensured {name} directory: {path}")

    # SQLite database path
    db_path = directories["db"] / "g2.db"

    # Create minimal g2.ini if it doesn't exist
    ini_path = directories["config"] / "g2.ini"
    if not ini_path.exists():
        ini_content = f"""# Minimal Senzing Configuration
[PIPELINE]
CONFIGPATH={directories["config"]}/
RESOURCEPATH={directories["resources"]}/
SUPPORTPATH={base_dir}/

[SQL]
CONNECTION=sqlite3://na:na@{db_path}
"""
        ini_path.write_text(ini_content)
        logger.info(f"Created minimal g2.ini at {ini_path}")

    return {
        "g2_ini": str(ini_path),
        "db_path": str(db_path),
        "data_dir": str(base_dir)
    }


def get_ini_json_params() -> dict:
    """
    Get Senzing initialization parameters as dictionary.

    Returns:
        Dictionary of initialization parameters for Senzing
    """
    config = ensure_sqlite_setup()
    base_dir = Path(config["data_dir"])

    return {
        "PIPELINE": {
            "CONFIGPATH": str(base_dir / "config") + "/",
            "RESOURCEPATH": str(base_dir / "resources") + "/",
            "SUPPORTPATH": str(base_dir) + "/"
        },
        "SQL": {
            "CONNECTION": f"sqlite3://na:na@{config['db_path']}"
        }
    }


# Module initialization
if __name__ == "__main__":
    config = ensure_sqlite_setup()
    print("Senzing SQLite configuration:")
    for key, value in config.items():
        print(f"  {key}: {value}")