#!/usr/bin/env python3
"""
Senzing Default Configuration Generator

Creates default Senzing configuration files with SQLite database
if custom configuration is not provided. This allows the system to
work out of the box for development and testing.
"""

import json
import os
import logging
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger(__name__)


def ensure_senzing_directories() -> Dict[str, Path]:
    """
    Create necessary directories for Senzing if they don't exist.

    Returns:
        Dictionary of directory paths
    """
    # Base data directory
    data_dir = Path(os.getenv("SENZING_DATA_DIR", "/data/senzing"))

    # Create subdirectories
    directories = {
        "data": data_dir,
        "db": data_dir / "db",
        "resources": data_dir / "resources",
        "temp": data_dir / "temp",
        "export": data_dir / "export"
    }

    for name, path in directories.items():
        path.mkdir(parents=True, exist_ok=True)
        logger.debug(f"Ensured directory exists: {path}")

    return directories


def generate_default_g2_ini(output_path: Optional[str] = None) -> str:
    """
    Generate default g2.ini configuration with SQLite database.

    Args:
        output_path: Optional path to write the configuration file

    Returns:
        Path to the generated configuration file
    """
    dirs = ensure_senzing_directories()

    # Default SQLite database path
    db_path = dirs["db"] / "g2.db"

    # Configuration content
    config_content = f"""# Senzing G2 Configuration
# Auto-generated default configuration with SQLite database
# For production, replace with PostgreSQL or MySQL configuration

[PIPELINE]
CONFIGPATH={dirs["data"]}/config/
RESOURCEPATH={dirs["resources"]}/
SUPPORTPATH={dirs["data"]}/

[SQL]
# SQLite configuration (default for development/testing)
CONNECTION=sqlite3://na:na@{db_path}

# PostgreSQL configuration (uncomment for production)
# CONNECTION=postgresql://senzing:senzing@postgres:5432/g2

# MySQL configuration (uncomment if preferred)
# CONNECTION=mysql://senzing:senzing@mysql:3306/g2

[HYBRID]
# Hybrid configuration for better performance (optional)
# NOTE: Update SSPASSWORD with actual credentials for production
SSHOSTNAME=localhost
SSPORT=8250
SSUSER=root
SSPASSWORD={os.getenv('SENZING_HYBRID_PASSWORD', 'changeme')}
"""

    # Determine output path
    if output_path is None:
        output_path = dirs["data"] / "config" / "g2.ini"
        output_path.parent.mkdir(parents=True, exist_ok=True)
    else:
        output_path = Path(output_path)

    # Write configuration file
    output_path.write_text(config_content)
    logger.info(f"Generated default g2.ini configuration at {output_path}")

    return str(output_path)


def generate_default_g2_config_json(output_path: Optional[str] = None) -> str:
    """
    Generate default g2config.json for NIEM entity resolution.

    Args:
        output_path: Optional path to write the configuration file

    Returns:
        Path to the generated configuration file
    """
    dirs = ensure_senzing_directories()

    # Default configuration for NIEM entities
    config = {
        "G2_CONFIG": {
            "CFG_VERSION": "3",
            "CFG_ETYPE": [
                {
                    "ETYPE_ID": 1,
                    "ETYPE_CODE": "PERSON",
                    "ETYPE_DESC": "Person entities from NIEM graph"
                },
                {
                    "ETYPE_ID": 2,
                    "ETYPE_CODE": "ORGANIZATION",
                    "ETYPE_DESC": "Organization entities from NIEM graph"
                }
            ],
            "CFG_DSRC": [
                {
                    "DSRC_ID": 1,
                    "DSRC_CODE": "NIEM_GRAPH",
                    "DSRC_DESC": "NIEM GraphRAG Neo4j data source"
                }
            ],
            "CFG_FTYPE": [
                {
                    "FTYPE_ID": 1,
                    "FTYPE_CODE": "NAME",
                    "FTYPE_DESC": "Name features for matching"
                },
                {
                    "FTYPE_ID": 2,
                    "FTYPE_CODE": "DOB",
                    "FTYPE_DESC": "Date of birth for matching"
                },
                {
                    "FTYPE_ID": 3,
                    "FTYPE_CODE": "SSN",
                    "FTYPE_DESC": "Social Security Number"
                },
                {
                    "FTYPE_ID": 4,
                    "FTYPE_CODE": "ADDRESS",
                    "FTYPE_DESC": "Address for matching"
                }
            ]
        }
    }

    # Determine output path
    if output_path is None:
        output_path = dirs["data"] / "config" / "g2config.json"
        output_path.parent.mkdir(parents=True, exist_ok=True)
    else:
        output_path = Path(output_path)

    # Write configuration file
    output_path.write_text(json.dumps(config, indent=2))
    logger.info(f"Generated default g2config.json at {output_path}")

    return str(output_path)


