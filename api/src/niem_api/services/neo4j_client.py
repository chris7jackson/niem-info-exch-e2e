#!/usr/bin/env python3

import logging
import os
from typing import Dict, List, Any, Optional
from neo4j import GraphDatabase
from neo4j.graph import Node, Relationship, Path

logger = logging.getLogger(__name__)


class Neo4jClient:
    """Simplified Neo4j client with built-in graph extraction"""

    def __init__(self, uri: str = None, user: str = None, password: str = None):
        self.uri = uri or os.getenv("NEO4J_URI", "bolt://localhost:7687")
        self.user = user or os.getenv("NEO4J_USER", "neo4j")
        self.password = password or os.getenv("NEO4J_PASSWORD", "password")
        self.driver = GraphDatabase.driver(self.uri, auth=(self.user, self.password))

    def query(self, cypher_query: str, parameters: Optional[Dict] = None) -> List[Dict]:
        """Execute a Cypher query and return raw results"""
        with self.driver.session() as session:
            result = session.run(cypher_query, parameters or {})
            return [record.data() for record in result]

    def query_graph(self, cypher_query: str, parameters: Optional[Dict] = None) -> Dict[str, Any]:
        """Execute a Cypher query and return structured graph data"""
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

    def _extract_graph_elements(self, value: Any, nodes: Dict, relationships: Dict):
        """Extract graph elements from Neo4j result values"""
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

    def get_schema(self) -> Dict[str, List[str]]:
        """Get database schema information"""
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

    def get_stats(self) -> Dict[str, int]:
        """Get database statistics"""
        with self.driver.session() as session:
            node_count = session.run("MATCH (n) RETURN count(n) as count").single()["count"]
            rel_count = session.run("MATCH ()-[r]->() RETURN count(r) as count").single()["count"]

            return {
                "nodeCount": node_count,
                "relationshipCount": rel_count
            }

    def close(self):
        """Close the driver connection"""
        if self.driver:
            self.driver.close()


