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


def get_database_connection() -> str:
    """
    Get database connection string from environment or use default SQLite.

    Supports:
    - PostgreSQL: SENZING_DATABASE_URL or individual components
    - MySQL: SENZING_DATABASE_URL or individual components
    - SQLite: Default fallback
    """
    # Check for full database URL first (best practice)
    db_url = os.getenv("SENZING_DATABASE_URL")
    if db_url:
        return db_url

    # Check for database type
    db_type = os.getenv("SENZING_DB_TYPE", "sqlite").lower()

    if db_type == "postgresql" or db_type == "postgres":
        # PostgreSQL connection from environment variables
        host = os.getenv("SENZING_DB_HOST", "postgres")
        port = os.getenv("SENZING_DB_PORT", "5432")
        database = os.getenv("SENZING_DB_NAME", "g2")
        user = os.getenv("SENZING_DB_USER", "senzing")
        password = os.getenv("SENZING_DB_PASSWORD", "senzing")
        return f"postgresql://{user}:{password}@{host}:{port}/{database}"

    elif db_type == "mysql":
        # MySQL connection from environment variables
        host = os.getenv("SENZING_DB_HOST", "mysql")
        port = os.getenv("SENZING_DB_PORT", "3306")
        database = os.getenv("SENZING_DB_NAME", "g2")
        user = os.getenv("SENZING_DB_USER", "senzing")
        password = os.getenv("SENZING_DB_PASSWORD", "senzing")
        return f"mysql://{user}:{password}@{host}:{port}/{database}"

    else:
        # Default to SQLite for development/testing
        base_dir = get_senzing_config_path()
        db_dir = base_dir / "sqlite"
        db_dir.mkdir(parents=True, exist_ok=True)
        db_path = db_dir / "g2.db"
        return f"sqlite3://na:na@{db_path}"


def ensure_sqlite_setup() -> dict:
    """
    Ensure database and minimal configuration for Senzing.

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

    # Get database connection string
    connection_string = get_database_connection()

    # Extract database path if using SQLite
    db_path = None
    if "sqlite3://" in connection_string:
        if "@" in connection_string:
            db_path = connection_string.split("@")[1]

    # Create minimal g2.ini if it doesn't exist
    ini_path = directories["config"] / "g2.ini"
    if not ini_path.exists():
        # Get resource path from environment or use default
        resource_path = os.getenv("SENZING_RESOURCE_PATH", str(directories["resources"]))

        ini_content = f"""# Senzing Configuration
# All sensitive values should be set via environment variables

[PIPELINE]
CONFIGPATH={directories["config"]}/
RESOURCEPATH={resource_path}/
SUPPORTPATH={base_dir}/

[SQL]
# Connection string from environment: SENZING_DATABASE_URL
# Or individual components: SENZING_DB_TYPE, SENZING_DB_HOST, etc.
CONNECTION={connection_string}
"""
        ini_path.write_text(ini_content)
        logger.info(f"Created g2.ini at {ini_path}")
        logger.info(f"Using database: {connection_string.split('@')[0] if '@' in connection_string else connection_string}")

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

    # Get database connection from environment
    connection_string = get_database_connection()

    # Get resource path from environment
    resource_path = os.getenv("SENZING_RESOURCE_PATH", str(base_dir / "resources"))

    return {
        "PIPELINE": {
            "CONFIGPATH": str(base_dir / "config") + "/",
            "RESOURCEPATH": resource_path + "/",
            "SUPPORTPATH": str(base_dir) + "/"
        },
        "SQL": {
            "CONNECTION": connection_string
        }
    }


# Module initialization
if __name__ == "__main__":
    config = ensure_sqlite_setup()
    print("Senzing SQLite configuration:")
    for key, value in config.items():
        print(f"  {key}: {value}")