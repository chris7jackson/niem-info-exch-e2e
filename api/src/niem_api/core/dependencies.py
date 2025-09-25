#!/usr/bin/env python3

import os

import httpx
from minio import Minio


def get_s3_client():
    """Get MinIO/S3 client"""
    endpoint = os.getenv("MINIO_ENDPOINT", "localhost:9000")
    access_key = os.getenv("MINIO_ACCESS_KEY", "minio")
    secret_key = os.getenv("MINIO_SECRET_KEY", "minio123")
    secure = os.getenv("MINIO_SECURE", "false").lower() == "true"

    # Remove http:// or https:// from endpoint if present
    if endpoint.startswith("http://"):
        endpoint = endpoint[7:]
        secure = False
    elif endpoint.startswith("https://"):
        endpoint = endpoint[8:]
        secure = True

    return Minio(
        endpoint,
        access_key=access_key,
        secret_key=secret_key,
        secure=secure
    )


