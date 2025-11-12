"""Unit tests for SettingsService."""

import pytest
from unittest.mock import Mock

from niem_api.services.settings_service import SettingsService
from niem_api.models.models import Settings
from tests.fixtures.settings_fixtures import (
    create_mock_neo4j_client,
    create_settings_object,
    create_neo4j_settings_response,
)


@pytest.mark.unit
class TestSettingsService:
    """Test suite for SettingsService class."""

    @pytest.fixture
    def mock_neo4j_client(self):
        """Create a mock Neo4j client."""
        return create_mock_neo4j_client()

    @pytest.fixture
    def settings_service(self, mock_neo4j_client):
        """Create SettingsService instance with mocked Neo4j client."""
        return SettingsService(mock_neo4j_client)

    def test_get_settings_returns_existing_settings(self, settings_service, mock_neo4j_client):
        """Test get_settings returns settings from database when they exist."""
        # Arrange
        expected_settings = create_neo4j_settings_response(skip_xml=True, skip_json=False)
        mock_neo4j_client.query.side_effect = None  # Clear side_effect
        mock_neo4j_client.query.return_value = expected_settings

        # Act
        result = settings_service.get_settings()

        # Assert
        assert isinstance(result, Settings)
        assert result.skip_xml_validation is True
        assert result.skip_json_validation is False
        mock_neo4j_client.query.assert_called_once()

    def test_get_settings_returns_defaults_when_not_found(self, settings_service, mock_neo4j_client):
        """Test get_settings returns default settings when none exist in database."""
        # Arrange
        mock_neo4j_client.query.side_effect = None  # Clear side_effect
        mock_neo4j_client.query.return_value = []  # Empty result = no settings

        # Act
        result = settings_service.get_settings()

        # Assert
        assert isinstance(result, Settings)
        assert result.skip_xml_validation is False  # Default value
        assert result.skip_json_validation is False  # Default value
        mock_neo4j_client.query.assert_called_once()

    def test_get_settings_returns_defaults_on_error(self, settings_service, mock_neo4j_client):
        """Test get_settings returns default settings when database error occurs."""
        # Arrange
        mock_neo4j_client.query.side_effect = Exception("Database connection failed")

        # Act
        result = settings_service.get_settings()

        # Assert
        assert isinstance(result, Settings)
        assert result.skip_xml_validation is False  # Default value
        assert result.skip_json_validation is False  # Default value

    def test_update_settings_success(self, settings_service, mock_neo4j_client):
        """Test update_settings successfully updates settings in database."""
        # Arrange
        new_settings = create_settings_object(skip_xml=True, skip_json=True)
        mock_neo4j_client.query.side_effect = None  # Clear side_effect
        mock_neo4j_client.query.return_value = create_neo4j_settings_response(
            skip_xml=True, skip_json=True
        )

        # Act
        result = settings_service.update_settings(new_settings)

        # Assert
        assert isinstance(result, Settings)
        assert result.skip_xml_validation is True
        assert result.skip_json_validation is True
        mock_neo4j_client.query.assert_called_once()

        # Verify the Cypher query was called with correct parameters
        call_args = mock_neo4j_client.query.call_args
        assert "MERGE" in call_args[0][0]  # Uses MERGE for upsert
        assert call_args[1]["skip_xml_validation"] is True
        assert call_args[1]["skip_json_validation"] is True

    def test_update_settings_raises_on_error(self, settings_service, mock_neo4j_client):
        """Test update_settings propagates database errors."""
        # Arrange
        new_settings = create_settings_object(skip_xml=False, skip_json=False)
        mock_neo4j_client.query.side_effect = Exception("Database write failed")

        # Act & Assert
        with pytest.raises(Exception) as exc_info:
            settings_service.update_settings(new_settings)

        assert "Database write failed" in str(exc_info.value)

    def test_initialize_settings_creates_default_settings(self, settings_service, mock_neo4j_client):
        """Test initialize_settings creates default settings on first run."""
        # Arrange
        mock_neo4j_client.query.side_effect = None  # Clear side_effect
        mock_neo4j_client.query.return_value = []

        # Act
        settings_service.initialize_settings()

        # Assert
        mock_neo4j_client.query.assert_called_once()

        # Verify the Cypher query uses MERGE and ON CREATE SET
        call_args = mock_neo4j_client.query.call_args
        assert "MERGE" in call_args[0][0]
        assert "ON CREATE SET" in call_args[0][0]
        assert call_args[1]["skip_xml_validation"] is False  # Default
        assert call_args[1]["skip_json_validation"] is False  # Default

    def test_initialize_settings_is_idempotent(self, settings_service, mock_neo4j_client):
        """Test initialize_settings can be called multiple times safely."""
        # Arrange
        mock_neo4j_client.query.side_effect = None  # Clear side_effect
        mock_neo4j_client.query.return_value = []

        # Act
        settings_service.initialize_settings()
        settings_service.initialize_settings()  # Call again

        # Assert
        assert mock_neo4j_client.query.call_count == 2
        # Both calls should have identical parameters (idempotent)

    def test_initialize_settings_handles_errors_gracefully(self, settings_service, mock_neo4j_client):
        """Test initialize_settings doesn't raise on database error."""
        # Arrange
        mock_neo4j_client.query.side_effect = Exception("Database unavailable")

        # Act - should not raise
        settings_service.initialize_settings()

        # Assert
        mock_neo4j_client.query.assert_called_once()

    def test_update_settings_with_mixed_values(self, settings_service, mock_neo4j_client):
        """Test update_settings with various combinations of settings."""
        # Arrange
        test_cases = [
            (True, False),
            (False, True),
            (True, True),
            (False, False),
        ]

        for skip_xml, skip_json in test_cases:
            # Reset mock and clear side_effect
            mock_neo4j_client.reset_mock()
            mock_neo4j_client.query.side_effect = None
            mock_neo4j_client.query.return_value = create_neo4j_settings_response(
                skip_xml=skip_xml, skip_json=skip_json
            )

            settings = create_settings_object(skip_xml=skip_xml, skip_json=skip_json)

            # Act
            result = settings_service.update_settings(settings)

            # Assert
            assert result.skip_xml_validation == skip_xml
            assert result.skip_json_validation == skip_json
