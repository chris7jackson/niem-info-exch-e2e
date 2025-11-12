"""Unit tests for settings API endpoints."""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, Mock

from niem_api.main import app
from niem_api.models.models import Settings
from tests.fixtures.settings_fixtures import create_settings_object


@pytest.mark.unit
class TestSettingsEndpoints:
    """Test suite for settings API endpoints."""

    @pytest.fixture
    def client(self):
        """Create test client for FastAPI app."""
        return TestClient(app)

    @pytest.fixture
    def mock_settings_service(self):
        """Create a mock SettingsService."""
        mock = Mock()
        mock.get_settings.return_value = create_settings_object(skip_xml=False, skip_json=False)
        mock.update_settings.return_value = create_settings_object(skip_xml=True, skip_json=True)
        return mock

    def test_get_settings_endpoint_returns_settings(self, client):
        """Test GET /api/settings returns current settings."""
        # Arrange
        expected_settings = create_settings_object(skip_xml=True, skip_json=False)

        with patch("niem_api.main.get_neo4j_client") as mock_get_client, \
             patch("niem_api.main.SettingsService") as mock_service_class:

            mock_service = Mock()
            mock_service.get_settings.return_value = expected_settings
            mock_service_class.return_value = mock_service

            # Act
            response = client.get("/api/settings")

            # Assert
            assert response.status_code == 200
            data = response.json()
            assert data["skip_xml_validation"] is True
            assert data["skip_json_validation"] is False
            mock_service.get_settings.assert_called_once()

    def test_update_settings_endpoint_updates_and_returns_settings(self, client):
        """Test PUT /api/settings updates and returns settings."""
        # Arrange
        updated_settings = create_settings_object(skip_xml=True, skip_json=True)

        with patch("niem_api.main.get_neo4j_client") as mock_get_client, \
             patch("niem_api.main.SettingsService") as mock_service_class:

            mock_service = Mock()
            mock_service.update_settings.return_value = updated_settings
            mock_service_class.return_value = mock_service

            # Act
            payload = {"skip_xml_validation": True, "skip_json_validation": True}
            response = client.put("/api/settings", json=payload)

            # Assert
            assert response.status_code == 200
            data = response.json()
            assert data["skip_xml_validation"] is True
            assert data["skip_json_validation"] is True
            mock_service.update_settings.assert_called_once()

            # Verify the service was called with correct Settings object
            call_args = mock_service.update_settings.call_args[0][0]
            assert isinstance(call_args, Settings)
            assert call_args.skip_xml_validation is True
            assert call_args.skip_json_validation is True

    def test_update_settings_validates_input(self, client):
        """Test PUT /api/settings validates input data."""
        # Arrange - Invalid payload (missing required field)
        invalid_payload = {"skip_xml_validation": True}  # Missing skip_json_validation

        # Act
        response = client.put("/api/settings", json=invalid_payload)

        # Assert
        assert response.status_code == 422  # Validation error

    def test_update_settings_rejects_invalid_types(self, client):
        """Test PUT /api/settings rejects invalid data types."""
        # Arrange - Invalid types (strings instead of booleans)
        invalid_payload = {
            "skip_xml_validation": "true",  # String instead of boolean
            "skip_json_validation": "false",
        }

        # Act
        response = client.put("/api/settings", json=invalid_payload)

        # Assert
        assert response.status_code == 422  # Validation error

    def test_get_settings_handles_service_defaults(self, client):
        """Test GET /api/settings returns defaults when service has no data."""
        # Arrange
        default_settings = create_settings_object(skip_xml=False, skip_json=False)

        with patch("niem_api.main.get_neo4j_client") as mock_get_client, \
             patch("niem_api.main.SettingsService") as mock_service_class:

            mock_service = Mock()
            mock_service.get_settings.return_value = default_settings
            mock_service_class.return_value = mock_service

            # Act
            response = client.get("/api/settings")

            # Assert
            assert response.status_code == 200
            data = response.json()
            assert data["skip_xml_validation"] is False
            assert data["skip_json_validation"] is False
