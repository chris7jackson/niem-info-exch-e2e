#!/usr/bin/env python3
"""
Unit tests for Senzing gRPC client.

Tests the SenzingClient class with mocked gRPC communication.

Run with: pytest api/tests/unit/clients/test_senzing_client.py -v
"""

import json
import pytest
from unittest.mock import Mock, patch, MagicMock
from niem_api.clients.senzing_client import SenzingClient, SENZING_AVAILABLE


@pytest.fixture
def mock_grpc_channel():
    """Create mock gRPC channel."""
    return Mock()


@pytest.fixture
def mock_factory(mock_grpc_channel):
    """Create mock Senzing factory."""
    factory = Mock()
    factory.create_engine = Mock(return_value=Mock())
    factory.create_configmanager = Mock(return_value=Mock())
    factory.create_diagnostic = Mock(return_value=Mock())
    factory.destroy = Mock()
    return factory


@pytest.mark.skipif(not SENZING_AVAILABLE, reason="Senzing not installed")
class TestSenzingClientInitialization:
    """Test Senzing client initialization."""

    @patch('niem_api.clients.senzing_client.SzAbstractFactory')
    @patch('niem_api.clients.senzing_client.grpc')
    def test_initialize_success(self, mock_grpc, mock_factory_class, mock_factory):
        """Test successful initialization."""
        # Setup mocks
        mock_grpc.insecure_channel = Mock(return_value=Mock())
        mock_factory_class.return_value = mock_factory

        with patch.dict('os.environ', {'SENZING_GRPC_URL': 'localhost:8261'}):
            client = SenzingClient()

            # Mock is_available to return True
            with patch.object(client, 'is_available', return_value=True):
                result = client.initialize()

                assert result is True
                assert client.initialized is True
                assert client.factory is not None
                assert client.engine is not None

    def test_initialize_without_senzing_available(self):
        """Test initialization when Senzing is not available."""
        client = SenzingClient()

        with patch.object(client, 'is_available', return_value=False):
            result = client.initialize()

            assert result is False
            assert client.initialized is False

    @patch('niem_api.clients.senzing_client.grpc')
    def test_initialize_connection_failure(self, mock_grpc):
        """Test handling of gRPC connection failure."""
        # Simulate connection error
        mock_grpc.insecure_channel.side_effect = Exception("Connection failed")

        client = SenzingClient()

        with patch.object(client, 'is_available', return_value=True):
            result = client.initialize()

            assert result is False
            assert client.initialized is False


class TestSenzingClientOperations:
    """Test Senzing client record operations."""

    @pytest.fixture
    def initialized_client(self, mock_factory):
        """Create an initialized Senzing client."""
        client = SenzingClient()
        client.factory = mock_factory
        client.engine = Mock()
        client.initialized = True
        return client

    def test_add_record_success(self, initialized_client):
        """Test adding a record successfully."""
        initialized_client.engine.add_record = Mock()

        record_json = '{"NAME_FULL": "Test Person"}'
        result = initialized_client.add_record("TEST_SOURCE", "REC_001", record_json)

        assert result is True
        initialized_client.engine.add_record.assert_called_once_with(
            "TEST_SOURCE", "REC_001", record_json
        )

    def test_add_record_not_initialized(self):
        """Test adding record when client not initialized."""
        client = SenzingClient()
        client.initialized = False

        result = client.add_record("TEST", "001", "{}")

        assert result is False

    def test_add_record_error(self, initialized_client):
        """Test handling of add_record error."""
        initialized_client.engine.add_record.side_effect = Exception("Add failed")

        result = initialized_client.add_record("TEST", "001", "{}")

        assert result is False

    def test_get_entity_by_record_id_success(self, initialized_client):
        """Test retrieving entity successfully."""
        mock_response = {
            'RESOLVED_ENTITY': {
                'ENTITY_ID': 123,
                'ENTITY_NAME': 'Test Person',
                'RECORDS': [{'RECORD_ID': '001'}]
            }
        }

        initialized_client.engine.get_entity_by_record_id = Mock(
            return_value=json.dumps(mock_response)
        )

        result = initialized_client.get_entity_by_record_id("TEST_SOURCE", "001")

        assert result is not None
        assert result['RESOLVED_ENTITY']['ENTITY_ID'] == 123
        assert result['RESOLVED_ENTITY']['ENTITY_NAME'] == 'Test Person'

    def test_get_entity_not_found(self, initialized_client):
        """Test handling when entity not found."""
        initialized_client.engine.get_entity_by_record_id.side_effect = Exception("Not found")

        result = initialized_client.get_entity_by_record_id("TEST", "999")

        assert result is None

    def test_delete_record_success(self, initialized_client):
        """Test deleting a record."""
        initialized_client.engine.delete_record = Mock()

        result = initialized_client.delete_record("TEST_SOURCE", "REC_001")

        assert result is True
        initialized_client.engine.delete_record.assert_called_once()

    def test_purge_repository(self, initialized_client):
        """Test purging the repository."""
        initialized_client.engine.purge_repository = Mock()

        result = initialized_client.purge_repository()

        assert result is True
        initialized_client.engine.purge_repository.assert_called_once()


class TestSenzingClientBatch:
    """Test batch processing."""

    @pytest.fixture
    def initialized_client(self, mock_factory):
        """Create initialized client."""
        client = SenzingClient()
        client.factory = mock_factory
        client.engine = Mock()
        client.initialized = True
        client.add_record = Mock(side_effect=[True, True, False])  # 2 success, 1 fail
        return client

    def test_process_batch(self, initialized_client):
        """Test batch processing with mixed results."""
        records = [
            ("SOURCE", "ID1", '{"name": "Person 1"}'),
            ("SOURCE", "ID2", '{"name": "Person 2"}'),
            ("SOURCE", "ID3", '{"name": "Person 3"}')
        ]

        result = initialized_client.process_batch(records)

        assert result['processed'] == 2
        assert result['failed'] == 1
        assert len(result['errors']) == 1

    def test_process_empty_batch(self, initialized_client):
        """Test processing empty batch."""
        result = initialized_client.process_batch([])

        assert result['processed'] == 0
        assert result['failed'] == 0


class TestSenzingClientCleanup:
    """Test resource cleanup."""

    def test_close_destroys_factory(self, mock_factory):
        """Test that close() destroys the factory."""
        client = SenzingClient()
        client.factory = mock_factory
        client.initialized = True

        client.close()

        mock_factory.destroy.assert_called_once()
        assert client.factory is None
        assert client.initialized is False

    def test_close_handles_destroy_error(self, mock_factory):
        """Test that close() handles destroy errors gracefully."""
        mock_factory.destroy.side_effect = Exception("Destroy failed")

        client = SenzingClient()
        client.factory = mock_factory
        client.initialized = True

        # Should not raise exception
        client.close()

        assert client.initialized is False


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
