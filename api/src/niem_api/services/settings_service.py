#!/usr/bin/env python3
"""
Settings Service

Manages application settings stored in Neo4j.
Provides get/update operations with defaults for missing settings.
"""

import logging
from typing import Any

from ..clients.neo4j_client import Neo4jClient
from ..models.models import Settings

logger = logging.getLogger(__name__)


class SettingsService:
    """
    Service for managing application settings in Neo4j.

    Settings are stored as a single Settings node in the database.
    If no settings exist, default values are used.
    """

    SETTINGS_NODE_ID = "app_settings"  # Constant ID for the single settings node

    def __init__(self, neo4j_client: Neo4jClient):
        """
        Initialize settings service.

        Args:
            neo4j_client: Neo4j client for database operations
        """
        self.neo4j_client = neo4j_client

    def get_settings(self) -> Settings:
        """
        Retrieve current application settings.

        Returns default settings if none exist in the database.

        Returns:
            Settings object with current configuration
        """
        query = """
        MATCH (s:Settings {id: $id})
        RETURN s.skip_xml_validation AS skip_xml_validation,
               s.skip_json_validation AS skip_json_validation
        """

        try:
            results = self.neo4j_client.query(query, {"id": self.SETTINGS_NODE_ID})

            if results:
                # Settings exist in database
                result = results[0]
                return Settings(
                    skip_xml_validation=result.get("skip_xml_validation", False),
                    skip_json_validation=result.get("skip_json_validation", False),
                )
            else:
                # No settings in database, return defaults
                logger.info("No settings found in database, using defaults")
                return Settings()

        except Exception as e:
            logger.error(f"Error retrieving settings: {e}")
            logger.info("Returning default settings due to error")
            return Settings()

    def update_settings(self, settings: Settings) -> Settings:
        """
        Update application settings in the database.

        Creates settings node if it doesn't exist (MERGE pattern).

        Args:
            settings: Settings object with new configuration

        Returns:
            Updated Settings object
        """
        query = """
        MERGE (s:Settings {id: $id})
        SET s.skip_xml_validation = $skip_xml_validation,
            s.skip_json_validation = $skip_json_validation,
            s.updated_at = datetime()
        RETURN s.skip_xml_validation AS skip_xml_validation,
               s.skip_json_validation AS skip_json_validation
        """

        try:
            results = self.neo4j_client.query(
                query,
                {
                    "id": self.SETTINGS_NODE_ID,
                    "skip_xml_validation": settings.skip_xml_validation,
                    "skip_json_validation": settings.skip_json_validation,
                },
            )

            logger.info(f"Settings updated: skip_xml_validation={settings.skip_xml_validation}, skip_json_validation={settings.skip_json_validation}")

            return settings

        except Exception as e:
            logger.error(f"Error updating settings: {e}")
            raise

    def initialize_settings(self) -> None:
        """
        Initialize settings in database if they don't exist.

        Creates settings node with default values on first run.
        Safe to call multiple times (uses MERGE).
        """
        query = """
        MERGE (s:Settings {id: $id})
        ON CREATE SET
            s.skip_xml_validation = $skip_xml_validation,
            s.skip_json_validation = $skip_json_validation,
            s.created_at = datetime(),
            s.updated_at = datetime()
        """

        try:
            default_settings = Settings()
            self.neo4j_client.query(
                query,
                {
                    "id": self.SETTINGS_NODE_ID,
                    "skip_xml_validation": default_settings.skip_xml_validation,
                    "skip_json_validation": default_settings.skip_json_validation,
                },
            )
            logger.info("Settings initialized in database")

        except Exception as e:
            logger.error(f"Error initializing settings: {e}")
            # Don't raise - app can still work with default settings
