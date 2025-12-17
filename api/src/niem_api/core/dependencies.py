#!/usr/bin/env python3

import os

from minio import Minio

from .env_utils import getenv_clean, getenv_bool, getenv_int


def get_s3_client():
    """Get MinIO/S3 client"""
    endpoint = getenv_clean("MINIO_ENDPOINT", "localhost:9000")
    access_key = getenv_clean("MINIO_ACCESS_KEY", "minio")
    secret_key = getenv_clean("MINIO_SECRET_KEY", "minio123")
    secure = getenv_bool("MINIO_SECURE", False)

    # Remove http:// or https:// from endpoint if present
    if endpoint.startswith("http://"):
        endpoint = endpoint[7:]
        secure = False
    elif endpoint.startswith("https://"):
        endpoint = endpoint[8:]
        secure = True

    return Minio(endpoint, access_key=access_key, secret_key=secret_key, secure=secure)


# Global Neo4j client instance
_neo4j_client = None


def get_neo4j_client():
    """Get or create global Neo4j client instance"""
    global _neo4j_client
    if _neo4j_client is None:
        from ..clients.neo4j_client import Neo4jClient

        neo4j_uri = getenv_clean("NEO4J_URI", "bolt://localhost:7687")
        neo4j_user = getenv_clean("NEO4J_USER", "neo4j")
        neo4j_password = getenv_clean("NEO4J_PASSWORD", "password")

        _neo4j_client = Neo4jClient(neo4j_uri, neo4j_user, neo4j_password)

    return _neo4j_client


# Global Postgres client instance
_postgres_client = None


def get_postgres_client():
    """Get or create global Postgres client instance"""
    global _postgres_client
    if _postgres_client is None:
        from ..clients.postgres_client import PostgresClient

        postgres_host = getenv_clean("POSTGRES_HOST", "localhost")
        postgres_port = getenv_int("POSTGRES_PORT", 5432)
        postgres_db = getenv_clean("POSTGRES_DB", "senzing")
        postgres_user = getenv_clean("POSTGRES_USER", "senzing")
        postgres_password = getenv_clean("POSTGRES_PASSWORD", "changeme")

        _postgres_client = PostgresClient(
            host=postgres_host,
            port=postgres_port,
            database=postgres_db,
            user=postgres_user,
            password=postgres_password,
        )

    return _postgres_client


def cleanup_connections():
    """Clean up global connections on application shutdown"""
    global _neo4j_client, _postgres_client
    if _neo4j_client is not None:
        _neo4j_client.close()
        _neo4j_client = None
    if _postgres_client is not None:
        _postgres_client.close()
        _postgres_client = None
