#!/usr/bin/env python3
"""Tests for schema handler batch processing capabilities."""

from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi import HTTPException, UploadFile
from minio import Minio

from niem_api.handlers.schema import handle_schema_upload


class TestSchemaBatchProcessing:
    """Test suite for schema upload batch processing."""

    @pytest.fixture
    def mock_s3_client(self):
        """Mock MinIO S3 client."""
        return Mock(spec=Minio)

    @pytest.fixture
    def create_mock_files(self):
        """Factory to create mock upload files."""
        def _create_files(count):
            files = []
            for i in range(count):
                mock_file = Mock(spec=UploadFile)
                mock_file.filename = f"schema_{i}.xsd"
                mock_file.read = AsyncMock(return_value=b'<?xml version="1.0"?><schema>test</schema>')
                files.append(mock_file)
            return files
        return _create_files

    @pytest.mark.asyncio
    async def test_batch_size_limit_exceeded(self, mock_s3_client, create_mock_files):
        """Test that batch size limit is enforced."""
        # Create 151 files (exceeds default limit of 150)
        files = create_mock_files(151)

        with pytest.raises(HTTPException) as exc_info:
            await handle_schema_upload(files, mock_s3_client)

        assert exc_info.value.status_code == 400
        assert "Batch size exceeds maximum" in exc_info.value.detail
        assert "151 files" in exc_info.value.detail
        assert "BATCH_MAX_SCHEMA_FILES" in exc_info.value.detail
        assert ".env" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_batch_size_limit_with_custom_env(self, mock_s3_client, create_mock_files):
        """Test batch size limit with custom environment variable."""
        # Create 3 files (exceeds custom limit of 2)
        files = create_mock_files(3)

        # Need to reload config and handler to pick up env var
        from importlib import reload
        from niem_api.core import config
        from niem_api.handlers import schema
        from unittest.mock import patch

        try:
            with patch.dict('os.environ', {'BATCH_MAX_SCHEMA_FILES': '2'}):
                reload(config)
                reload(schema)

                # Re-import the function from the reloaded module
                from niem_api.handlers.schema import handle_schema_upload as handle_upload

                with pytest.raises(HTTPException) as exc_info:
                    await handle_upload(files, mock_s3_client)

                assert exc_info.value.status_code == 400
                assert "exceeds maximum of 2 files" in exc_info.value.detail
        finally:
            # Restore original config by reloading without env override
            reload(config)
            reload(schema)

    @pytest.mark.asyncio
    async def test_batch_within_limit_success(self, mock_s3_client, create_mock_files):
        """Test successful batch upload within limit."""
        from niem_api.models.models import SchevalReport

        files = create_mock_files(10)

        with patch('niem_api.handlers.schema._validate_all_scheval') as mock_scheval, \
             patch('niem_api.handlers.schema._convert_to_cmf') as mock_cmf, \
             patch('niem_api.handlers.schema.upload_file') as mock_upload:

            mock_scheval.return_value = SchevalReport(
                status="pass",
                message="Valid",
                conformance_target="niem-6.0",
                errors=[],
                warnings=[],
                summary={"error_count": 0, "warning_count": 0}
            )

            mock_cmf.return_value = (
                {"status": "success", "cmf_content": "<cmf>test</cmf>"},
                {"status": "success", "jsonschema": {"type": "object"}}
            )

            result = await handle_schema_upload(files, mock_s3_client)

            assert result.files_processed == 10
            assert result.successful == 10
            assert result.failed == 0
            assert result.schema_id is not None

    @pytest.mark.asyncio
    async def test_batch_all_or_nothing_failure(self, mock_s3_client, create_mock_files):
        """Test all-or-nothing behavior: if validation fails, entire batch fails."""
        from niem_api.models.models import SchevalReport, SchevalIssue

        files = create_mock_files(5)

        with patch('niem_api.handlers.schema._validate_all_scheval') as mock_scheval, \
             patch('niem_api.handlers.schema._convert_to_cmf') as mock_cmf:

            # Mock validation failure on one file - should fail entire batch
            mock_scheval.return_value = SchevalReport(
                status="fail",
                message="Validation failed",
                conformance_target="niem-6.0",
                errors=[SchevalIssue(
                    file="schema_2.xsd",
                    line=10,
                    column=5,
                    severity="error",
                    message="Invalid element",
                    rule="niem-rule-1",
                    context=None
                )],
                warnings=[],
                summary={"error_count": 1, "warning_count": 0}
            )

            mock_cmf.return_value = (
                {"status": "success", "cmf_content": "<cmf>test</cmf>"},
                {"status": "success"}
            )

            with pytest.raises(HTTPException) as exc_info:
                await handle_schema_upload(files, mock_s3_client)

            assert exc_info.value.status_code == 400
            assert isinstance(exc_info.value.detail, dict)
            assert "NIEM NDR validation" in exc_info.value.detail['message']

    @pytest.mark.asyncio
    async def test_single_file_upload(self, mock_s3_client, create_mock_files):
        """Test single file upload (edge case of batch processing)."""
        from niem_api.models.models import SchevalReport

        files = create_mock_files(1)

        with patch('niem_api.handlers.schema._validate_all_scheval') as mock_scheval, \
             patch('niem_api.handlers.schema._convert_to_cmf') as mock_cmf, \
             patch('niem_api.handlers.schema.upload_file'):

            mock_scheval.return_value = SchevalReport(
                status="pass",
                message="Valid",
                conformance_target="niem-6.0",
                errors=[],
                warnings=[],
                summary={"error_count": 0, "warning_count": 0}
            )

            mock_cmf.return_value = (
                {"status": "success", "cmf_content": "<cmf>test</cmf>"},
                {"status": "success", "jsonschema": {"type": "object"}}
            )

            result = await handle_schema_upload(files, mock_s3_client)

            assert result.files_processed == 1
            assert result.successful == 1
            assert result.failed == 0

    @pytest.mark.asyncio
    async def test_batch_summary_fields_present(self, mock_s3_client, create_mock_files):
        """Test that batch summary fields are always present in response."""
        from niem_api.models.models import SchevalReport

        files = create_mock_files(3)

        with patch('niem_api.handlers.schema._validate_all_scheval') as mock_scheval, \
             patch('niem_api.handlers.schema._convert_to_cmf') as mock_cmf, \
             patch('niem_api.handlers.schema.upload_file'):

            mock_scheval.return_value = SchevalReport(
                status="pass",
                message="Valid",
                conformance_target="niem-6.0",
                errors=[],
                warnings=[],
                summary={"error_count": 0, "warning_count": 0}
            )

            mock_cmf.return_value = (
                {"status": "success", "cmf_content": "<cmf>test</cmf>"},
                {"status": "success", "jsonschema": {"type": "object"}}
            )

            result = await handle_schema_upload(files, mock_s3_client)

            # Verify batch summary fields exist
            assert hasattr(result, 'files_processed')
            assert hasattr(result, 'successful')
            assert hasattr(result, 'failed')
            assert result.files_processed is not None
            assert result.successful is not None
            assert result.failed is not None
