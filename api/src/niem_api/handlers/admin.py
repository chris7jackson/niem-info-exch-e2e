#!/usr/bin/env python3

import logging
import secrets
from typing import Any

from fastapi import HTTPException
from minio import Minio

from ..models.models import ResetRequest, ResetResponse

logger = logging.getLogger(__name__)


def handle_reset(
    request: ResetRequest,
    s3: Minio
) -> ResetResponse:
    """Handle system reset"""
    try:
        counts = {}

        # Get current counts
        if request.schemas:
            counts["schemas"] = count_schemas(s3)

        if request.data:
            data_counts = count_data_files(s3)
            counts.update(data_counts)

        if request.neo4j:
            neo4j_result = count_neo4j_objects()
            # Extract only the numeric stats, not the status field
            if "stats" in neo4j_result:
                counts.update({f"neo4j_{k}": v for k, v in neo4j_result["stats"].items()})


        if request.dry_run:
            confirm_token = secrets.token_urlsafe(32)
            return ResetResponse(
                counts=counts,
                confirm_token=confirm_token,
                message="Dry run completed. Use confirm_token to execute reset."
            )

        # Validate confirm token
        if not request.confirm_token:
            raise HTTPException(status_code=400, detail="confirm_token required for actual reset")

        # Execute reset operations
        if request.schemas:
            reset_schemas(s3)

        if request.data:
            reset_data_files(s3)

        if request.neo4j:
            reset_neo4j()

        return ResetResponse(
            counts=counts,
            message="Reset completed successfully"
        )

    except Exception as e:
        logger.error(f"Reset failed: {e}")
        if isinstance(e, HTTPException):
            raise
        raise HTTPException(status_code=500, detail=f"Reset failed: {str(e)}") from e


def count_minio_objects(s3: Minio) -> dict[str, int]:
    """Count objects and buckets in MinIO"""
    try:
        total_objects = 0
        bucket_count = 0
        from ..clients.s3_client import BUCKETS
        for bucket in BUCKETS:
            if s3.bucket_exists(bucket):
                bucket_count += 1
                objects = s3.list_objects(bucket, recursive=True)
                total_objects += sum(1 for _ in objects)
        return {"objects": total_objects, "buckets": bucket_count}
    except Exception as e:
        logger.error(f"Failed to count MinIO objects: {e}")
        return {"objects": 0, "buckets": 0}




def reset_minio(s3: Minio):
    """Reset MinIO buckets - remove all objects and delete the buckets themselves, then recreate them"""
    try:
        from ..clients.s3_client import BUCKETS
        for bucket in BUCKETS:
            if s3.bucket_exists(bucket):
                # First remove all objects
                objects = s3.list_objects(bucket, recursive=True)
                for obj in objects:
                    s3.remove_object(bucket, obj.object_name)
                logger.info(f"Removed all objects from bucket: {bucket}")

                # Then remove the bucket itself
                s3.remove_bucket(bucket)
                logger.info(f"Removed bucket: {bucket}")

        # Recreate all required buckets
        for bucket in BUCKETS:
            s3.make_bucket(bucket)
            logger.info(f"Recreated bucket: {bucket}")

        logger.info("MinIO reset completed - all buckets reset and recreated")
    except Exception as e:
        logger.error(f"MinIO reset failed: {e}")
        raise




def count_schemas(s3: Minio) -> int:
    """Count schema folders in niem-schemas bucket"""
    try:
        if not s3.bucket_exists("niem-schemas"):
            return 0
        # List top-level folders (prefixes) only
        objects = s3.list_objects("niem-schemas", recursive=False)
        folders = set()
        for obj in objects:
            # Each object_name is a path like "schema-name/file.xsd"
            # Extract the folder name (first part before /)
            if obj.is_dir or '/' in obj.object_name:
                folder = obj.object_name.split('/')[0]
                folders.add(folder)
        return len(folders)
    except Exception as e:
        logger.error(f"Failed to count schemas: {e}")
        return 0


def count_data_files(s3: Minio) -> dict[str, int]:
    """Count XML and JSON data files in niem-data bucket"""
    try:
        if not s3.bucket_exists("niem-data"):
            return {"xml_files": 0, "json_files": 0, "total_files": 0}

        objects = s3.list_objects("niem-data", recursive=True)
        xml_count = 0
        json_count = 0

        for obj in objects:
            name_lower = obj.object_name.lower()
            if name_lower.endswith('.xml'):
                xml_count += 1
            elif name_lower.endswith('.json'):
                json_count += 1

        return {
            "xml_files": xml_count,
            "json_files": json_count,
            "total_files": xml_count + json_count
        }
    except Exception as e:
        logger.error(f"Failed to count data files: {e}")
        return {"xml_files": 0, "json_files": 0, "total_files": 0}


def reset_schemas(s3: Minio):
    """Reset only schemas in niem-schemas bucket"""
    try:
        if s3.bucket_exists("niem-schemas"):
            # Remove all objects in schemas bucket
            objects = s3.list_objects("niem-schemas", recursive=True)
            for obj in objects:
                s3.remove_object("niem-schemas", obj.object_name)
            logger.info("Removed all schemas from niem-schemas bucket")
        else:
            logger.info("niem-schemas bucket does not exist")
    except Exception as e:
        logger.error(f"Schema reset failed: {e}")
        raise


def reset_data_files(s3: Minio):
    """Reset only data files in niem-data bucket"""
    try:
        if s3.bucket_exists("niem-data"):
            # Remove all objects in data bucket
            objects = s3.list_objects("niem-data", recursive=True)
            for obj in objects:
                s3.remove_object("niem-data", obj.object_name)
            logger.info("Removed all data files from niem-data bucket")
        else:
            logger.info("niem-data bucket does not exist")
    except Exception as e:
        logger.error(f"Data files reset failed: {e}")
        raise


def reset_neo4j():
    """Reset Neo4j database - delete all nodes and relationships"""
    try:
        from ..core.dependencies import get_neo4j_client

        neo4j_client = get_neo4j_client()

        # Delete all nodes and relationships
        neo4j_client.query("MATCH (n) DETACH DELETE n")
        logger.info("Deleted all nodes and relationships from Neo4j")

    except Exception as e:
        logger.error(f"Neo4j reset failed: {e}")
        raise


def count_neo4j_objects() -> dict[str, Any]:
    """
    Count Neo4j nodes, relationships, indexes, and constraints.

    Returns:
        Dictionary with status and statistics

    Raises:
        HTTPException: If counting fails
    """
    try:
        from ..core.dependencies import get_neo4j_client

        neo4j_client = get_neo4j_client()

        # Get counts
        node_count_result = neo4j_client.query("MATCH (n) RETURN count(n) as count")
        node_count = node_count_result[0]["count"]

        rel_count_result = neo4j_client.query("MATCH ()-[r]->() RETURN count(r) as count")
        rel_count = rel_count_result[0]["count"]

        # Get schema counts
        indexes = neo4j_client.query("SHOW INDEXES")
        constraints = neo4j_client.query("SHOW CONSTRAINTS")

        # Filter out built-in indexes
        user_indexes = [idx for idx in indexes if idx.get("type", "").lower() not in ["lookup", "token"]]

        return {
            "status": "success",
            "stats": {
                "nodes": node_count,
                "relationships": rel_count,
                "indexes": len(user_indexes),
                "constraints": len(constraints)
            }
        }
    except Exception as e:
        logger.error(f"Failed to count Neo4j objects: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get Neo4j stats: {str(e)}") from e




