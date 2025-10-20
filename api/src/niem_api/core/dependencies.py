#!/usr/bin/env python3

import os

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


# Global Neo4j client instance
_neo4j_client = None

def get_neo4j_client():
    """Get or create global Neo4j client instance"""
    global _neo4j_client
    if _neo4j_client is None:
        from ..clients.neo4j_client import Neo4jClient

        neo4j_uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        neo4j_user = os.getenv("NEO4J_USER", "neo4j")
        neo4j_password = os.getenv("NEO4J_PASSWORD", "password")

        _neo4j_client = Neo4jClient(neo4j_uri, neo4j_user, neo4j_password)

    return _neo4j_client


def cleanup_connections():
    """Clean up global connections on application shutdown"""
    global _neo4j_client
    if _neo4j_client is not None:
        _neo4j_client.close()
        _neo4j_client = None


