#!/usr/bin/env python3

import pytest
import json
import os
from io import BytesIO
from minio import Minio

from niem_api.services.storage import (
    upload_file,
    create_buckets,
    list_files,
    delete_file,
    get_file_content
)


@pytest.mark.integration
class TestMinioIntegration:
    """Integration tests for MinIO storage operations"""

    @pytest.fixture
    def minio_client(self):
        """MinIO client connected to service (GitHub Actions or local)"""
        endpoint = os.getenv("MINIO_ENDPOINT", "localhost:9001")
        access_key = os.getenv("MINIO_ACCESS_KEY", "minio")
        secret_key = os.getenv("MINIO_SECRET_KEY", "minio123")
        secure = os.getenv("MINIO_SECURE", "false").lower() == "true"

        client = Minio(
            endpoint,
            access_key=access_key,
            secret_key=secret_key,
            secure=secure
        )
        return client

    @pytest.fixture(scope="class")
    def minio_container(self):
        """Start MinIO test container"""
        with MinioContainer() as minio:
            yield minio

    @pytest.fixture
    def minio_client(self, minio_container):
        """MinIO client connected to test container"""
        from minio import Minio

        client = Minio(
            minio_container.get_connection_url().replace("http://", ""),
            access_key=minio_container.access_key,
            secret_key=minio_container.secret_key,
            secure=False
        )
        return client

    @pytest.mark.asyncio
    async def test_bucket_creation(self, minio_client):
        """Test bucket creation functionality"""
        # Mock the get_s3_client dependency
        with patch('niem_api.services.storage.get_s3_client', return_value=minio_client):
            await create_buckets()

        # Verify buckets were created
        buckets = list(minio_client.list_buckets())
        bucket_names = [bucket.name for bucket in buckets]

        assert "niem-schemas" in bucket_names
        assert "niem-data" in bucket_names

    @pytest.mark.asyncio
    async def test_file_upload_and_retrieval(self, minio_client):
        """Test file upload and retrieval operations"""
        # Ensure bucket exists
        if not minio_client.bucket_exists("test-bucket"):
            minio_client.make_bucket("test-bucket")

        # Test file content
        test_content = b"This is a test file content"
        test_filename = "test-file.txt"

        # Upload file
        await upload_file(
            minio_client,
            "test-bucket",
            test_filename,
            test_content,
            "text/plain"
        )

        # Verify file exists
        try:
            response = minio_client.get_object("test-bucket", test_filename)
            retrieved_content = response.read()
            response.close()
            response.release_conn()

            assert retrieved_content == test_content
        except Exception as e:
            pytest.fail(f"Failed to retrieve uploaded file: {e}")

    @pytest.mark.asyncio
    async def test_file_listing(self, minio_client):
        """Test file listing functionality"""
        bucket_name = "test-listing"

        # Ensure bucket exists
        if not minio_client.bucket_exists(bucket_name):
            minio_client.make_bucket(bucket_name)

        # Upload multiple test files
        test_files = [
            ("file1.txt", b"Content 1"),
            ("file2.json", b'{"key": "value"}'),
            ("subdir/file3.xml", b"<root>test</root>")
        ]

        for filename, content in test_files:
            await upload_file(minio_client, bucket_name, filename, content, "text/plain")

        # List files
        files = await list_files(minio_client, bucket_name)

        assert len(files) == 3
        filenames = [f["name"] for f in files]
        assert "file1.txt" in filenames
        assert "file2.json" in filenames
        assert "subdir/file3.xml" in filenames

        # Verify file metadata
        json_file = next(f for f in files if f["name"] == "file2.json")
        assert json_file["size"] > 0
        assert json_file["content_type"] is not None

    @pytest.mark.asyncio
    async def test_file_deletion(self, minio_client):
        """Test file deletion functionality"""
        bucket_name = "test-deletion"

        # Ensure bucket exists
        if not minio_client.bucket_exists(bucket_name):
            minio_client.make_bucket(bucket_name)

        # Upload a test file
        test_filename = "to-delete.txt"
        test_content = b"This file will be deleted"

        await upload_file(minio_client, bucket_name, test_filename, test_content, "text/plain")

        # Verify file exists
        files_before = await list_files(minio_client, bucket_name)
        assert any(f["name"] == test_filename for f in files_before)

        # Delete the file
        await delete_file(minio_client, bucket_name, test_filename)

        # Verify file was deleted
        files_after = await list_files(minio_client, bucket_name)
        assert not any(f["name"] == test_filename for f in files_after)

    @pytest.mark.asyncio
    async def test_schema_storage_workflow(self, minio_client):
        """Test complete schema storage workflow"""
        schema_id = "test_schema_123"
        bucket_name = "niem-schemas"

        # Ensure bucket exists
        if not minio_client.bucket_exists(bucket_name):
            minio_client.make_bucket(bucket_name)

        # Simulate complete schema upload workflow
        files_to_upload = {
            f"{schema_id}/schema.xsd": (b"<schema>XSD content</schema>", "application/xml"),
            f"{schema_id}/schema.cmf": (b"<cmf>CMF content</cmf>", "application/xml"),
            f"{schema_id}/schema.json": (json.dumps({"type": "object"}).encode(), "application/json"),
            f"{schema_id}/mapping.yaml": (b"objects: []\nassociations: []", "application/x-yaml"),
            f"{schema_id}/metadata.json": (json.dumps({
                "schema_id": schema_id,
                "filename": "test_schema.xsd",
                "uploaded_at": "2024-01-01T00:00:00",
                "is_active": True
            }).encode(), "application/json")
        }

        # Upload all files
        for filepath, (content, content_type) in files_to_upload.items():
            await upload_file(minio_client, bucket_name, filepath, content, content_type)

        # Verify all files exist
        for filepath in files_to_upload.keys():
            try:
                response = minio_client.get_object(bucket_name, filepath)
                response.close()
                response.release_conn()
            except Exception as e:
                pytest.fail(f"Failed to retrieve {filepath}: {e}")

        # Test metadata retrieval
        metadata_response = minio_client.get_object(bucket_name, f"{schema_id}/metadata.json")
        metadata = json.loads(metadata_response.read().decode())
        metadata_response.close()
        metadata_response.release_conn()

        assert metadata["schema_id"] == schema_id
        assert metadata["is_active"] is True

    @pytest.mark.asyncio
    async def test_data_file_storage(self, minio_client):
        """Test data file storage for ingestion"""
        bucket_name = "niem-data"

        # Ensure bucket exists
        if not minio_client.bucket_exists(bucket_name):
            minio_client.make_bucket(bucket_name)

        # Test XML file storage
        xml_content = b'''<?xml version="1.0"?>
        <CrashDriver>
            <PersonName>John Doe</PersonName>
            <Age>30</Age>
        </CrashDriver>'''

        xml_filename = "test_crash_data.xml"
        await upload_file(minio_client, bucket_name, xml_filename, xml_content, "application/xml")

        # Test JSON file storage
        json_content = json.dumps({
            "person_name": "Jane Doe",
            "age": 25
        }).encode()

        json_filename = "test_data.json"
        await upload_file(minio_client, bucket_name, json_filename, json_content, "application/json")

        # Verify both files
        files = await list_files(minio_client, bucket_name)
        filenames = [f["name"] for f in files]

        assert xml_filename in filenames
        assert json_filename in filenames

        # Verify content types
        xml_file = next(f for f in files if f["name"] == xml_filename)
        json_file = next(f for f in files if f["name"] == json_filename)

        assert "xml" in xml_file["content_type"].lower()
        assert "json" in json_file["content_type"].lower()

    @pytest.mark.asyncio
    async def test_large_file_handling(self, minio_client):
        """Test handling of large files"""
        bucket_name = "test-large-files"

        # Ensure bucket exists
        if not minio_client.bucket_exists(bucket_name):
            minio_client.make_bucket(bucket_name)

        # Create a large file (1MB)
        large_content = b"A" * (1024 * 1024)
        large_filename = "large_file.bin"

        # Upload large file
        await upload_file(minio_client, bucket_name, large_filename, large_content, "application/octet-stream")

        # Verify upload
        response = minio_client.get_object(bucket_name, large_filename)
        retrieved_content = response.read()
        response.close()
        response.release_conn()

        assert len(retrieved_content) == len(large_content)
        assert retrieved_content == large_content

    @pytest.mark.asyncio
    async def test_concurrent_uploads(self, minio_client):
        """Test concurrent file uploads"""
        import asyncio

        bucket_name = "test-concurrent"

        # Ensure bucket exists
        if not minio_client.bucket_exists(bucket_name):
            minio_client.make_bucket(bucket_name)

        async def upload_test_file(file_index: int):
            content = f"File {file_index} content".encode()
            filename = f"concurrent_file_{file_index}.txt"
            await upload_file(minio_client, bucket_name, filename, content, "text/plain")

        # Upload 10 files concurrently
        tasks = [upload_test_file(i) for i in range(10)]
        await asyncio.gather(*tasks)

        # Verify all files were uploaded
        files = await list_files(minio_client, bucket_name)
        assert len(files) == 10

        # Verify filenames
        expected_files = [f"concurrent_file_{i}.txt" for i in range(10)]
        actual_files = [f["name"] for f in files]

        for expected_file in expected_files:
            assert expected_file in actual_files