#!/usr/bin/env python3

import os
from io import BytesIO

import pytest
from minio import Minio


@pytest.mark.integration
class TestMinioIntegration:
    """Integration tests for MinIO storage operations"""

    @pytest.fixture
    def minio_client(self):
        """MinIO client connected to service (GitHub Actions or local)"""
        endpoint = os.getenv("MINIO_ENDPOINT", "localhost:9000")
        access_key = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
        secret_key = os.getenv("MINIO_SECRET_KEY", "minioadmin")
        secure = os.getenv("MINIO_SECURE", "false").lower() == "true"

        client = Minio(endpoint, access_key=access_key, secret_key=secret_key, secure=secure)
        return client

    def test_minio_connection(self, minio_client):
        """Test basic MinIO connectivity"""
        # Should be able to list buckets (even if empty)
        buckets = list(minio_client.list_buckets())
        assert isinstance(buckets, list)

    def test_minio_bucket_operations(self, minio_client):
        """Test bucket creation and deletion"""
        test_bucket = "test-bucket-integration"

        # Create bucket if not exists
        if not minio_client.bucket_exists(test_bucket):
            minio_client.make_bucket(test_bucket)

        # Verify bucket exists
        assert minio_client.bucket_exists(test_bucket)

        # Upload a test object
        test_data = b"Hello MinIO Integration Test"
        minio_client.put_object(test_bucket, "test-file.txt", BytesIO(test_data), len(test_data))

        # Verify object exists
        obj = minio_client.get_object(test_bucket, "test-file.txt")
        data = obj.read()
        assert data == test_data

        # Cleanup
        minio_client.remove_object(test_bucket, "test-file.txt")
        minio_client.remove_bucket(test_bucket)
