#!/usr/bin/env python3

import logging
from typing import Dict, List, Any
from ..core.dependencies import get_neo4j_client

logger = logging.getLogger(__name__)


async def execute_cypher_query(cypher_query: str) -> Dict[str, Any]:
    """Execute a Cypher query and return structured graph data"""
    client = get_neo4j_client()
    try:
        return client.query_graph(cypher_query)
    except Exception as e:
        logger.error(f"Error executing Cypher query: {e}")
        raise


async def get_full_graph(limit: int = 1000) -> Dict[str, Any]:
    """Get the complete graph structure with all nodes and relationships"""
    cypher_query = f"""
    MATCH (n)
    OPTIONAL MATCH (n)-[r]-(m)
    RETURN n, r, m
    LIMIT {limit}
    """
    return await execute_cypher_query(cypher_query)


async def get_node_labels() -> List[str]:
    """Get all node labels in the database"""
    client = get_neo4j_client()
    try:
        schema = client.get_schema()
        return schema["nodeLabels"]
    except Exception as e:
        logger.error(f"Error getting node labels: {e}")
        raise


async def get_relationship_types() -> List[str]:
    """Get all relationship types in the database"""
    client = get_neo4j_client()
    try:
        schema = client.get_schema()
        return schema["relationshipTypes"]
    except Exception as e:
        logger.error(f"Error getting relationship types: {e}")
        raise


async def get_database_summary() -> Dict[str, Any]:
    """Get a comprehensive summary of the database structure"""
    client = get_neo4j_client()
    try:
        stats = client.get_stats()
        schema = client.get_schema()

        return {
            **stats,
            **schema,
            "summary": f"Database contains {stats['nodeCount']} nodes with {len(schema['nodeLabels'])} different types, and {stats['relationshipCount']} relationships of {len(schema['relationshipTypes'])} different types."
        }
    except Exception as e:
        logger.error(f"Error getting database summary: {e}")
        raise