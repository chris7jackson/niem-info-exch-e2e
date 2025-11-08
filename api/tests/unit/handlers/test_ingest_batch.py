#!/usr/bin/env python3
"""Tests for ingest handler batch processing capabilities."""

import asyncio
from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi import HTTPException, UploadFile
from minio import Minio

from niem_api.handlers.ingest import handle_json_ingest, handle_xml_ingest


class TestIngestBatchProcessing:
    """Test suite for XML/JSON ingestion batch processing."""

    @pytest.fixture
    def mock_s3_client(self):
        """Mock MinIO S3 client."""
        return Mock(spec=Minio)

    @pytest.fixture
    def create_mock_xml_files(self):
        """Factory to create mock XML upload files."""
        def _create_files(count):
            files = []
            for i in range(count):
                mock_file = Mock(spec=UploadFile)
                mock_file.filename = f"data_{i}.xml"
                mock_file.read = AsyncMock(return_value=b'<?xml version="1.0"?><data>test</data>')
                files.append(mock_file)
            return files
        return _create_files

    @pytest.fixture
    def create_mock_json_files(self):
        """Factory to create mock JSON upload files."""
        def _create_files(count):
            files = []
            for i in range(count):
                mock_file = Mock(spec=UploadFile)
                mock_file.filename = f"data_{i}.json"
                mock_file.read = AsyncMock(return_value=b'{"test": "data"}')
                files.append(mock_file)
            return files
        return _create_files

    # XML Ingestion Tests

    @pytest.mark.asyncio
    async def test_xml_batch_size_limit_exceeded(self, mock_s3_client, create_mock_xml_files):
        """Test that XML batch size limit is enforced."""
        files = create_mock_xml_files(151)

        with pytest.raises(HTTPException) as exc_info:
            await handle_xml_ingest(files, mock_s3_client)

        assert exc_info.value.status_code == 400
        assert "Batch size exceeds maximum" in exc_info.value.detail
        assert "151 files" in exc_info.value.detail
        assert "BATCH_MAX_INGEST_FILES" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_xml_parallel_processing_success(self, mock_s3_client, create_mock_xml_files):
        """Test XML files are processed in parallel."""
        files = create_mock_xml_files(5)

        with patch('niem_api.handlers.ingest._get_schema_id') as mock_get_schema, \
             patch('niem_api.handlers.ingest._load_mapping_from_s3') as mock_load_mapping, \
             patch('niem_api.handlers.ingest._download_schema_files') as mock_download_schema, \
             patch('niem_api.handlers.ingest._process_single_file') as mock_process, \
             patch('niem_api.handlers.ingest.Neo4jClient'):

            mock_get_schema.return_value = "test-schema-id"
            mock_load_mapping.return_value = {"mappings": {}}
            mock_download_schema.return_value = "/tmp/schema"

            # Mock successful processing for each file
            mock_process.return_value = (
                {"status": "success", "filename": "test.xml", "nodes_created": 10, "relationships_created": 5},
                15  # statements_executed
            )

            result = await handle_xml_ingest(files, mock_s3_client)

            assert result["files_processed"] == 5
            assert result["successful"] == 5
            assert result["failed"] == 0
            assert result["total_nodes_created"] == 50  # 10 per file * 5 files
            assert result["total_relationships_created"] == 25  # 5 per file * 5 files
            assert mock_process.call_count == 5

    @pytest.mark.asyncio
    async def test_xml_individual_file_failure_isolation(self, mock_s3_client, create_mock_xml_files):
        """Test that individual file failures don't stop batch processing."""
        files = create_mock_xml_files(5)

        with patch('niem_api.handlers.ingest._get_schema_id') as mock_get_schema, \
             patch('niem_api.handlers.ingest._load_mapping_from_s3') as mock_load_mapping, \
             patch('niem_api.handlers.ingest._download_schema_files') as mock_download_schema, \
             patch('niem_api.handlers.ingest._process_single_file') as mock_process, \
             patch('niem_api.handlers.ingest.Neo4jClient'):

            mock_get_schema.return_value = "test-schema-id"
            mock_load_mapping.return_value = {"mappings": {}}
            mock_download_schema.return_value = "/tmp/schema"

            # Mock: 3 successes, 2 failures
            def side_effect(*args, **kwargs):
                file = args[0]
                if "data_1" in file.filename or "data_3" in file.filename:
                    return (
                        {"status": "failed", "filename": file.filename, "error": "Processing error"},
                        0
                    )
                return (
                    {"status": "success", "filename": file.filename, "nodes_created": 10, "relationships_created": 5},
                    15
                )

            mock_process.side_effect = side_effect

            result = await handle_xml_ingest(files, mock_s3_client)

            assert result["files_processed"] == 5
            assert result["successful"] == 3
            assert result["failed"] == 2
            assert len(result["results"]) == 5

    @pytest.mark.asyncio
    async def test_xml_timeout_handling(self, mock_s3_client, create_mock_xml_files):
        """Test that timeout exceptions are handled gracefully."""
        files = create_mock_xml_files(3)

        with patch('niem_api.handlers.ingest._get_schema_id') as mock_get_schema, \
             patch('niem_api.handlers.ingest._load_mapping_from_s3') as mock_load_mapping, \
             patch('niem_api.handlers.ingest._download_schema_files') as mock_download_schema, \
             patch('niem_api.handlers.ingest._process_single_file') as mock_process, \
             patch('niem_api.handlers.ingest.Neo4jClient'), \
             patch('niem_api.handlers.ingest.batch_config') as mock_config:

            mock_get_schema.return_value = "test-schema-id"
            mock_load_mapping.return_value = {"mappings": {}}
            mock_download_schema.return_value = "/tmp/schema"
            mock_config.OPERATION_TIMEOUT = 1
            mock_config.get_batch_limit.return_value = 150

            # Mock: one file times out
            async def slow_process(*args, **kwargs):
                file = args[0]
                if "data_1" in file.filename:
                    await asyncio.sleep(2)  # Exceeds timeout
                return (
                    {"status": "success", "filename": file.filename, "nodes_created": 10, "relationships_created": 5},
                    15
                )

            mock_process.side_effect = slow_process

            result = await handle_xml_ingest(files, mock_s3_client)

            assert result["files_processed"] == 3
            assert result["failed"] >= 1  # At least the timeout
            # Check that timeout error is present
            timeout_results = [r for r in result["results"] if "timeout" in r.get("error", "").lower()]
            assert len(timeout_results) >= 1

    # JSON Ingestion Tests

    @pytest.mark.asyncio
    async def test_json_batch_size_limit_exceeded(self, mock_s3_client, create_mock_json_files):
        """Test that JSON batch size limit is enforced."""
        files = create_mock_json_files(151)

        with pytest.raises(HTTPException) as exc_info:
            await handle_json_ingest(files, mock_s3_client)

        assert exc_info.value.status_code == 400
        assert "Batch size exceeds maximum" in exc_info.value.detail
        assert "BATCH_MAX_INGEST_FILES" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_json_parallel_processing_success(self, mock_s3_client, create_mock_json_files):
        """Test JSON files are processed in parallel."""
        files = create_mock_json_files(5)

        with patch('niem_api.handlers.ingest._get_schema_id') as mock_get_schema, \
             patch('niem_api.handlers.ingest.schema.get_schema_metadata') as mock_get_metadata, \
             patch('niem_api.handlers.ingest._load_mapping_from_s3') as mock_load_mapping, \
             patch('niem_api.handlers.ingest._download_json_schema_from_s3') as mock_download_schema, \
             patch('niem_api.handlers.ingest._process_single_json_file') as mock_process, \
             patch('niem_api.handlers.ingest.Neo4jClient'):

            mock_get_schema.return_value = "test-schema-id"
            mock_get_metadata.return_value = {"json_schema_filename": "schema.json"}
            mock_load_mapping.return_value = {"mappings": {}}
            mock_download_schema.return_value = {"type": "object"}

            # Mock successful processing
            mock_process.return_value = (
                {"status": "success", "filename": "test.json", "nodes_created": 8, "relationships_created": 4},
                12
            )

            result = await handle_json_ingest(files, mock_s3_client)

            assert result["files_processed"] == 5
            assert result["successful"] == 5
            assert result["failed"] == 0
            assert result["total_nodes_created"] == 40  # 8 per file * 5 files
            assert result["total_relationships_created"] == 20  # 4 per file * 5 files

    @pytest.mark.asyncio
    async def test_json_individual_file_failure_isolation(self, mock_s3_client, create_mock_json_files):
        """Test that individual JSON file failures don't stop batch."""
        files = create_mock_json_files(4)

        with patch('niem_api.handlers.ingest._get_schema_id') as mock_get_schema, \
             patch('niem_api.handlers.ingest.schema.get_schema_metadata') as mock_get_metadata, \
             patch('niem_api.handlers.ingest._load_mapping_from_s3') as mock_load_mapping, \
             patch('niem_api.handlers.ingest._download_json_schema_from_s3') as mock_download_schema, \
             patch('niem_api.handlers.ingest._process_single_json_file') as mock_process, \
             patch('niem_api.handlers.ingest.Neo4jClient'):

            mock_get_schema.return_value = "test-schema-id"
            mock_get_metadata.return_value = {"json_schema_filename": "schema.json"}
            mock_load_mapping.return_value = {"mappings": {}}
            mock_download_schema.return_value = {"type": "object"}

            # Mock: 2 successes, 2 failures
            def side_effect(*args, **kwargs):
                file = args[0]
                if "data_0" in file.filename or "data_2" in file.filename:
                    return (
                        {"status": "failed", "filename": file.filename, "error": "Validation error"},
                        0
                    )
                return (
                    {"status": "success", "filename": file.filename, "nodes_created": 8, "relationships_created": 4},
                    12
                )

            mock_process.side_effect = side_effect

            result = await handle_json_ingest(files, mock_s3_client)

            assert result["files_processed"] == 4
            assert result["successful"] == 2
            assert result["failed"] == 2

    @pytest.mark.asyncio
    async def test_batch_summary_fields_present(self, mock_s3_client, create_mock_xml_files):
        """Test that batch summary fields are present in response."""
        files = create_mock_xml_files(2)

        with patch('niem_api.handlers.ingest._get_schema_id') as mock_get_schema, \
             patch('niem_api.handlers.ingest._load_mapping_from_s3') as mock_load_mapping, \
             patch('niem_api.handlers.ingest._download_schema_files') as mock_download_schema, \
             patch('niem_api.handlers.ingest._process_single_file') as mock_process, \
             patch('niem_api.handlers.ingest.Neo4jClient'):

            mock_get_schema.return_value = "test-schema-id"
            mock_load_mapping.return_value = {"mappings": {}}
            mock_download_schema.return_value = "/tmp/schema"
            mock_process.return_value = (
                {"status": "success", "filename": "test.xml", "nodes_created": 10, "relationships_created": 5},
                15
            )

            result = await handle_xml_ingest(files, mock_s3_client)

            # Verify batch summary fields exist
            assert "files_processed" in result
            assert "successful" in result
            assert "failed" in result
            assert result["files_processed"] == 2
            assert isinstance(result["successful"], int)
            assert isinstance(result["failed"], int)
