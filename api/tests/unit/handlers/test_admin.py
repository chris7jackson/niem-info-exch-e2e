#!/usr/bin/env python3

from unittest.mock import Mock, patch

import pytest
from minio import Minio

from niem_api.handlers.admin import count_data_files, count_neo4j_objects, count_schemas, handle_reset, reset_neo4j
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
            schemas=True,
            data=True,
            neo4j=True,
            dry_run=False
        )

    def test_count_schemas_empty_bucket(self, mock_s3_client):
        """Test counting schemas when bucket is empty"""
        mock_s3_client.bucket_exists.return_value = False

        result = count_schemas(mock_s3_client)

        assert result == 0
        mock_s3_client.bucket_exists.assert_called_once_with("niem-schemas")

    def test_count_schemas_with_objects(self, mock_s3_client):
        """Test counting schemas with objects in bucket"""
        # Create mock objects with is_dir attribute
        mock_obj1 = Mock()
        mock_obj1.is_dir = True
        mock_obj1.object_name = "schema1/"

        mock_obj2 = Mock()
        mock_obj2.is_dir = False
        mock_obj2.object_name = "schema2/file.xsd"

        mock_s3_client.list_objects.return_value = iter([mock_obj1, mock_obj2])

        result = count_schemas(mock_s3_client)

        assert result == 2
        mock_s3_client.list_objects.assert_called_once_with("niem-schemas", recursive=False)

    def test_count_data_files(self, mock_s3_client):
        """Test counting data files by type"""
        mock_objects = [
            Mock(object_name="file1.xml", size=1024),
            Mock(object_name="file2.json", size=2048),
            Mock(object_name="file3.xml", size=512),
        ]
        mock_s3_client.list_objects.return_value = iter(mock_objects)

        result = count_data_files(mock_s3_client)

        assert result["xml_files"] == 2
        assert result["json_files"] == 1
        assert result["total_files"] == 3

    def test_handle_reset_dry_run(self, mock_s3_client):
        """Test reset handler dry run (no confirm token)"""
        reset_request = ResetRequest(schemas=True, data=True, neo4j=True, dry_run=True)

        with patch('niem_api.handlers.admin.count_schemas', return_value=5), \
             patch('niem_api.handlers.admin.count_data_files', return_value={"total_files": 10}), \
             patch('niem_api.handlers.admin.count_neo4j_objects', return_value={"status": "success", "stats": {"nodes": 100, "relationships": 50, "indexes": 2, "constraints": 1}}):

            result = handle_reset(reset_request, mock_s3_client)

            assert result.confirm_token is not None
            assert "Dry run completed" in result.message
            assert result.counts["schemas"] == 5

    def test_count_neo4j_objects(self):
        """Test counting Neo4j objects"""
        with patch('niem_api.core.dependencies.get_neo4j_client') as mock_client:
            mock_neo4j = Mock()
            mock_client.return_value = mock_neo4j
            mock_neo4j.query.side_effect = [
                [{"count": 100}],  # Node count
                [{"count": 50}],   # Relationship count
                [{"name": "index1", "type": "BTREE"}, {"name": "lookup_index", "type": "LOOKUP"}],  # Indexes
                [{"name": "constraint1"}]  # Constraints
            ]

            result = count_neo4j_objects()

            assert result["status"] == "success"
            assert result["stats"]["nodes"] == 100
            assert result["stats"]["relationships"] == 50
            assert result["stats"]["indexes"] == 1  # Only BTREE, not LOOKUP
            assert result["stats"]["constraints"] == 1

    def test_reset_neo4j_error_handling(self):
        """Test Neo4j reset with error handling"""
        with patch('niem_api.core.dependencies.get_neo4j_client') as mock_client:
            mock_neo4j = Mock()
            mock_client.return_value = mock_neo4j
            mock_neo4j.query.side_effect = Exception("Connection failed")

            with pytest.raises(Exception) as exc_info:
                reset_neo4j()

            assert "Connection failed" in str(exc_info.value)
