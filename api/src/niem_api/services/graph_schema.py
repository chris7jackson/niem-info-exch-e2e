#!/usr/bin/env python3

import json
import logging
from typing import Dict, List, Any

from neo4j import GraphDatabase
from neo4j.exceptions import ClientError

logger = logging.getLogger(__name__)


class GraphSchemaManager:
    """Manages Neo4j database schema configuration from mapping specifications"""

    def __init__(self, neo4j_uri: str, neo4j_user: str, neo4j_password: str):
        self.driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))

    def close(self):
        """Close the Neo4j driver"""
        if self.driver:
            self.driver.close()

    def configure_schema_from_mapping(self, mapping: Dict[str, Any]) -> Dict[str, Any]:
        """Configure Neo4j schema (indexes, constraints) from mapping specification"""
        logger.info("Configuring Neo4j schema from mapping specification")

        results = {
            "indexes_created": [],
            "constraints_created": [],
            "indexes_failed": [],
            "constraints_failed": [],
            "labels_identified": [],
            "relationship_types_identified": []
        }

        try:
            with self.driver.session() as session:
                # Extract labels and relationship types
                results["labels_identified"] = [node["label"] for node in mapping.get("nodes", [])]
                results["relationship_types_identified"] = [rel["type"] for rel in mapping.get("relationships", [])]

                # Create uniqueness constraints for ID properties (constraints include indexes)
                id_properties_handled = set()

                for node in mapping.get("nodes", []):
                    label = node["label"]

                    # Look for ID properties that should be unique
                    id_props = [p for p in node.get("props", []) if p["name"] == "id"]

                    for prop_info in id_props:
                        prop_name = prop_info["name"]
                        property_key = f"{label}.{prop_name}"

                        try:
                            result = self._create_unique_constraint(session, label, prop_name)
                            if result:
                                results["constraints_created"].append(f"{label}.{prop_name} UNIQUE")
                                id_properties_handled.add(property_key)
                        except Exception as e:
                            logger.warning(f"Failed to create constraint on {label}.{prop_name}: {e}")
                            results["constraints_failed"].append(f"{label}.{prop_name}: {str(e)}")

                # Create indexes for non-ID properties from mapping specification
                for index_spec in mapping.get("indexes", []):
                    label = index_spec["label"]
                    properties = index_spec["properties"]

                    for prop in properties:
                        property_key = f"{label}.{prop}"

                        # Skip if we already created a constraint for this property (constraints include indexes)
                        if property_key in id_properties_handled:
                            continue

                        try:
                            result = self._create_index(session, label, prop)
                            if result:
                                results["indexes_created"].append(f"{label}.{prop}")
                        except Exception as e:
                            logger.warning(f"Failed to create index on {label}.{prop}: {e}")
                            results["indexes_failed"].append(f"{label}.{prop}: {str(e)}")

                logger.info(f"Schema configuration completed: {len(results['indexes_created'])} indexes, {len(results['constraints_created'])} constraints")
                return results

        except Exception as e:
            logger.error(f"Failed to configure schema: {e}")
            results["error"] = str(e)
            return results

    def _create_index(self, session, label: str, property_name: str) -> bool:
        """Create an index on a label/property combination"""
        try:
            # Check if index already exists
            existing_indexes = session.run("SHOW INDEXES").data()
            for index in existing_indexes:
                if (index.get("labelsOrTypes") == [label] and
                    index.get("properties") == [property_name]):
                    logger.debug(f"Index on {label}.{property_name} already exists")
                    return False

            # Create the index
            query = f"CREATE INDEX IF NOT EXISTS FOR (n:{label}) ON (n.{property_name})"
            session.run(query)
            logger.info(f"Created index on {label}.{property_name}")
            return True

        except ClientError as e:
            if "equivalent index already exists" in str(e).lower():
                logger.debug(f"Index on {label}.{property_name} already exists")
                return False
            raise

    def _create_unique_constraint(self, session, label: str, property_name: str) -> bool:
        """Create a uniqueness constraint on a label/property combination"""
        try:
            # Check if constraint already exists
            existing_constraints = session.run("SHOW CONSTRAINTS").data()
            for constraint in existing_constraints:
                if (constraint.get("labelsOrTypes") == [label] and
                    constraint.get("properties") == [property_name] and
                    constraint.get("type") == "UNIQUENESS"):
                    logger.debug(f"Unique constraint on {label}.{property_name} already exists")
                    return False

            # Check if an index exists that would conflict
            existing_indexes = session.run("SHOW INDEXES").data()
            index_exists = False
            index_name = None

            for index in existing_indexes:
                if (index.get("labelsOrTypes") == [label] and
                    index.get("properties") == [property_name] and
                    index.get("type") != "RANGE"):  # Skip built-in range indexes
                    index_exists = True
                    index_name = index.get("name")
                    break

            # If a conflicting index exists, drop it first
            if index_exists and index_name:
                logger.info(f"Dropping existing index {index_name} to create unique constraint")
                session.run(f"DROP INDEX {index_name}")

            # Create the constraint
            query = f"CREATE CONSTRAINT IF NOT EXISTS FOR (n:{label}) REQUIRE n.{property_name} IS UNIQUE"
            session.run(query)
            logger.info(f"Created unique constraint on {label}.{property_name}")
            return True

        except ClientError as e:
            if "equivalent constraint already exists" in str(e).lower():
                logger.debug(f"Unique constraint on {label}.{property_name} already exists")
                return False
            raise

    def get_current_schema_info(self) -> Dict[str, Any]:
        """Get current Neo4j schema information"""
        try:
            with self.driver.session() as session:
                # Get indexes
                indexes = session.run("SHOW INDEXES").data()

                # Get constraints
                constraints = session.run("SHOW CONSTRAINTS").data()

                # Get labels
                labels_result = session.run("CALL db.labels()").data()
                labels = [record["label"] for record in labels_result]

                # Get relationship types
                rel_types_result = session.run("CALL db.relationshipTypes()").data()
                relationship_types = [record["relationshipType"] for record in rel_types_result]

                return {
                    "indexes": indexes,
                    "constraints": constraints,
                    "labels": labels,
                    "relationship_types": relationship_types
                }
        except Exception as e:
            logger.error(f"Failed to get schema info: {e}")
            return {"error": str(e)}

    def reset_schema(self, confirm_reset: bool = False) -> Dict[str, Any]:
        """Reset the Neo4j schema (DROP ALL CONSTRAINTS AND INDEXES)"""
        if not confirm_reset:
            return {"error": "Reset requires explicit confirmation"}

        logger.warning("Resetting Neo4j schema - dropping all constraints and indexes")

        try:
            with self.driver.session() as session:
                dropped_constraints = []
                dropped_indexes = []

                # Drop all constraints
                constraints = session.run("SHOW CONSTRAINTS").data()
                for constraint in constraints:
                    constraint_name = constraint.get("name")
                    if constraint_name:
                        session.run(f"DROP CONSTRAINT {constraint_name}")
                        dropped_constraints.append(constraint_name)

                # Drop all indexes (except built-in ones)
                indexes = session.run("SHOW INDEXES").data()
                for index in indexes:
                    index_name = index.get("name")
                    index_type = index.get("type", "").lower()

                    # Skip built-in indexes
                    if index_name and "token" not in index_type and "lookup" not in index_type:
                        try:
                            session.run(f"DROP INDEX {index_name}")
                            dropped_indexes.append(index_name)
                        except ClientError as e:
                            logger.warning(f"Could not drop index {index_name}: {e}")

                logger.info(f"Schema reset completed: dropped {len(dropped_constraints)} constraints, {len(dropped_indexes)} indexes")

                return {
                    "dropped_constraints": dropped_constraints,
                    "dropped_indexes": dropped_indexes
                }

        except Exception as e:
            logger.error(f"Failed to reset schema: {e}")
            return {"error": str(e)}


def get_graph_schema_manager() -> GraphSchemaManager:
    """Get a GraphSchemaManager instance with environment configuration"""
    import os

    neo4j_uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    neo4j_user = os.getenv("NEO4J_USER", "neo4j")
    neo4j_password = os.getenv("NEO4J_PASSWORD", "password")

    return GraphSchemaManager(neo4j_uri, neo4j_user, neo4j_password)