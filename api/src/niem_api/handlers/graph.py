#!/usr/bin/env python3

import logging
from typing import Dict, List, Any
from ..core.dependencies import get_neo4j_client

logger = logging.getLogger(__name__)


def execute_cypher_query(cypher_query: str = None, limit: int = None) -> Dict[str, Any]:
    """
    Execute a Cypher query and return structured graph data.

    Args:
        cypher_query: Optional Cypher query. Defaults to basic graph query if not provided.
        limit: Optional maximum number of results to return. Defaults to 100 if not provided.
               Applied only if query doesn't already have LIMIT.

    Returns:
        Dictionary with status and graph data (nodes, relationships, metadata)
    """
    # Default limit if not provided
    if limit is None:
        limit = 1000

    # Default query if none provided
    if not cypher_query:
        cypher_query = "MATCH (n)-[r]->(m) RETURN n, r, m"

    # Add limit if not already present in query
    if "LIMIT" not in cypher_query.upper() and limit:
        cypher_query += f" LIMIT {limit}"

    client = get_neo4j_client()
    try:
        result = client.query_graph(cypher_query)
        return {
            "status": "success",
            "data": result
        }
    except Exception as e:
        logger.error(f"Error executing Cypher query: {e}")
        raise


def get_full_graph(limit: int = 1000) -> Dict[str, Any]:
    """
    Get the complete graph structure with all nodes and relationships.

    Args:
        limit: Maximum number of results to return

    Returns:
        Dictionary with status and graph data
    """
    cypher_query = f"""
    MATCH (n)
    OPTIONAL MATCH (n)-[r]-(m)
    RETURN n, r, m
    LIMIT {limit}
    """
    # execute_cypher_query already returns formatted response
    return execute_cypher_query(cypher_query)


def get_node_labels() -> List[str]:
    """Get all node labels in the database"""
    client = get_neo4j_client()
    try:
        schema = client.get_schema()
        return schema["nodeLabels"]
    except Exception as e:
        logger.error(f"Error getting node labels: {e}")
        raise


def get_relationship_types() -> List[str]:
    """Get all relationship types in the database"""
    client = get_neo4j_client()
    try:
        schema = client.get_schema()
        return schema["relationshipTypes"]
    except Exception as e:
        logger.error(f"Error getting relationship types: {e}")
        raise