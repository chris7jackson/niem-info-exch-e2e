#!/usr/bin/env python3

import logging
from typing import Dict, List, Any, Set
from neo4j import GraphDatabase
from neo4j.graph import Node, Relationship, Path
import os

logger = logging.getLogger(__name__)

# Neo4j connection settings
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")


def extract_graph_elements(value: Any, nodes: Dict[str, Dict], relationships: Dict[str, Dict]) -> None:
    """
    Recursively extract all nodes and relationships from any Neo4j data type.
    This handles all possible return types: Node, Relationship, Path, List, etc.
    """

    if isinstance(value, Node):
        # Single node
        node_id = str(value.id)
        if node_id not in nodes:
            nodes[node_id] = {
                "id": node_id,
                "label": list(value.labels)[0] if value.labels else "Unknown",
                "labels": list(value.labels),
                "properties": dict(value.items())
            }

    elif isinstance(value, Relationship):
        # Single relationship
        rel_id = str(value.id)
        if rel_id not in relationships:
            # Also ensure start and end nodes are captured
            start_node_id = str(value.start_node.id)
            end_node_id = str(value.end_node.id)

            # Add start node if not already present
            if start_node_id not in nodes:
                start_node = value.start_node
                nodes[start_node_id] = {
                    "id": start_node_id,
                    "label": list(start_node.labels)[0] if start_node.labels else "Unknown",
                    "labels": list(start_node.labels),
                    "properties": dict(start_node.items())
                }

            # Add end node if not already present
            if end_node_id not in nodes:
                end_node = value.end_node
                nodes[end_node_id] = {
                    "id": end_node_id,
                    "label": list(end_node.labels)[0] if end_node.labels else "Unknown",
                    "labels": list(end_node.labels),
                    "properties": dict(end_node.items())
                }

            relationships[rel_id] = {
                "id": rel_id,
                "type": value.type,
                "startNode": start_node_id,
                "endNode": end_node_id,
                "properties": dict(value.items())
            }

    elif isinstance(value, Path):
        # Path contains nodes and relationships
        for node in value.nodes:
            extract_graph_elements(node, nodes, relationships)
        for rel in value.relationships:
            extract_graph_elements(rel, nodes, relationships)

    elif isinstance(value, list):
        # List of any items (could be nodes, relationships, paths, etc.)
        for item in value:
            extract_graph_elements(item, nodes, relationships)

    elif isinstance(value, dict):
        # Dictionary might contain nested graph elements
        for nested_value in value.values():
            extract_graph_elements(nested_value, nodes, relationships)


async def execute_cypher_query(cypher_query: str) -> Dict[str, Any]:
    """
    Execute a Cypher query and return ALL graph data exactly as Neo4j provides it.
    This handles any type of Cypher query return structure without data loss.
    """

    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

    try:
        with driver.session() as session:
            logger.info(f"Executing Cypher query: {cypher_query}")

            result = session.run(cypher_query)

            # Use dictionaries with ID keys to automatically deduplicate
            nodes = {}
            relationships = {}

            # Process all records and extract ALL graph elements
            for record in result:
                # Process each column in the record
                for key, value in record.items():
                    logger.debug(f"Processing column '{key}' with value type: {type(value)}")
                    extract_graph_elements(value, nodes, relationships)

            # Convert to lists for final output
            nodes_list = list(nodes.values())
            relationships_list = list(relationships.values())

            # Get all unique node labels for dynamic configuration
            all_labels = set()
            for node in nodes_list:
                all_labels.update(node["labels"])

            # Get all unique relationship types
            all_relationship_types = set()
            for rel in relationships_list:
                all_relationship_types.add(rel["type"])

            logger.info(f"Query executed successfully: {len(nodes_list)} unique nodes, {len(relationships_list)} unique relationships")
            logger.info(f"Node labels found: {sorted(list(all_labels))}")
            logger.info(f"Relationship types found: {sorted(list(all_relationship_types))}")

            return {
                "nodes": nodes_list,
                "relationships": relationships_list,
                "metadata": {
                    "nodeLabels": sorted(list(all_labels)),
                    "relationshipTypes": sorted(list(all_relationship_types)),
                    "nodeCount": len(nodes_list),
                    "relationshipCount": len(relationships_list)
                }
            }

    except Exception as e:
        logger.error(f"Error executing Cypher query: {e}")
        raise

    finally:
        driver.close()


async def get_full_graph(limit: int = 1000) -> Dict[str, Any]:
    """
    Get the complete graph structure with all nodes and relationships.
    This is the most direct way to see everything in Neo4j.
    """

    # Get all nodes and all relationships separately to ensure nothing is missed
    cypher_query = f"""
    MATCH (n)
    OPTIONAL MATCH (n)-[r]-(m)
    RETURN n, r, m
    LIMIT {limit}
    """

    return await execute_cypher_query(cypher_query)


async def get_node_labels() -> List[str]:
    """Get all node labels in the database"""

    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

    try:
        with driver.session() as session:
            result = session.run("CALL db.labels()")
            labels = [record["label"] for record in result]
            return sorted(labels)

    except Exception as e:
        logger.error(f"Error getting node labels: {e}")
        raise

    finally:
        driver.close()


async def get_relationship_types() -> List[str]:
    """Get all relationship types in the database"""

    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

    try:
        with driver.session() as session:
            result = session.run("CALL db.relationshipTypes()")
            types = [record["relationshipType"] for record in result]
            return sorted(types)

    except Exception as e:
        logger.error(f"Error getting relationship types: {e}")
        raise

    finally:
        driver.close()


async def get_database_summary() -> Dict[str, Any]:
    """Get a comprehensive summary of the database structure"""

    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

    try:
        with driver.session() as session:
            # Get counts
            node_count_result = session.run("MATCH (n) RETURN count(n) as count")
            node_count = node_count_result.single()["count"]

            rel_count_result = session.run("MATCH ()-[r]->() RETURN count(r) as count")
            rel_count = rel_count_result.single()["count"]

            # Get schema info
            labels = await get_node_labels()
            rel_types = await get_relationship_types()

            return {
                "nodeCount": node_count,
                "relationshipCount": rel_count,
                "nodeLabels": labels,
                "relationshipTypes": rel_types,
                "summary": f"Database contains {node_count} nodes with {len(labels)} different types, and {rel_count} relationships of {len(rel_types)} different types."
            }

    except Exception as e:
        logger.error(f"Error getting database summary: {e}")
        raise

    finally:
        driver.close()