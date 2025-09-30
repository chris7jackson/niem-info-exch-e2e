"""
Client Layer

This package contains low-level client wrappers for external services.
Clients handle communication with external systems but contain no business logic.

Modules:
- neo4j_client: Neo4j graph database client
- s3_client: MinIO/S3 object storage client
- cmf_client: NIEM CMF tool wrapper
"""

from .neo4j_client import Neo4jClient
from .s3_client import create_buckets, upload_file, download_file, list_files, BUCKETS
from .cmf_client import (
    CMFError,
    is_cmf_available,
    get_cmf_version,
    download_and_setup_cmf,
    run_cmf_command
)

__all__ = [
    # Neo4j client
    'Neo4jClient',
    # S3 client
    'create_buckets',
    'upload_file',
    'download_file',
    'list_files',
    'BUCKETS',
    # CMF client
    'CMFError',
    'is_cmf_available',
    'get_cmf_version',
    'download_and_setup_cmf',
    'run_cmf_command',
]
