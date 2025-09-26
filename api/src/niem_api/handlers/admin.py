#!/usr/bin/env python3

import logging
import secrets
from typing import Dict

from fastapi import HTTPException
from minio import Minio

from ..models.models import ResetRequest, ResetResponse

logger = logging.getLogger(__name__)


async def handle_reset(
    request: ResetRequest,
    s3: Minio
) -> ResetResponse:
    """Handle system reset"""
    try:
        counts = {}

        # Get current counts
        if request.schemas:
            counts["schemas"] = await count_schemas(s3)

        if request.data:
            data_counts = await count_data_files(s3)
            counts.update(data_counts)

        if request.neo4j:
            neo4j_counts = await count_neo4j_objects()
            counts.update({f"neo4j_{k}": v for k, v in neo4j_counts.items()})


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
            await reset_schemas(s3)

        if request.data:
            await reset_data_files(s3)

        if request.neo4j:
            await reset_neo4j()

        return ResetResponse(
            counts=counts,
            message="Reset completed successfully"
        )

    except Exception as e:
        logger.error(f"Reset failed: {e}")
        if isinstance(e, HTTPException):
            raise
        raise HTTPException(status_code=500, detail=f"Reset failed: {str(e)}")


async def count_minio_objects(s3: Minio) -> Dict[str, int]:
    """Count objects and buckets in MinIO"""
    try:
        total_objects = 0
        bucket_count = 0
        from ..services.storage import BUCKETS
        for bucket in BUCKETS:
            if s3.bucket_exists(bucket):
                bucket_count += 1
                objects = s3.list_objects(bucket, recursive=True)
                total_objects += sum(1 for _ in objects)
        return {"objects": total_objects, "buckets": bucket_count}
    except Exception as e:
        logger.error(f"Failed to count MinIO objects: {e}")
        return {"objects": 0, "buckets": 0}




async def reset_minio(s3: Minio):
    """Reset MinIO buckets - remove all objects and delete the buckets themselves, then recreate them"""
    try:
        from ..services.storage import BUCKETS
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




async def count_schemas(s3: Minio) -> int:
    """Count uploaded schemas in niem-schemas bucket"""
    try:
        if not s3.bucket_exists("niem-schemas"):
            return 0
        objects = s3.list_objects("niem-schemas", recursive=True)
        return sum(1 for _ in objects)
    except Exception as e:
        logger.error(f"Failed to count schemas: {e}")
        return 0


async def count_data_files(s3: Minio) -> Dict[str, int]:
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


async def reset_schemas(s3: Minio):
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


async def reset_data_files(s3: Minio):
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


async def reset_neo4j():
    """Reset Neo4j database - clear all data and schema"""
    try:
        from ..services.graph_schema import get_graph_schema_manager

        graph_manager = get_graph_schema_manager()

        # Clear all data
        with graph_manager.driver.session() as session:
            # Delete all nodes and relationships
            session.run("MATCH (n) DETACH DELETE n")
            logger.info("Cleared all Neo4j data (nodes and relationships)")

        # Reset schema (indexes and constraints)
        result = graph_manager.reset_schema(confirm_reset=True)
        if "error" in result:
            raise Exception(f"Schema reset failed: {result['error']}")

        graph_manager.close()
        logger.info("Neo4j reset completed")
    except Exception as e:
        logger.error(f"Neo4j reset failed: {e}")
        raise


async def clear_neo4j_schema():
    """Clear Neo4j schema (indexes and constraints) only"""
    try:
        from ..services.graph_schema import get_graph_schema_manager

        graph_manager = get_graph_schema_manager()
        result = graph_manager.reset_schema(confirm_reset=True)
        graph_manager.close()

        if "error" in result:
            raise Exception(f"Schema clear failed: {result['error']}")

        logger.info(f"Neo4j schema cleared: {len(result.get('dropped_constraints', []))} constraints, {len(result.get('dropped_indexes', []))} indexes")
        return result
    except Exception as e:
        logger.error(f"Neo4j schema clear failed: {e}")
        raise


async def clear_neo4j_data():
    """Clear Neo4j data (nodes and relationships) only"""
    try:
        from ..services.graph_schema import get_graph_schema_manager

        graph_manager = get_graph_schema_manager()

        with graph_manager.driver.session() as session:
            # Get counts before deletion
            node_count = session.run("MATCH (n) RETURN count(n) as count").single()["count"]
            rel_count = session.run("MATCH ()-[r]->() RETURN count(r) as count").single()["count"]

            # Delete all nodes and relationships
            session.run("MATCH (n) DETACH DELETE n")

            logger.info(f"Cleared Neo4j data: {node_count} nodes, {rel_count} relationships")

        graph_manager.close()
        return {"nodes_deleted": node_count, "relationships_deleted": rel_count}
    except Exception as e:
        logger.error(f"Neo4j data clear failed: {e}")
        raise


async def count_neo4j_objects():
    """Count Neo4j nodes and relationships"""
    try:
        from ..services.graph_schema import get_graph_schema_manager

        graph_manager = get_graph_schema_manager()

        with graph_manager.driver.session() as session:
            node_count = session.run("MATCH (n) RETURN count(n) as count").single()["count"]
            rel_count = session.run("MATCH ()-[r]->() RETURN count(r) as count").single()["count"]

            # Get schema counts
            indexes = session.run("SHOW INDEXES").data()
            constraints = session.run("SHOW CONSTRAINTS").data()

            # Filter out built-in indexes
            user_indexes = [idx for idx in indexes if idx.get("type", "").lower() not in ["lookup", "token"]]

        graph_manager.close()

        return {
            "nodes": node_count,
            "relationships": rel_count,
            "indexes": len(user_indexes),
            "constraints": len(constraints)
        }
    except Exception as e:
        logger.error(f"Failed to count Neo4j objects: {e}")
        return {"nodes": 0, "relationships": 0, "indexes": 0, "constraints": 0}


