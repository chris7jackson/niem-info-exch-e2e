#!/usr/bin/env python3
"""
PostgreSQL Settings Service

Manages application settings stored in PostgreSQL.
Provides get/update operations with defaults for missing settings.
"""

import logging
from typing import Any

from ..clients.postgres_client import PostgresClient
from ..models.models import Settings

logger = logging.getLogger(__name__)


class PostgresSettingsService:
    """
    Service for managing application settings in PostgreSQL.

    Settings are stored in the app_settings table.
    If no settings exist, default values are used.
    """

    def __init__(self, postgres_client: PostgresClient):
        """
        Initialize settings service.

        Args:
            postgres_client: PostgreSQL client for database operations
        """
        self.postgres_client = postgres_client
        self._ensure_table_exists()

    def _ensure_table_exists(self) -> None:
        """
        Create the app_settings table if it doesn't exist.

        Table schema:
        - id: Primary key (always 'default')
        - skip_xml_validation: Boolean flag
        - skip_json_validation: Boolean flag
        - created_at: Timestamp
        - updated_at: Timestamp
        """
        create_table_query = """
        CREATE TABLE IF NOT EXISTS app_settings (
            id VARCHAR(50) PRIMARY KEY DEFAULT 'default',
            skip_xml_validation BOOLEAN DEFAULT FALSE,
            skip_json_validation BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """

        try:
            self.postgres_client.execute(create_table_query)
            logger.info("Ensured app_settings table exists")
        except Exception as e:
            logger.error(f"Error creating app_settings table: {e}")
            raise

    def get_settings(self) -> Settings:
        """
        Retrieve current application settings.

        Returns default settings if none exist in the database.

        Returns:
            Settings object with current configuration
        """
        query = """
        SELECT skip_xml_validation, skip_json_validation
        FROM app_settings
        WHERE id = %(id)s
        """

        try:
            result = self.postgres_client.execute_one(query, {"id": "default"})

            if result:
                # Settings exist in database
                return Settings(
                    skip_xml_validation=result.get("skip_xml_validation", False),
                    skip_json_validation=result.get("skip_json_validation", False),
                )
            else:
                # No settings in database, return defaults and initialize
                logger.info("No settings found in database, using defaults")
                default_settings = Settings()
                self.initialize_settings()
                return default_settings

        except Exception as e:
            logger.error(f"Error retrieving settings: {e}")
            logger.info("Returning default settings due to error")
            return Settings()

    def update_settings(self, settings: Settings) -> Settings:
        """
        Update application settings in the database.

        Creates settings row if it doesn't exist (INSERT ... ON CONFLICT).

        Args:
            settings: Settings object with new configuration

        Returns:
            Updated Settings object
        """
        query = """
        INSERT INTO app_settings (id, skip_xml_validation, skip_json_validation, created_at, updated_at)
        VALUES (%(id)s, %(skip_xml_validation)s, %(skip_json_validation)s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        ON CONFLICT (id)
        DO UPDATE SET
            skip_xml_validation = EXCLUDED.skip_xml_validation,
            skip_json_validation = EXCLUDED.skip_json_validation,
            updated_at = CURRENT_TIMESTAMP
        """

        try:
            self.postgres_client.execute(
                query,
                {
                    "id": "default",
                    "skip_xml_validation": settings.skip_xml_validation,
                    "skip_json_validation": settings.skip_json_validation,
                },
            )

            logger.info(
                f"Settings updated: skip_xml_validation={settings.skip_xml_validation}, "
                f"skip_json_validation={settings.skip_json_validation}"
            )

            return settings

        except Exception as e:
            logger.error(f"Error updating settings: {e}")
            raise

    def initialize_settings(self) -> None:
        """
        Initialize settings in database if they don't exist.

        Creates settings row with default values on first run.
        Safe to call multiple times (uses INSERT ... ON CONFLICT DO NOTHING).
        """
        query = """
        INSERT INTO app_settings (id, skip_xml_validation, skip_json_validation, created_at, updated_at)
        VALUES (%(id)s, %(skip_xml_validation)s, %(skip_json_validation)s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        ON CONFLICT (id) DO NOTHING
        """

        try:
            default_settings = Settings()
            self.postgres_client.execute(
                query,
                {
                    "id": "default",
                    "skip_xml_validation": default_settings.skip_xml_validation,
                    "skip_json_validation": default_settings.skip_json_validation,
                },
            )
            logger.info("Settings initialized in database")

        except Exception as e:
            logger.error(f"Error initializing settings: {e}")
            # Don't raise - app can still work with default settings
