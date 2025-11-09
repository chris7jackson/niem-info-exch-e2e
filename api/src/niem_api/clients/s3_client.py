#!/usr/bin/env python3
"""
S3/MinIO Object Storage Client

A low-level client wrapper for MinIO object storage operations.
Handles bucket management and file operations with proper error handling.

This client is pure infrastructure - it contains no business logic.
Use services layer for business logic that uses this client.
"""

import logging
from typing import Any

from minio import Minio
from minio.error import S3Error

logger = logging.getLogger(__name__)

# Application-wide bucket configuration
BUCKETS = ["niem-schemas", "niem-data"]  # Schema XSD files and mappings  # Uploaded XML/JSON data files


async def create_buckets():
    """
    Create required MinIO buckets for the application.

    Creates all buckets defined in the BUCKETS constant if they don't already exist.
    Idempotent - safe to call multiple times.

    Raises:
        S3Error: If bucket creation fails due to permissions or connectivity issues

    Note:
        This should be called during application startup to ensure buckets exist.
        Uses dependency injection to get MinIO client from core.dependencies.
    """
    from ..core.dependencies import get_s3_client

    client = get_s3_client()

    for bucket_name in BUCKETS:
        try:
            if not client.bucket_exists(bucket_name):
                client.make_bucket(bucket_name)
                logger.info(f"Created bucket: {bucket_name}")
            else:
                logger.info(f"Bucket already exists: {bucket_name}")
        except S3Error as e:
            logger.error(f"Failed to create bucket {bucket_name}: {e}")
            raise


async def upload_file(client: Minio, bucket: str, object_name: str, data: bytes, content_type: str) -> str:
    """
    Upload a file to MinIO object storage.

    Args:
        client: MinIO client instance
        bucket: Target bucket name (must exist)
        object_name: Object key/path within bucket (e.g., "schemas/schema1.xsd")
        data: File content as bytes
        content_type: MIME type (e.g., "application/xml", "application/json")

    Returns:
        S3 URI of uploaded file (e.g., "s3://niem-schemas/schema1.xsd")

    Raises:
        S3Error: If upload fails due to permissions, connectivity, or bucket not found

    Example:
        ```python
        client = get_s3_client()
        xml_content = b'<root>...</root>'
        uri = await upload_file(
            client,
            "niem-data",
            "uploads/file.xml",
            xml_content,
            "application/xml"
        )
        ```
    """
    try:
        from io import BytesIO

        client.put_object(bucket, object_name, BytesIO(data), length=len(data), content_type=content_type)
        logger.info(f"Uploaded {object_name} to {bucket}")
        return f"s3://{bucket}/{object_name}"
    except S3Error as e:
        logger.error(f"Failed to upload {object_name} to {bucket}: {e}")
        raise


async def download_file(client: Minio, bucket: str, object_name: str) -> bytes:
    """
    Download a file from MinIO object storage.

    Args:
        client: MinIO client instance
        bucket: Source bucket name
        object_name: Object key/path within bucket

    Returns:
        File content as bytes

    Raises:
        S3Error: If download fails (object not found, permissions, connectivity)

    Example:
        ```python
        client = get_s3_client()
        content = await download_file(client, "niem-schemas", "schema1.xsd")
        xml_string = content.decode('utf-8')
        ```

    Note:
        Response connection is properly closed and released after reading.
    """
    try:
        response = client.get_object(bucket, object_name)
        data = response.read()
        response.close()
        response.release_conn()
        return data
    except S3Error as e:
        logger.error(f"Failed to download {object_name} from {bucket}: {e}")
        raise


