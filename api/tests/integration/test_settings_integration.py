"""Integration tests for settings feature with real Neo4j."""

import pytest

from niem_api.clients.neo4j_client import Neo4jClient
from niem_api.services.settings_service import SettingsService
from niem_api.models.models import Settings
from tests.fixtures.settings_fixtures import create_settings_object


@pytest.mark.integration
class TestSettingsIntegration:
    """Integration tests for settings persistence in Neo4j."""

    @pytest.fixture
    def neo4j_client(self):
        """Create a real Neo4j client for integration testing."""
        client = Neo4jClient()
        yield client
        # Cleanup - remove test settings node after each test
        try:
            client.query(
                "MATCH (s:Settings {id: $id}) DELETE s",
                {"id": SettingsService.SETTINGS_NODE_ID},
            )
        except Exception:
            pass  # Ignore cleanup errors
        finally:
            client.driver.close()

    @pytest.fixture
    def settings_service(self, neo4j_client):
        """Create SettingsService with real Neo4j client."""
        return SettingsService(neo4j_client)

    def test_settings_roundtrip(self, settings_service):
        """Test complete roundtrip: create, read, update, read."""
        # Step 1: Initialize with defaults
        settings_service.initialize_settings()

        # Step 2: Read initial settings (should be defaults)
        initial_settings = settings_service.get_settings()
        assert initial_settings.skip_xml_validation is False
        assert initial_settings.skip_json_validation is False

        # Step 3: Update settings
        new_settings = create_settings_object(skip_xml=True, skip_json=True)
        updated = settings_service.update_settings(new_settings)
        assert updated.skip_xml_validation is True
        assert updated.skip_json_validation is True

        # Step 4: Read again to verify persistence
        retrieved_settings = settings_service.get_settings()
        assert retrieved_settings.skip_xml_validation is True
        assert retrieved_settings.skip_json_validation is True

    def test_settings_persist_across_service_instances(self, neo4j_client):
        """Test settings persist when creating new service instances."""
        # Step 1: Create first service instance and save settings
        service1 = SettingsService(neo4j_client)
        service1.initialize_settings()
        settings1 = create_settings_object(skip_xml=True, skip_json=False)
        service1.update_settings(settings1)

        # Step 2: Create second service instance and retrieve settings
        service2 = SettingsService(neo4j_client)
        settings2 = service2.get_settings()

        # Assert: Settings should match what was saved by first instance
        assert settings2.skip_xml_validation is True
        assert settings2.skip_json_validation is False

    def test_initialize_settings_is_truly_idempotent(self, settings_service):
        """Test multiple initialize calls don't create duplicate nodes."""
        # Initialize multiple times
        settings_service.initialize_settings()
        settings_service.initialize_settings()
        settings_service.initialize_settings()

        # Query to count Settings nodes
        result = settings_service.neo4j_client.query(
            "MATCH (s:Settings {id: $id}) RETURN count(s) as count",
            {"id": SettingsService.SETTINGS_NODE_ID},
        )

        # Assert: Only one settings node should exist
        assert result[0]["count"] == 1

    def test_update_creates_node_if_missing(self, settings_service, neo4j_client):
        """Test update_settings creates node via MERGE if it doesn't exist."""
        # Ensure no settings node exists (cleanup fixture should have removed it)
        result = neo4j_client.query(
            "MATCH (s:Settings {id: $id}) RETURN count(s) as count",
            {"id": SettingsService.SETTINGS_NODE_ID},
        )
        assert result[0]["count"] == 0

        # Update settings without initializing first
        new_settings = create_settings_object(skip_xml=True, skip_json=True)
        settings_service.update_settings(new_settings)

        # Verify node was created
        result = neo4j_client.query(
            "MATCH (s:Settings {id: $id}) RETURN count(s) as count",
            {"id": SettingsService.SETTINGS_NODE_ID},
        )
        assert result[0]["count"] == 1

        # Verify values are correct
        retrieved = settings_service.get_settings()
        assert retrieved.skip_xml_validation is True
        assert retrieved.skip_json_validation is True

    def test_settings_update_preserves_node_identity(self, settings_service, neo4j_client):
        """Test updating settings doesn't create duplicate nodes."""
        # Initialize and get initial node ID
        settings_service.initialize_settings()

        # Update settings multiple times
        for i in range(3):
            settings = create_settings_object(
                skip_xml=(i % 2 == 0), skip_json=(i % 2 != 0)
            )
            settings_service.update_settings(settings)

        # Verify only one node exists
        result = neo4j_client.query(
            "MATCH (s:Settings {id: $id}) RETURN count(s) as count",
            {"id": SettingsService.SETTINGS_NODE_ID},
        )
        assert result[0]["count"] == 1

    def test_concurrent_updates_dont_create_duplicates(self, neo4j_client):
        """Test concurrent service instances don't create duplicate settings."""
        # Create multiple service instances
        services = [SettingsService(neo4j_client) for _ in range(3)]

        # Each service updates settings
        for i, service in enumerate(services):
            settings = create_settings_object(skip_xml=(i == 0), skip_json=(i == 1))
            service.update_settings(settings)

        # Verify only one settings node exists
        result = neo4j_client.query(
            "MATCH (s:Settings {id: $id}) RETURN count(s) as count",
            {"id": SettingsService.SETTINGS_NODE_ID},
        )
        assert result[0]["count"] == 1
