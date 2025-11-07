#!/usr/bin/env python3
"""Tests for XML-to-JSON conversion batch processing capabilities."""

import asyncio
from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi import HTTPException, UploadFile
from minio import Minio

from niem_api.handlers.convert import handle_xml_to_json_batch


class TestConversionBatchProcessing:
    """Test suite for XML-to-JSON conversion batch processing."""

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
                mock_file.filename = f"instance_{i}.xml"
                mock_file.read = AsyncMock(return_value=b'<?xml version="1.0"?><data>test</data>')
                files.append(mock_file)
            return files
        return _create_files

    @pytest.mark.asyncio
    async def test_batch_size_limit_exceeded(self, mock_s3_client, create_mock_xml_files):
        """Test that batch size limit is enforced for conversion."""
        files = create_mock_xml_files(151)

        with pytest.raises(HTTPException) as exc_info:
            await handle_xml_to_json_batch(files, mock_s3_client)

        assert exc_info.value.status_code == 400
        assert "Batch size exceeds maximum" in exc_info.value.detail
        assert "151 files" in exc_info.value.detail
        assert "BATCH_MAX_CONVERSION_FILES" in exc_info.value.detail
        assert ".env" in exc_info.value.detail

    @pytest.mark.asyncio
    @patch.dict('os.environ', {'BATCH_MAX_CONVERSION_FILES': '5'})
    async def test_batch_size_limit_with_custom_env(self, mock_s3_client, create_mock_xml_files):
        """Test batch size limit with custom environment variable."""
        files = create_mock_xml_files(6)

        # Reload config to pick up env var
        from importlib import reload
        from niem_api.core import config
        reload(config)

        with pytest.raises(HTTPException) as exc_info:
            await handle_xml_to_json_batch(files, mock_s3_client)

        assert exc_info.value.status_code == 400
        assert "exceeds maximum of 5 files" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_parallel_conversion_success(self, mock_s3_client, create_mock_xml_files):
        """Test XML files are converted to JSON in parallel."""
        files = create_mock_xml_files(5)

        with patch('niem_api.handlers.convert.is_niemtran_available') as mock_niemtran_available, \
             patch('niem_api.handlers.convert._get_schema_id') as mock_get_schema, \
             patch('niem_api.handlers.convert._download_schema_files_for_validation') as mock_download, \
             patch('niem_api.handlers.convert._convert_single_file') as mock_convert:

            mock_niemtran_available.return_value = True
            mock_get_schema.return_value = "test-schema-id"
            mock_download.return_value = "/tmp/schema"

            # Mock successful conversion
            mock_convert.return_value = {
                "filename": "test.xml",
                "status": "success",
                "json_content": {"test": "data"},
                "json_string": '{"test": "data"}'
            }

            result = await handle_xml_to_json_batch(files, mock_s3_client)

            assert result["files_processed"] == 5
            assert result["successful"] == 5
            assert result["failed"] == 0
            assert len(result["results"]) == 5
            assert mock_convert.call_count == 5

    @pytest.mark.asyncio
    async def test_individual_file_failure_isolation(self, mock_s3_client, create_mock_xml_files):
        """Test that individual file failures don't stop conversion batch."""
        files = create_mock_xml_files(4)

        with patch('niem_api.handlers.convert.is_niemtran_available') as mock_niemtran_available, \
             patch('niem_api.handlers.convert._get_schema_id') as mock_get_schema, \
             patch('niem_api.handlers.convert._download_schema_files_for_validation') as mock_download, \
             patch('niem_api.handlers.convert._convert_single_file') as mock_convert:

            mock_niemtran_available.return_value = True
            mock_get_schema.return_value = "test-schema-id"
            mock_download.return_value = "/tmp/schema"

            # Mock: 2 successes, 2 failures
            def side_effect(*args, **kwargs):
                file = args[0]
                if "instance_0" in file.filename or "instance_2" in file.filename:
                    return {
                        "filename": file.filename,
                        "status": "failed",
                        "error": "Conversion error"
                    }
                return {
                    "filename": file.filename,
                    "status": "success",
                    "json_content": {"test": "data"},
                    "json_string": '{"test": "data"}'
                }

            mock_convert.side_effect = side_effect

            result = await handle_xml_to_json_batch(files, mock_s3_client)

            assert result["files_processed"] == 4
            assert result["successful"] == 2
            assert result["failed"] == 2

    @pytest.mark.asyncio
    async def test_timeout_handling(self, mock_s3_client, create_mock_xml_files):
        """Test that timeout exceptions are handled for conversion."""
        files = create_mock_xml_files(3)

        with patch('niem_api.handlers.convert.is_niemtran_available') as mock_niemtran_available, \
             patch('niem_api.handlers.convert._get_schema_id') as mock_get_schema, \
             patch('niem_api.handlers.convert._download_schema_files_for_validation') as mock_download, \
             patch('niem_api.handlers.convert._convert_single_file') as mock_convert, \
             patch('niem_api.handlers.convert.batch_config') as mock_config:

            mock_niemtran_available.return_value = True
            mock_get_schema.return_value = "test-schema-id"
            mock_download.return_value = "/tmp/schema"
            mock_config.OPERATION_TIMEOUT = 1
            mock_config.get_batch_limit.return_value = 150

            # Mock: one file takes too long
            async def slow_convert(*args, **kwargs):
                file = args[0]
                if "instance_1" in file.filename:
                    await asyncio.sleep(2)  # Exceeds timeout
                return {
                    "filename": file.filename,
                    "status": "success",
                    "json_content": {"test": "data"},
                    "json_string": '{"test": "data"}'
                }

            mock_convert.side_effect = slow_convert

            result = await handle_xml_to_json_batch(files, mock_s3_client)

            assert result["files_processed"] == 3
            assert result["failed"] >= 1
            # Check that at least one timeout error exists
            timeout_results = [r for r in result["results"] if "timeout" in r.get("error", "").lower()]
            assert len(timeout_results) >= 1

    @pytest.mark.asyncio
    async def test_niemtran_not_available(self, mock_s3_client, create_mock_xml_files):
        """Test error when NIEMTran tool is not available."""
        files = create_mock_xml_files(2)

        with patch('niem_api.handlers.convert.is_niemtran_available') as mock_niemtran_available:
            mock_niemtran_available.return_value = False

            with pytest.raises(HTTPException) as exc_info:
                await handle_xml_to_json_batch(files, mock_s3_client)

            assert exc_info.value.status_code == 500
            assert "NIEMTran tool is not available" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_batch_summary_fields(self, mock_s3_client, create_mock_xml_files):
        """Test that batch summary fields are present in response."""
        files = create_mock_xml_files(3)

        with patch('niem_api.handlers.convert.is_niemtran_available') as mock_niemtran_available, \
             patch('niem_api.handlers.convert._get_schema_id') as mock_get_schema, \
             patch('niem_api.handlers.convert._download_schema_files_for_validation') as mock_download, \
             patch('niem_api.handlers.convert._convert_single_file') as mock_convert:

            mock_niemtran_available.return_value = True
            mock_get_schema.return_value = "test-schema-id"
            mock_download.return_value = "/tmp/schema"
            mock_convert.return_value = {
                "filename": "test.xml",
                "status": "success",
                "json_content": {"test": "data"},
                "json_string": '{"test": "data"}'
            }

            result = await handle_xml_to_json_batch(files, mock_s3_client)

            # Verify batch summary fields exist
            assert "files_processed" in result
            assert "successful" in result
            assert "failed" in result
            assert "results" in result
            assert result["files_processed"] == 3
            assert isinstance(result["successful"], int)
            assert isinstance(result["failed"], int)
            assert isinstance(result["results"], list)

    @pytest.mark.asyncio
    async def test_single_file_conversion(self, mock_s3_client, create_mock_xml_files):
        """Test single file conversion (edge case of batch processing)."""
        files = create_mock_xml_files(1)

        with patch('niem_api.handlers.convert.is_niemtran_available') as mock_niemtran_available, \
             patch('niem_api.handlers.convert._get_schema_id') as mock_get_schema, \
             patch('niem_api.handlers.convert._download_schema_files_for_validation') as mock_download, \
             patch('niem_api.handlers.convert._convert_single_file') as mock_convert:

            mock_niemtran_available.return_value = True
            mock_get_schema.return_value = "test-schema-id"
            mock_download.return_value = "/tmp/schema"
            mock_convert.return_value = {
                "filename": "instance_0.xml",
                "status": "success",
                "json_content": {"test": "data"},
                "json_string": '{"test": "data"}'
            }

            result = await handle_xml_to_json_batch(files, mock_s3_client)

            assert result["files_processed"] == 1
            assert result["successful"] == 1
            assert result["failed"] == 0