async def list_files(client: Minio, bucket: str, prefix: str = "") -> list[dict[str, Any]]:
    """
    List files in a MinIO bucket with optional prefix filter.

    Args:
        client: MinIO client instance
        bucket: Bucket name to list
        prefix: Optional prefix to filter results (e.g., "uploads/" for subfolder)

    Returns:
        List of file metadata dictionaries with keys:
        - name: Object key/path (str)
        - size: File size in bytes (int)
        - last_modified: ISO8601 timestamp string or None
        - content_type: MIME type (str)

    Raises:
        S3Error: If listing fails due to permissions or connectivity

    Example:
        ```python
        client = get_s3_client()

        # List all files
        all_files = await list_files(client, "niem-data")

        # List files in subfolder
        xml_files = await list_files(client, "niem-data", prefix="xml/")

        for file in xml_files:
            print(f"{file['name']}: {file['size']} bytes")
        ```

    Note:
        Returns empty list if bucket doesn't exist (not an error).
        Uses recursive listing to include all nested objects.
    """
    try:
        objects = client.list_objects(bucket, prefix=prefix, recursive=True)
        files = []
        for obj in objects:
            files.append(
                {
                    "name": obj.object_name,
                    "size": obj.size,
                    "last_modified": obj.last_modified.isoformat() if obj.last_modified else None,
                    "content_type": obj.content_type or "application/octet-stream",
                }
            )
        return files
    except S3Error as e:
        # If bucket doesn't exist, return empty list
        if e.code == "NoSuchBucket":
            logger.info(f"Bucket {bucket} does not exist, returning empty file list")
            return []
        else:
            logger.error(f"Failed to list files in {bucket}: {e}")
            raise


def get_text_content(client: Minio, bucket: str, object_name: str) -> str:
    """
    Get object content as decoded UTF-8 string with proper connection cleanup.

    Args:
        client: MinIO client instance
        bucket: Source bucket name
        object_name: Object key/path within bucket

    Returns:
        Object content as UTF-8 string

    Raises:
        S3Error: If download fails (object not found, permissions, connectivity)

    Example:
        ```python
        client = get_s3_client()
        yaml_content = get_text_content(client, "niem-schemas", "schema/mapping.yaml")
        ```

    Note:
        Properly closes and releases HTTP connection after reading.
    """
    try:
        response = client.get_object(bucket, object_name)
        content = response.read().decode("utf-8")
        response.close()
        response.release_conn()
        return content
    except S3Error as e:
        logger.error(f"Failed to get text content from {object_name} in {bucket}: {e}")
        raise


def get_json_content(client: Minio, bucket: str, object_name: str) -> dict[str, Any]:
    """
    Get object content as parsed JSON with proper connection cleanup.

    Args:
        client: MinIO client instance
        bucket: Source bucket name
        object_name: Object key/path within bucket

    Returns:
        Parsed JSON object as dictionary

    Raises:
        S3Error: If download fails
        json.JSONDecodeError: If content is not valid JSON

    Example:
        ```python
        client = get_s3_client()
        metadata = get_json_content(client, "niem-schemas", "schema/metadata.json")
        schema_id = metadata["schema_id"]
        ```

    Note:
        Properly closes and releases HTTP connection after reading.
    """
    import json

    try:
        response = client.get_object(bucket, object_name)
        content = response.read().decode("utf-8")
        response.close()
        response.release_conn()
        return json.loads(content)
    except S3Error as e:
        logger.error(f"Failed to get JSON content from {object_name} in {bucket}: {e}")
        raise


def get_yaml_content(client: Minio, bucket: str, object_name: str) -> dict[str, Any]:
    """
    Get object content as parsed YAML with proper connection cleanup.

    Args:
        client: MinIO client instance
        bucket: Source bucket name
        object_name: Object key/path within bucket

    Returns:
        Parsed YAML object as dictionary

    Raises:
        S3Error: If download fails
        yaml.YAMLError: If content is not valid YAML

    Example:
        ```python
        client = get_s3_client()
        mapping = get_yaml_content(client, "niem-schemas", "schema/mapping.yaml")
        ```

    Note:
        Properly closes and releases HTTP connection after reading.
    """
    import yaml

    try:
        response = client.get_object(bucket, object_name)
        content = response.read().decode("utf-8")
        response.close()
        response.release_conn()
        return yaml.safe_load(content)
    except S3Error as e:
        logger.error(f"Failed to get YAML content from {object_name} in {bucket}: {e}")
        raise
