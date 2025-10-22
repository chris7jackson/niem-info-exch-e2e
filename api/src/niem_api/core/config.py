#!/usr/bin/env python3
"""
Configuration settings for batch processing operations.

These settings can be overridden via environment variables to adjust
resource limits based on deployment environment (local dev vs production).
"""

import os


class BatchConfig:
    """Batch processing configuration with operation-specific limits.

    All values can be overridden via environment variables.
    Default values are conservative for local Docker development.

    For production deployments with more resources, increase these limits
    via environment variables in docker-compose.yml or deployment config.
    """

    # Concurrency: Max parallel operations across the system
    # Lower = safer for local dev, Higher = faster for production
    MAX_CONCURRENT_OPERATIONS = int(os.getenv('BATCH_MAX_CONCURRENT_OPERATIONS', '3'))

    # Timeout: Max seconds per individual file operation
    OPERATION_TIMEOUT = int(os.getenv('BATCH_OPERATION_TIMEOUT', '60'))

    # Operation-specific batch size limits
    # Schema uploads often have 25+ XSD files (NIEM references)
    MAX_SCHEMA_FILES = int(os.getenv('BATCH_MAX_SCHEMA_FILES', '50'))

    # XML/JSON conversions typically smaller batches
    MAX_CONVERSION_FILES = int(os.getenv('BATCH_MAX_CONVERSION_FILES', '20'))

    # XML/JSON ingestion to Neo4j
    MAX_INGEST_FILES = int(os.getenv('BATCH_MAX_INGEST_FILES', '20'))

    @classmethod
    def get_batch_limit(cls, operation_type: str) -> int:
        """Get batch size limit for specific operation type.

        Args:
            operation_type: One of 'schema', 'conversion', 'ingest'

        Returns:
            Maximum files allowed for this operation
        """
        limits = {
            'schema': cls.MAX_SCHEMA_FILES,
            'conversion': cls.MAX_CONVERSION_FILES,
            'ingest': cls.MAX_INGEST_FILES,
        }
        return limits.get(operation_type, 10)  # Default fallback


# Singleton instance
batch_config = BatchConfig()
