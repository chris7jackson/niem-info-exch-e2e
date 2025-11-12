"""Unit tests for validation logic integration with settings."""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from fastapi import UploadFile
from io import BytesIO

from niem_api.handlers import ingest
from niem_api.models.models import Settings
from tests.fixtures.settings_fixtures import create_settings_object


@pytest.mark.unit
class TestValidationWithSettings:
    """Test suite for validation logic integration with settings."""

    @pytest.fixture
    def mock_validate_xml(self):
        """Mock the XML validation function."""
        with patch.object(ingest, "_validate_xml_content") as mock:
            yield mock

    @pytest.fixture
    def mock_validate_json(self):
        """Mock the JSON validation function."""
        with patch.object(ingest, "_validate_json_content") as mock:
            yield mock

    @pytest.fixture
    def sample_upload_file(self):
        """Create a sample UploadFile for testing."""
        content = b'<?xml version="1.0"?><root>test</root>'
        file = UploadFile(filename="test.xml", file=BytesIO(content))
        return file

    @pytest.mark.asyncio
    async def test_xml_validation_skipped_when_flag_true(
        self, sample_upload_file, mock_validate_xml
    ):
        """Test XML validation is skipped when skip_xml_validation=True."""
        # Arrange
        settings = create_settings_object(skip_xml=True, skip_json=False)
        mapping = {"objects": [], "associations": []}
        mock_neo4j = Mock()
        mock_neo4j.query.return_value = []
        mock_s3 = Mock()
        schema_dir = "/tmp/test"
        upload_id = "test123"
        schema_id = "schema1"
        mode = "dynamic"

        # Mock Cypher generation to avoid errors
        with patch.object(ingest, "_generate_cypher_from_xml") as mock_cypher, \
             patch.object(ingest, "_execute_cypher_statements") as mock_execute, \
             patch.object(ingest, "_store_processed_files") as mock_store:

            mock_cypher.return_value = (["CREATE (n:Test)"], {"nodes": 1})
            mock_execute.return_value = 1

            # Act
            result, _ = await ingest._process_single_file(
                file=sample_upload_file,
                mapping=mapping,
                neo4j_client=mock_neo4j,
                s3=mock_s3,
                schema_dir=schema_dir,
                upload_id=upload_id,
                schema_id=schema_id,
                mode=mode,
                settings=settings,
            )

            # Assert
            mock_validate_xml.assert_not_called()  # Validation should be skipped
            assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_xml_validation_runs_when_flag_false(
        self, sample_upload_file, mock_validate_xml
    ):
        """Test XML validation runs when skip_xml_validation=False."""
        # Arrange
        settings = create_settings_object(skip_xml=False, skip_json=False)
        mapping = {"objects": [], "associations": []}
        mock_neo4j = Mock()
        mock_neo4j.query.return_value = []
        mock_s3 = Mock()
        schema_dir = "/tmp/test"
        upload_id = "test123"
        schema_id = "schema1"
        mode = "dynamic"

        # Mock Cypher generation to avoid errors
        with patch.object(ingest, "_generate_cypher_from_xml") as mock_cypher, \
             patch.object(ingest, "_execute_cypher_statements") as mock_execute, \
             patch.object(ingest, "_store_processed_files") as mock_store:

            mock_cypher.return_value = (["CREATE (n:Test)"], {"nodes": 1})
            mock_execute.return_value = 1

            # Act
            result, _ = await ingest._process_single_file(
                file=sample_upload_file,
                mapping=mapping,
                neo4j_client=mock_neo4j,
                s3=mock_s3,
                schema_dir=schema_dir,
                upload_id=upload_id,
                schema_id=schema_id,
                mode=mode,
                settings=settings,
            )

            # Assert
            mock_validate_xml.assert_called_once()  # Validation should run
            assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_json_validation_skipped_when_flag_true(self, mock_validate_json):
        """Test JSON validation is skipped when skip_json_validation=True."""
        # Arrange
        settings = create_settings_object(skip_xml=False, skip_json=True)
        json_content = '{"@context": "http://example.org", "@id": "test", "@type": "Test"}'
        json_file = UploadFile(filename="test.json", file=BytesIO(json_content.encode()))
        mapping = {"objects": [], "associations": []}
        json_schema = {"type": "object"}  # Simple schema
        mock_neo4j = Mock()
        mock_neo4j.query.return_value = []
        mock_s3 = Mock()
        upload_id = "test123"
        schema_id = "schema1"
        mode = "dynamic"

        # Mock Cypher generation to avoid errors
        with patch.object(ingest, "_generate_cypher_from_json") as mock_cypher, \
             patch.object(ingest, "_execute_cypher_statements") as mock_execute, \
             patch.object(ingest, "_store_processed_files") as mock_store:

            mock_cypher.return_value = (["CREATE (n:Test)"], {"nodes": 1})
            mock_execute.return_value = 1

            # Act
            result, _ = await ingest._process_single_json_file(
                file=json_file,
                mapping=mapping,
                json_schema=json_schema,
                neo4j_client=mock_neo4j,
                s3=mock_s3,
                upload_id=upload_id,
                schema_id=schema_id,
                mode=mode,
                settings=settings,
            )

            # Assert
            mock_validate_json.assert_not_called()  # Validation should be skipped
            assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_json_validation_runs_when_flag_false(self, mock_validate_json):
        """Test JSON validation runs when skip_json_validation=False."""
        # Arrange
        settings = create_settings_object(skip_xml=False, skip_json=False)
        json_content = '{"@context": "http://example.org", "@id": "test", "@type": "Test"}'
        json_file = UploadFile(filename="test.json", file=BytesIO(json_content.encode()))
        mapping = {"objects": [], "associations": []}
        json_schema = {"type": "object"}  # Simple schema
        mock_neo4j = Mock()
        mock_neo4j.query.return_value = []
        mock_s3 = Mock()
        upload_id = "test123"
        schema_id = "schema1"
        mode = "dynamic"

        # Mock Cypher generation to avoid errors
        with patch.object(ingest, "_generate_cypher_from_json") as mock_cypher, \
             patch.object(ingest, "_execute_cypher_statements") as mock_execute, \
             patch.object(ingest, "_store_processed_files") as mock_store:

            mock_cypher.return_value = (["CREATE (n:Test)"], {"nodes": 1})
            mock_execute.return_value = 1

            # Act
            result, _ = await ingest._process_single_json_file(
                file=json_file,
                mapping=mapping,
                json_schema=json_schema,
                neo4j_client=mock_neo4j,
                s3=mock_s3,
                upload_id=upload_id,
                schema_id=schema_id,
                mode=mode,
                settings=settings,
            )

            # Assert
            mock_validate_json.assert_called_once()  # Validation should run
            assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_json_validation_skipped_when_no_schema(self, mock_validate_json):
        """Test JSON validation is skipped when json_schema is None."""
        # Arrange
        settings = create_settings_object(skip_xml=False, skip_json=False)
        json_content = '{"@context": "http://example.org", "@id": "test"}'
        json_file = UploadFile(filename="test.json", file=BytesIO(json_content.encode()))
        mapping = {"objects": [], "associations": []}
        json_schema = None  # No schema available
        mock_neo4j = Mock()
        mock_neo4j.query.return_value = []
        mock_s3 = Mock()
        upload_id = "test123"
        schema_id = "schema1"
        mode = "dynamic"

        # Mock Cypher generation
        with patch.object(ingest, "_generate_cypher_from_json") as mock_cypher, \
             patch.object(ingest, "_execute_cypher_statements") as mock_execute, \
             patch.object(ingest, "_store_processed_files") as mock_store:

            mock_cypher.return_value = (["CREATE (n:Test)"], {"nodes": 1})
            mock_execute.return_value = 1

            # Act
            result, _ = await ingest._process_single_json_file(
                file=json_file,
                mapping=mapping,
                json_schema=json_schema,
                neo4j_client=mock_neo4j,
                s3=mock_s3,
                upload_id=upload_id,
                schema_id=schema_id,
                mode=mode,
                settings=settings,
            )

            # Assert
            mock_validate_json.assert_not_called()  # Should skip - no schema
            assert result["status"] == "success"
