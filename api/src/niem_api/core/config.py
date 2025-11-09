#!/usr/bin/env python3
"""
Configuration settings for batch processing and Senzing entity resolution.

These settings can be overridden via environment variables to adjust
resource limits based on deployment environment (local dev vs production).
"""

import base64
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)


class BatchConfig:
    """Batch processing configuration with operation-specific limits.

    All values can be overridden via environment variables.
    Default values are conservative for local Docker development.

    For production deployments with more resources, increase these limits
    via environment variables in docker-compose.yml or deployment config.
    """

    # Concurrency: Max parallel operations across the system
    # Lower = safer for local dev, Higher = faster for production
    MAX_CONCURRENT_OPERATIONS = int(os.getenv("BATCH_MAX_CONCURRENT_OPERATIONS", "3"))

    # Timeout: Max seconds per individual file operation
    OPERATION_TIMEOUT = int(os.getenv("BATCH_OPERATION_TIMEOUT", "60"))

    # Operation-specific batch size limits
    # Schema uploads often have 25+ XSD files (NIEM references)
    MAX_SCHEMA_FILES = int(os.getenv("BATCH_MAX_SCHEMA_FILES", "50"))

    # XML/JSON conversions typically smaller batches
    MAX_CONVERSION_FILES = int(os.getenv("BATCH_MAX_CONVERSION_FILES", "20"))

    # XML/JSON ingestion to Neo4j
    MAX_INGEST_FILES = int(os.getenv("BATCH_MAX_INGEST_FILES", "20"))

    # JSON validation feature flag
    # Default: true (validation skipped)
    #
    # Reasons for default=true:
    # 1. CMF tool cannot generate JSON schemas for NIEM < 6.0 (e.g., NIECE 3.0, NIBRS 5.0)
    # 2. JSON schemas from model.xsd don't validate message instances correctly
    # 3. Model schema validation cycle is separate from message validation
    #
    # Set to 'false' only if you have NIEM 6.0+ schemas AND valid message schemas
    SKIP_JSON_VALIDATION = os.getenv("SKIP_JSON_VALIDATION", "true").lower() == "true"

    @classmethod
    def get_batch_limit(cls, operation_type: str) -> int:
        """Get batch size limit for specific operation type.

        Args:
            operation_type: One of 'schema', 'conversion', 'ingest'

        Returns:
            Maximum files allowed for this operation
        """
        limits = {
            "schema": cls.MAX_SCHEMA_FILES,
            "conversion": cls.MAX_CONVERSION_FILES,
            "ingest": cls.MAX_INGEST_FILES,
        }
        return limits.get(operation_type, 10)  # Default fallback


# Singleton instance
batch_config = BatchConfig()


class SenzingConfig:
    """Senzing entity resolution configuration.

    Manages Senzing license file location and automatic base64 decoding.
    The license can be provided in two ways:
    1. Pre-decoded: api/secrets/senzing/g2.lic (preferred for production)
    2. Base64 encoded: api/g2license_*/g2.lic_base64 (auto-decoded on startup)
    """

    # License file paths
    LICENSE_PATH = Path(os.getenv("SENZING_LICENSE_PATH", "/app/secrets/senzing/g2.lic"))
    LICENSE_SEARCH_PATTERN = "/app/licenses/g2license_*"  # Pattern to find license folders

    # Senzing data directory
    DATA_DIR = Path(os.getenv("SENZING_DATA_DIR", "/data/senzing"))

    # Target node labels for entity resolution (NIEM Person/Organization entities)
    TARGET_LABELS = [
        "nc:Person",
        "nc:Organization",
        "j:CrashDriver",
        "j:CrashPerson",
    ]

    @classmethod
    def ensure_license(cls) -> bool:
        """Ensure Senzing license file exists, auto-decoding if needed.

        Returns:
            True if license is available, False otherwise
        """
        # Check if decoded license already exists
        if cls.LICENSE_PATH.exists():
            logger.info(f"✅ Senzing license found at {cls.LICENSE_PATH}")
            return True

        # Try to find and decode base64 license from any g2license_* folder
        import glob

        license_dirs = glob.glob(cls.LICENSE_SEARCH_PATTERN)

        if not license_dirs:
            logger.warning(
                f"⚠️ Senzing license not found. Entity resolution features disabled.\n"
                f"   Expected at: {cls.LICENSE_PATH}\n"
                f"   Or base64 at: api/g2license_*/g2.lic_base64 on host\n"
                f"   To obtain a license, contact support@senzing.com"
            )
            return False

        # Search all license folders for base64 files
        base64_files = []
        for license_dir in sorted(license_dirs, reverse=True):  # Most recent first
            base64_files.extend(Path(license_dir).glob("*.lic_base64"))

        if not base64_files:
            logger.warning(
                f"⚠️ License folders found but no .lic_base64 files: {license_dirs}\n"
                f"   Expected: g2.lic_base64 inside the license folder"
            )
            return False

        # Use the first base64 file found (from most recent folder)
        base64_path = base64_files[0]

        try:
            logger.info(f"Decoding Senzing license from {base64_path}")

            # Create target directory
            cls.LICENSE_PATH.parent.mkdir(parents=True, exist_ok=True)

            # Read and decode
            with open(base64_path, "r") as f:
                encoded = f.read().strip()

            decoded = base64.b64decode(encoded)

            # Write decoded license
            with open(cls.LICENSE_PATH, "wb") as f:
                f.write(decoded)

            logger.info(f"✅ Senzing license decoded successfully to {cls.LICENSE_PATH}")
            return True

        except Exception as e:
            logger.error(f"❌ Failed to decode Senzing license from {base64_path}: {e}")
            return False

    @classmethod
    def is_available(cls) -> bool:
        """Check if Senzing license is available.

        Returns:
            True if license file exists
        """
        return cls.LICENSE_PATH.exists()


# Singleton instance
senzing_config = SenzingConfig()
