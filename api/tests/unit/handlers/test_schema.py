#!/usr/bin/env python3

from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi import HTTPException, UploadFile
from minio import Minio

from niem_api.handlers.schema import (
    get_active_schema_id,
    get_all_schemas,
    handle_schema_activation,
    handle_schema_upload,
)


class TestSchemaHandlers:
    """Test suite for schema handler functions"""

    @pytest.fixture
    def mock_s3_client(self):
        """Mock MinIO S3 client"""
        mock_client = Mock(spec=Minio)
        return mock_client

    @pytest.fixture
    def mock_upload_file(self):
        """Mock uploaded XSD file"""
        mock_file = Mock(spec=UploadFile)
        mock_file.filename = "test_schema.xsd"
        mock_file.read = AsyncMock(return_value=b'<?xml version="1.0"?><schema>test</schema>')
        return mock_file

    @pytest.fixture
    def mock_upload_files(self, mock_upload_file):
        """Mock list of uploaded XSD files"""
        return [mock_upload_file]

    @pytest.fixture
    def sample_xsd_content(self):
        """Sample XSD content for testing"""
        return '''<?xml version="1.0" encoding="UTF-8"?>
        <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema"
                   targetNamespace="http://example.com/test"
                   xmlns:tns="http://example.com/test">
            <xs:element name="TestElement" type="xs:string"/>
        </xs:schema>'''

    @pytest.mark.asyncio
    async def test_handle_schema_upload_success(self, mock_s3_client, mock_upload_files):
        """Test successful schema upload and processing"""
        from niem_api.models.models import NdrValidationReport

        with patch('niem_api.handlers.schema._validate_ndr') as mock_ndr, \
             patch('niem_api.handlers.schema._convert_to_cmf') as mock_cmf_convert, \
             patch('niem_api.handlers.schema.upload_file') as mock_upload:

            # Mock NDR validation success
            mock_ndr.return_value = NdrValidationReport(
                status="pass",
                message="Schema is valid",
                conformance_target="niem-6.0",
                errors=[],
                warnings=[],
                summary={"error_count": 0, "warning_count": 0}
            )

            # Mock CMF conversion success
            mock_cmf_convert.return_value = (
                {"status": "success", "cmf_content": "<cmf>test</cmf>"},
                {"status": "success"}
            )

            result = await handle_schema_upload(mock_upload_files, mock_s3_client)

            assert result.schema_id is not None
            assert result.is_active is True
            assert result.ndr_validation.status == "pass"
            mock_upload.assert_called()

    @pytest.mark.asyncio
    async def test_handle_schema_upload_ndr_failure(self, mock_s3_client, mock_upload_files):
        """Test schema upload with NDR validation failure"""
        from niem_api.models.models import NdrValidationReport, NdrValidationIssue

        with patch('niem_api.handlers.schema._validate_ndr') as mock_ndr, \
             patch('niem_api.handlers.schema._convert_to_cmf') as mock_cmf_convert:
            # Mock NDR validation failure
            mock_ndr.return_value = NdrValidationReport(
                status="fail",
                message="Schema validation failed",
                conformance_target="niem-6.0",
                errors=[NdrValidationIssue(
                    file="test.xsd",
                    line=1,
                    column=1,
                    severity="error",
                    message="Invalid element",
                    rule=None
                )],
                warnings=[],
                summary={"error_count": 1, "warning_count": 0}
            )

            # Mock CMF conversion - it should still be attempted
            mock_cmf_convert.return_value = (
                {"status": "success", "cmf_content": "<cmf>test</cmf>"},
                {"status": "success"}
            )

            with pytest.raises(HTTPException) as exc_info:
                await handle_schema_upload(mock_upload_files, mock_s3_client)

            assert exc_info.value.status_code == 400
            # Detail is now a dict with a message field
            assert isinstance(exc_info.value.detail, dict)
            assert "NIEM NDR validation" in exc_info.value.detail['message']

    @pytest.mark.asyncio
    async def test_handle_schema_upload_file_too_large(self, mock_s3_client):
        """Test schema upload with file size limit exceeded"""
        large_file = Mock(spec=UploadFile)
        large_file.filename = "large_schema.xsd"
        large_file.read = AsyncMock(return_value=b'x' * (25 * 1024 * 1024))  # 25MB

        with pytest.raises(HTTPException) as exc_info:
            await handle_schema_upload([large_file], mock_s3_client)

        assert exc_info.value.status_code == 400
        assert "Total file size exceeds" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_handle_schema_activation_success(self, mock_s3_client):
        """Test successful schema activation"""
        schema_id = "test_schema_123"

        # Mock schema exists
        mock_s3_client.get_object.return_value = Mock()

        with patch('niem_api.handlers.schema.upload_file') as mock_upload:
            result = await handle_schema_activation(schema_id, mock_s3_client)

            assert result["active_schema_id"] == schema_id
            mock_upload.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_schema_activation_not_found(self, mock_s3_client):
        """Test schema activation when schema doesn't exist"""
        from minio.error import S3Error

        schema_id = "nonexistent_schema"
        mock_response = Mock()
        mock_s3_client.get_object.side_effect = S3Error(mock_response, "NoSuchKey", "", "", "", "")

        with pytest.raises(HTTPException) as exc_info:
            await handle_schema_activation(schema_id, mock_s3_client)

        assert exc_info.value.status_code == 404
        assert "Schema not found" in exc_info.value.detail

    def test_get_all_schemas_empty(self, mock_s3_client):
        """Test getting all schemas when none exist"""
        from minio.error import S3Error

        # Create S3Error instances with proper code values
        # S3Error signature: S3Error(code, message, resource, request_id, host_id, response)
        no_such_key_error = S3Error("NoSuchKey", "Key not found", "", "", "", Mock())
        no_such_bucket_error = S3Error("NoSuchBucket", "Bucket not found", "", "", "", Mock())

        # Mock get_object to raise S3Error for active_schema.json (so get_active_schema_id returns None)
        mock_s3_client.get_object.side_effect = no_such_key_error
        # Mock list_objects to raise NoSuchBucket error
        mock_s3_client.list_objects.side_effect = no_such_bucket_error

        result = get_all_schemas(mock_s3_client)

        assert result == []

    def test_get_active_schema_id_exists(self, mock_s3_client):
        """Test getting active schema ID when one exists"""
        mock_response = Mock()
        mock_response.read.return_value.decode.return_value = '{"active_schema_id": "schema_123"}'
        mock_s3_client.get_object.return_value = mock_response

        result = get_active_schema_id(mock_s3_client)

        assert result == "schema_123"

    def test_get_active_schema_id_not_found(self, mock_s3_client):
        """Test getting active schema ID when none exists"""
        from minio.error import S3Error

        mock_response = Mock()
        mock_s3_client.get_object.side_effect = S3Error(mock_response, "NoSuchKey", "", "", "", "")

        result = get_active_schema_id(mock_s3_client)

        assert result is None