def get_or_create_default_config() -> Dict[str, str]:
    """
    Get existing configuration or create default configuration files.

    Returns:
        Dictionary with paths to configuration files
    """
    config_dir = Path(os.getenv("SENZING_CONFIG_PATH", "/app/config"))
    data_dir = Path(os.getenv("SENZING_DATA_DIR", "/data/senzing"))

    # Check for existing configuration
    g2_ini_path = config_dir / "g2.ini"
    g2_config_path = config_dir / "g2config.json"

    # Use data directory config if app config doesn't exist
    if not g2_ini_path.exists():
        g2_ini_path = data_dir / "config" / "g2.ini"
    if not g2_config_path.exists():
        g2_config_path = data_dir / "config" / "g2config.json"

    paths = {}

    # Generate g2.ini if it doesn't exist
    if not g2_ini_path.exists():
        logger.info("No g2.ini found, generating default SQLite configuration")
        paths["g2_ini"] = generate_default_g2_ini(str(g2_ini_path))
    else:
        logger.info(f"Using existing g2.ini from {g2_ini_path}")
        paths["g2_ini"] = str(g2_ini_path)

    # Generate g2config.json if it doesn't exist
    if not g2_config_path.exists():
        logger.info("No g2config.json found, generating default configuration")
        paths["g2_config"] = generate_default_g2_config_json(str(g2_config_path))
    else:
        logger.info(f"Using existing g2config.json from {g2_config_path}")
        paths["g2_config"] = str(g2_config_path)

    return paths


def initialize_sqlite_database(db_path: str) -> bool:
    """
    Initialize SQLite database with Senzing schema if needed.

    Args:
        db_path: Path to SQLite database file

    Returns:
        True if successful, False otherwise
    """
    import sqlite3
    from pathlib import Path

    try:
        # Ensure directory exists
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)

        # Connect to database (creates if doesn't exist)
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Create basic tables if they don't exist
        # Note: Actual Senzing schema is much more complex
        # This is a simplified version for initial setup
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS SYS_CFG (
                CONFIG_ID INTEGER PRIMARY KEY,
                CONFIG_JSON TEXT,
                CREATED_AT TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS DSRC_RECORD (
                DSRC_ID INTEGER,
                RECORD_ID TEXT,
                JSON_DATA TEXT,
                CREATED_AT TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (DSRC_ID, RECORD_ID)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS RES_ENTITY (
                RES_ENT_ID INTEGER PRIMARY KEY AUTOINCREMENT,
                ENTITY_ID INTEGER,
                ENTITY_NAME TEXT,
                CREATED_AT TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.commit()
        conn.close()

        logger.info(f"Initialized SQLite database at {db_path}")
        return True

    except Exception as e:
        logger.error(f"Failed to initialize SQLite database: {e}")
        return False


# Auto-configuration on import
if __name__ == "__main__":
    # Run configuration when module is executed directly
    config_paths = get_or_create_default_config()
    print("Senzing configuration files:")
    for name, path in config_paths.items():
        print(f"  {name}: {path}")