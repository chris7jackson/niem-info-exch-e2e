#!/usr/bin/env python3

import pytest
from unittest.mock import Mock, AsyncMock, patch
from fastapi import HTTPException
from minio import Minio

from niem_api.handlers.admin import (
    handle_reset,
    count_schemas,
    count_data_files,
    clear_neo4j_schema,
    clear_neo4j_data,
    reset_neo4j,
    count_neo4j_objects
)
from niem_api.models.models import ResetRequest


class TestAdminHandlers:
    """Test suite for admin handler functions"""

    @pytest.fixture
    def mock_s3_client(self):
        """Mock MinIO S3 client"""
        mock_client = Mock(spec=Minio)
        mock_client.bucket_exists.return_value = True
        return mock_client

    @pytest.fixture
    def reset_request(self):
        """Sample reset request"""
        return ResetRequest(
            reset_schemas=True,
            reset_data=True,
            reset_neo4j=True
        )

    @pytest.mark.asyncio
    async def test_count_schemas_empty_bucket(self, mock_s3_client):
        """Test counting schemas when bucket is empty"""
        mock_s3_client.bucket_exists.return_value = False

        result = await count_schemas(mock_s3_client)

        assert result == 0
        mock_s3_client.bucket_exists.assert_called_once_with("niem-schemas")

    @pytest.mark.asyncio
    async def test_count_schemas_with_objects(self, mock_s3_client):
        """Test counting schemas with objects in bucket"""
        mock_objects = [Mock(), Mock(), Mock()]
        mock_s3_client.list_objects.return_value = iter(mock_objects)

        result = await count_schemas(mock_s3_client)

        assert result == 3
        mock_s3_client.list_objects.assert_called_once_with("niem-schemas", recursive=True)

    @pytest.mark.asyncio
    async def test_count_data_files(self, mock_s3_client):
        """Test counting data files by type"""
        mock_objects = [
            Mock(object_name="file1.xml", size=1024),
            Mock(object_name="file2.json", size=2048),
            Mock(object_name="file3.xml", size=512),
        ]
        mock_s3_client.list_objects.return_value = iter(mock_objects)

        result = await count_data_files(mock_s3_client)

        assert result["xml_files"] == 2
        assert result["json_files"] == 1
        assert result["total_files"] == 3

    @pytest.mark.asyncio
    async def test_handle_reset_dry_run(self, mock_s3_client, reset_request):
        """Test reset handler dry run (no confirm token)"""
        with patch('niem_api.handlers.admin.count_schemas', return_value=5), \
             patch('niem_api.handlers.admin.count_data_files', return_value={"total_files": 10}), \
             patch('niem_api.handlers.admin.count_neo4j_objects', return_value={"nodes": 100}):

            result = await handle_reset(reset_request, mock_s3_client)

            assert "confirm_token" in result
            assert "Dry run completed" in result["message"]
            assert result["counts"]["schemas"] == 5

    @pytest.mark.asyncio
    async def test_clear_neo4j_schema(self):
        """Test clearing Neo4j schema only"""
        with patch('niem_api.handlers.admin.get_neo4j_client') as mock_client:
            mock_neo4j = Mock()
            mock_client.return_value = mock_neo4j
            mock_neo4j.query.return_value = [
                {"name": "constraint1", "type": "UNIQUENESS"},
                {"name": "index1", "type": "BTREE"}
            ]

            result = await clear_neo4j_schema()

            assert "constraints_dropped" in result
            assert "indexes_dropped" in result
            mock_neo4j.query.assert_called()

    @pytest.mark.asyncio
    async def test_reset_neo4j_error_handling(self):
        """Test Neo4j reset with error handling"""
        with patch('niem_api.handlers.admin.get_neo4j_client') as mock_client:
            mock_neo4j = Mock()
            mock_client.return_value = mock_neo4j
            mock_neo4j.query.side_effect = Exception("Connection failed")

            with pytest.raises(HTTPException) as exc_info:
                await reset_neo4j()

            assert exc_info.value.status_code == 500
            assert "Connection failed" in str(exc_info.value.detail)