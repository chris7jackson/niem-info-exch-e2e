#!/usr/bin/env python3

import pytest
import os
from neo4j import GraphDatabase


@pytest.mark.integration
class TestNeo4jIntegration:
    """Integration tests for Neo4j database operations"""

    @pytest.fixture
    def neo4j_driver(self):
        """Neo4j driver connected to service (GitHub Actions or local)"""
        uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        user = os.getenv("NEO4J_USER", "neo4j")
        password = os.getenv("NEO4J_PASSWORD", "testpassword")

        driver = GraphDatabase.driver(uri, auth=(user, password))
        yield driver
        driver.close()

    def test_neo4j_connection(self, neo4j_driver):
        """Test basic Neo4j connectivity"""
        with neo4j_driver.session() as session:
            result = session.run("RETURN 1 as number")
            record = result.single()
            assert record["number"] == 1

    def test_neo4j_node_operations(self, neo4j_driver):
        """Test basic node creation and retrieval"""
        with neo4j_driver.session() as session:
            # Clean up
            session.run("MATCH (n:IntegrationTest) DELETE n")

            # Create node
            session.run(
                "CREATE (n:IntegrationTest {name: $name, value: $value})",
                name="test", value=42
            )

            # Retrieve node
            result = session.run(
                "MATCH (n:IntegrationTest {name: $name}) RETURN n",
                name="test"
            )
            node = result.single()["n"]
            assert node["name"] == "test"
            assert node["value"] == 42

            # Clean up
            session.run("MATCH (n:IntegrationTest) DELETE n")
