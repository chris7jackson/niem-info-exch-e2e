#!/usr/bin/env python3
"""
Neo4j Database Client

A low-level client wrapper for Neo4j graph database operations.
Handles connection management and query execution with structured result extraction.

This client is pure infrastructure - it contains no business logic.
Use services layer for business logic that uses this client.
"""

import logging
import os
from typing import Any

from neo4j import GraphDatabase
from neo4j.graph import Node, Path, Relationship

logger = logging.getLogger(__name__)


class Neo4jClient:
    """
    Neo4j database client with connection pooling and result extraction.

    Provides methods for:
    - Executing Cypher queries
    - Extracting graph structures (nodes, relationships, paths)
    - Retrieving database schema and statistics

    Example:
        ```python
        client = Neo4jClient()
        results = client.query("MATCH (n:Person) RETURN n LIMIT 10")
        graph = client.query_graph("MATCH (n)-[r]->(m) RETURN n, r, m LIMIT 50")
        client.close()
        ```

    Environment Variables:
        - NEO4J_URI: Database connection URI (default: bolt://localhost:7687)
        - NEO4J_USER: Authentication username (default: neo4j)
        - NEO4J_PASSWORD: Authentication password (default: password)
    """

    def __init__(self, uri: str = None, user: str = None, password: str = None):
        """
        Initialize Neo4j client with connection parameters.

        Args:
            uri: Database connection URI. If None, reads from NEO4J_URI env var.
            user: Authentication username. If None, reads from NEO4J_USER env var.
            password: Authentication password. If None, reads from NEO4J_PASSWORD env var.

        Raises:
            neo4j.exceptions.ServiceUnavailable: If cannot connect to database
        """
        self.uri = uri or os.getenv("NEO4J_URI", "bolt://localhost:7687")
        self.user = user or os.getenv("NEO4J_USER", "neo4j")
        self.password = password or os.getenv("NEO4J_PASSWORD", "password")
        self.driver = GraphDatabase.driver(self.uri, auth=(self.user, self.password))

    def query(self, cypher_query: str, parameters: dict | None = None) -> list[dict]:
        """
        Execute a Cypher query and return raw record data.

        Args:
            cypher_query: Cypher query string to execute
            parameters: Optional query parameters for parameterized queries

        Returns:
            List of dictionaries containing query result records.
            Each record is a dict mapping column names to values.

        Example:
            ```python
            results = client.query(
                "MATCH (n:Person {name: $name}) RETURN n.age as age",
                parameters={"name": "John"}
            )
            # Returns: [{"age": 30}]
            ```

        Raises:
            neo4j.exceptions.CypherSyntaxError: If query syntax is invalid
            neo4j.exceptions.ClientError: If query execution fails
        """
        with self.driver.session() as session:
            result = session.run(cypher_query, parameters or {})
            return [record.data() for record in result]

    def query_graph(self, cypher_query: str, parameters: dict | None = None) -> dict[str, Any]:
        """
        Execute a Cypher query and return structured graph data.

        Extracts nodes, relationships, and paths from query results into a
        structured format suitable for graph visualization.

        Args:
            cypher_query: Cypher query string to execute
            parameters: Optional query parameters

        Returns:
            Dictionary with keys:
            - nodes: List of node dicts with {id, label, labels, properties}
            - relationships: List of relationship dicts with {id, type, startNode, endNode, properties}
            - metadata: Summary with {nodeLabels, relationshipTypes, nodeCount, relationshipCount}

        Example:
            ```python
            graph = client.query_graph("MATCH (n)-[r]->(m) RETURN n, r, m LIMIT 10")
            print(f"Found {len(graph['nodes'])} nodes and {len(graph['relationships'])} edges")
            ```

        Raises:
            neo4j.exceptions.CypherSyntaxError: If query syntax is invalid
            neo4j.exceptions.ClientError: If query execution fails
        """
        with self.driver.session() as session:
            logger.info(f"Executing Cypher query: {cypher_query}")
            result = session.run(cypher_query, parameters or {})

            nodes = {}
            relationships = {}

            for record in result:
                for key, value in record.items():
                    self._extract_graph_elements(value, nodes, relationships)

            # Convert to lists and add metadata
            nodes_list = list(nodes.values())
            relationships_list = list(relationships.values())

            # Get metadata
            all_labels = set()
            for node in nodes_list:
                all_labels.update(node["labels"])

            all_rel_types = {rel["type"] for rel in relationships_list}

            return {
                "nodes": nodes_list,
                "relationships": relationships_list,
                "metadata": {
                    "nodeLabels": sorted(list(all_labels)),
                    "relationshipTypes": sorted(list(all_rel_types)),
                    "nodeCount": len(nodes_list),
                    "relationshipCount": len(relationships_list)
                }
            }

    def _extract_graph_elements(self, value: Any, nodes: dict, relationships: dict):
        """
        Recursively extract graph elements from Neo4j result values.

        Handles Neo4j types: Node, Relationship, Path, and nested collections.
        Populates nodes and relationships dicts with unique elements.

        Args:
            value: Value from Neo4j query result (can be Node, Relationship, Path, list, dict)
            nodes: Dict to populate with nodes (keyed by node ID)
            relationships: Dict to populate with relationships (keyed by relationship ID)
        """
        if isinstance(value, Node):
            node_id = str(value.id)
            if node_id not in nodes:
                nodes[node_id] = {
                    "id": node_id,
                    "label": list(value.labels)[0] if value.labels else "Unknown",
                    "labels": list(value.labels),
                    "properties": dict(value.items())
                }

        elif isinstance(value, Relationship):
            rel_id = str(value.id)
            if rel_id not in relationships:
                start_id = str(value.start_node.id)
                end_id = str(value.end_node.id)

                # Ensure start and end nodes are captured
                self._extract_graph_elements(value.start_node, nodes, relationships)
                self._extract_graph_elements(value.end_node, nodes, relationships)

                relationships[rel_id] = {
                    "id": rel_id,
                    "type": value.type,
                    "startNode": start_id,
                    "endNode": end_id,
                    "properties": dict(value.items())
                }

        elif isinstance(value, Path):
            for node in value.nodes:
                self._extract_graph_elements(node, nodes, relationships)
            for rel in value.relationships:
                self._extract_graph_elements(rel, nodes, relationships)

        elif isinstance(value, list):
            for item in value:
                self._extract_graph_elements(item, nodes, relationships)

        elif isinstance(value, dict):
            for nested_value in value.values():
                self._extract_graph_elements(nested_value, nodes, relationships)

    def get_schema(self) -> dict[str, list[str]]:
        """
        Get database schema information (labels and relationship types).

        Returns:
            Dictionary with keys:
            - nodeLabels: Sorted list of all node labels in database
            - relationshipTypes: Sorted list of all relationship types in database

        Example:
            ```python
            schema = client.get_schema()
            print(f"Node types: {schema['nodeLabels']}")
            print(f"Edge types: {schema['relationshipTypes']}")
            ```

        Raises:
            neo4j.exceptions.ClientError: If database procedures fail
        """
        with self.driver.session() as session:
            # Get node labels
            labels_result = session.run("CALL db.labels()")
            labels = [record["label"] for record in labels_result]

            # Get relationship types
            types_result = session.run("CALL db.relationshipTypes()")
            rel_types = [record["relationshipType"] for record in types_result]

            return {
                "nodeLabels": sorted(labels),
                "relationshipTypes": sorted(rel_types)
            }

    def get_stats(self) -> dict[str, int]:
        """
        Get database statistics (node and relationship counts).

        Returns:
            Dictionary with keys:
            - nodeCount: Total number of nodes in database
            - relationshipCount: Total number of relationships in database

        Example:
            ```python
            stats = client.get_stats()
            print(f"Database has {stats['nodeCount']} nodes and {stats['relationshipCount']} edges")
            ```

        Note:
            This performs full database scans and can be slow on large databases.
        """
        with self.driver.session() as session:
            node_count = session.run("MATCH (n) RETURN count(n) as count").single()["count"]
            rel_count = session.run("MATCH ()-[r]->() RETURN count(r) as count").single()["count"]

            return {
                "nodeCount": node_count,
                "relationshipCount": rel_count
            }

    def close(self):
        """
        Close the driver connection and release resources.

        Should be called when client is no longer needed.
        Connection will be unusable after calling this method.

        Example:
            ```python
            client = Neo4jClient()
            try:
                # Use client
                results = client.query("MATCH (n) RETURN n LIMIT 1")
            finally:
                client.close()
            ```
        """
        if self.driver:
            self.driver.close()
