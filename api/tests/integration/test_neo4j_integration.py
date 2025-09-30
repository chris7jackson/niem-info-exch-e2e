#!/usr/bin/env python3

import pytest
import asyncio
from testcontainers.neo4j import Neo4jContainer

from niem_api.services.neo4j_client import Neo4jClient
from niem_api.services.graph_schema import GraphSchemaManager


@pytest.mark.integration
class TestNeo4jIntegration:
    """Integration tests for Neo4j database operations"""

    @pytest.fixture(scope="class")
    def neo4j_container(self):
        """Start Neo4j test container"""
        with Neo4jContainer("neo4j:5.20.0-community") as neo4j:
            neo4j.with_env("NEO4J_AUTH", "neo4j/testpassword")
            yield neo4j

    @pytest.fixture
    def neo4j_client(self, neo4j_container):
        """Neo4j client connected to test container"""
        uri = neo4j_container.get_connection_url()
        client = Neo4jClient(uri, "neo4j", "testpassword")
        yield client
        client.close()

    @pytest.fixture
    def graph_schema_manager(self, neo4j_client):
        """Graph schema manager with test client"""
        # Mock the dependency injection for testing
        with patch('niem_api.services.graph_schema.get_neo4j_client', return_value=neo4j_client):
            manager = GraphSchemaManager()
            yield manager
            manager.close()

    def test_connection_establishment(self, neo4j_client):
        """Test that we can establish connection to Neo4j"""
        assert neo4j_client.check_connection() is True

    def test_basic_query_execution(self, neo4j_client):
        """Test basic query execution"""
        result = neo4j_client.query("RETURN 1 as number")
        assert len(result) == 1
        assert result[0]["number"] == 1

    def test_node_creation_and_retrieval(self, neo4j_client):
        """Test creating and retrieving nodes"""
        # Clean up first
        neo4j_client.query("MATCH (n:TestPerson) DELETE n")

        # Create a test node
        neo4j_client.query(
            "CREATE (p:TestPerson {name: $name, age: $age})",
            {"name": "John Doe", "age": 30}
        )

        # Retrieve the node
        result = neo4j_client.query(
            "MATCH (p:TestPerson {name: $name}) RETURN p",
            {"name": "John Doe"}
        )

        assert len(result) == 1
        person = result[0]["p"]
        assert person["name"] == "John Doe"
        assert person["age"] == 30

        # Clean up
        neo4j_client.query("MATCH (n:TestPerson) DELETE n")

    def test_relationship_creation_and_query(self, neo4j_client):
        """Test creating relationships and querying graph structure"""
        # Clean up first
        neo4j_client.query("MATCH (n:TestPerson)-[r:KNOWS]-(m:TestPerson) DELETE r, n, m")

        # Create nodes and relationship
        neo4j_client.query("""
            CREATE (p1:TestPerson {name: 'Alice', id: 'alice'})
            CREATE (p2:TestPerson {name: 'Bob', id: 'bob'})
            CREATE (p1)-[:KNOWS {since: '2020'}]->(p2)
        """)

        # Query graph structure
        graph_result = neo4j_client.query_graph("""
            MATCH (p1:TestPerson)-[r:KNOWS]->(p2:TestPerson)
            RETURN p1, r, p2
        """)

        assert len(graph_result["nodes"]) == 2
        assert len(graph_result["relationships"]) == 1

        # Verify nodes
        nodes_by_name = {node["properties"]["name"]: node for node in graph_result["nodes"]}
        assert "Alice" in nodes_by_name
        assert "Bob" in nodes_by_name

        # Verify relationship
        rel = graph_result["relationships"][0]
        assert rel["type"] == "KNOWS"
        assert rel["properties"]["since"] == "2020"

        # Clean up
        neo4j_client.query("MATCH (n:TestPerson)-[r:KNOWS]-(m:TestPerson) DELETE r, n, m")

    def test_schema_operations(self, graph_schema_manager, neo4j_client):
        """Test schema creation and management"""
        # Clean up existing schema
        try:
            neo4j_client.query("DROP INDEX TestPersonNameIndex IF EXISTS")
            neo4j_client.query("DROP CONSTRAINT TestPersonIdConstraint IF EXISTS")
        except:
            pass

        # Test index creation
        result = graph_schema_manager._create_index("TestPerson", "name")
        assert result is True

        # Test constraint creation
        result = graph_schema_manager._create_unique_constraint("TestPerson", "id")
        assert result is True

        # Verify schema exists
        indexes = neo4j_client.query("SHOW INDEXES")
        constraints = neo4j_client.query("SHOW CONSTRAINTS")

        index_found = any(
            idx.get("labelsOrTypes") == ["TestPerson"] and
            idx.get("properties") == ["name"]
            for idx in indexes
        )
        constraint_found = any(
            constraint.get("labelsOrTypes") == ["TestPerson"] and
            constraint.get("properties") == ["id"]
            for constraint in constraints
        )

        assert index_found
        assert constraint_found

        # Clean up
        try:
            neo4j_client.query("DROP INDEX FOR (n:TestPerson) ON (n.name)")
            neo4j_client.query("DROP CONSTRAINT FOR (n:TestPerson) REQUIRE n.id IS UNIQUE")
        except:
            pass

    def test_mapping_schema_configuration(self, graph_schema_manager):
        """Test configuring schema from mapping specification"""
        sample_mapping = {
            "nodes": [
                {
                    "label": "Person",
                    "props": [{"name": "id", "type": "string"}]
                },
                {
                    "label": "Company",
                    "props": [{"name": "id", "type": "string"}]
                }
            ],
            "relationships": [
                {"type": "WORKS_FOR"}
            ],
            "indexes": [
                {
                    "label": "Person",
                    "properties": ["name", "email"]
                }
            ]
        }

        result = graph_schema_manager.configure_schema_from_mapping(sample_mapping)

        assert "constraints_created" in result
        assert "indexes_created" in result
        assert len(result["labels_identified"]) == 2
        assert "Person" in result["labels_identified"]
        assert "Company" in result["labels_identified"]

    def test_database_stats_collection(self, neo4j_client):
        """Test database statistics collection"""
        # Create some test data
        neo4j_client.query("""
            CREATE (p:TestPerson {name: 'Alice'})
            CREATE (c:TestCompany {name: 'Acme Corp'})
            CREATE (p)-[:WORKS_FOR]->(c)
        """)

        stats = neo4j_client.get_database_stats()

        assert "node_count" in stats
        assert "relationship_count" in stats
        assert "labels" in stats
        assert "relationship_types" in stats

        # Verify our test data appears in stats
        assert stats["node_count"] >= 2
        assert stats["relationship_count"] >= 1
        assert "TestPerson" in stats["labels"]
        assert "TestCompany" in stats["labels"]
        assert "WORKS_FOR" in stats["relationship_types"]

        # Clean up
        neo4j_client.query("MATCH (n:TestPerson)-[r]-(m) DELETE r, n, m")

    def test_concurrent_operations(self, neo4j_client):
        """Test concurrent database operations"""
        async def create_person(person_id: int):
            neo4j_client.query(
                "CREATE (p:ConcurrentTest {id: $id, name: $name})",
                {"id": person_id, "name": f"Person{person_id}"}
            )

        async def run_concurrent_creates():
            tasks = [create_person(i) for i in range(10)]
            await asyncio.gather(*tasks)

        # Run concurrent operations
        asyncio.run(run_concurrent_creates())

        # Verify all nodes were created
        result = neo4j_client.query("MATCH (p:ConcurrentTest) RETURN count(p) as count")
        assert result[0]["count"] == 10

        # Clean up
        neo4j_client.query("MATCH (n:ConcurrentTest) DELETE n")

    def test_transaction_rollback(self, neo4j_client):
        """Test transaction rollback behavior"""
        # This tests that our client handles errors properly
        # and doesn't leave partial data
        try:
            with neo4j_client.driver.session() as session:
                with session.begin_transaction() as tx:
                    tx.run("CREATE (p:TransactionTest {id: 1})")
                    # Intentionally cause an error
                    tx.run("INVALID CYPHER QUERY")
        except Exception:
            pass  # Expected to fail

        # Verify no partial data was committed
        result = neo4j_client.query("MATCH (p:TransactionTest) RETURN count(p) as count")
        assert result[0]["count"] == 0