#!/usr/bin/env python3

import logging
from typing import Optional
from minio import Minio
from minio.error import S3Error

logger = logging.getLogger(__name__)

BUCKETS = [
    "niem-schemas",
    "niem-data"
]


async def create_buckets():
    """Create required MinIO buckets"""
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
    """Upload file to MinIO"""
    try:
        from io import BytesIO
        result = client.put_object(
            bucket,
            object_name,
            BytesIO(data),
            length=len(data),
            content_type=content_type
        )
        logger.info(f"Uploaded {object_name} to {bucket}")
        return f"s3://{bucket}/{object_name}"
    except S3Error as e:
        logger.error(f"Failed to upload {object_name} to {bucket}: {e}")
        raise


async def download_file(client: Minio, bucket: str, object_name: str) -> bytes:
    """Download file from MinIO"""
    try:
        response = client.get_object(bucket, object_name)
        data = response.read()
        response.close()
        response.release_conn()
        return data
    except S3Error as e:
        logger.error(f"Failed to download {object_name} from {bucket}: {e}")
        raise


async def list_files(client: Minio, bucket: str, prefix: str = "") -> list:
    """List files in MinIO bucket"""
    try:
        objects = client.list_objects(bucket, prefix=prefix, recursive=True)
        files = []
        for obj in objects:
            files.append({
                "name": obj.object_name,
                "size": obj.size,
                "last_modified": obj.last_modified.isoformat() if obj.last_modified else None,
                "content_type": obj.content_type or "application/octet-stream"
            })
        return files
    except S3Error as e:
        # If bucket doesn't exist, return empty list
        if e.code == "NoSuchBucket":
            logger.info(f"Bucket {bucket} does not exist, returning empty file list")
            return []
        else:
            logger.error(f"Failed to list files in {bucket}: {e}")
            raise