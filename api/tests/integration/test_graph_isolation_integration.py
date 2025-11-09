#!/usr/bin/env python3
"""Integration tests for graph isolation with multiple file ingestion."""

import json
import os
import pytest
from neo4j import GraphDatabase


@pytest.mark.integration
class TestMultiFileGraphIsolation:
    """Integration tests for graph isolation between multiple uploaded files."""

    @pytest.fixture
    def neo4j_driver(self):
        """Neo4j driver connected to service (GitHub Actions or local)."""
        uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        user = os.getenv("NEO4J_USER", "neo4j")
        password = os.getenv("NEO4J_PASSWORD", "testpassword")

        driver = GraphDatabase.driver(uri, auth=(user, password))
        yield driver
        driver.close()

    @pytest.fixture
    def clean_database(self, neo4j_driver):
        """Clean test data before and after each test."""
        with neo4j_driver.session() as session:
            # Clean before - delete all relationships connected to test nodes, then delete nodes
            session.run(
                """
                MATCH (n) WHERE n._upload_id STARTS WITH 'test_integration_'
                DETACH DELETE n
            """
            )

        yield

        with neo4j_driver.session() as session:
            # Clean after - delete all relationships connected to test nodes, then delete nodes
            session.run(
                """
                MATCH (n) WHERE n._upload_id STARTS WITH 'test_integration_'
                DETACH DELETE n
            """
            )

    def test_nodes_with_same_id_different_uploads_are_isolated(self, neo4j_driver, clean_database):
        """Test that nodes with same ID in different uploads remain isolated."""
        with neo4j_driver.session() as session:
            # Create node from file 1
            session.run(
                """
                CREATE (n:TestPerson {
                    id: 'person1',
                    _upload_id: 'test_integration_upload1',
                    _source_file: 'file1.json',
                    name: 'John from File 1'
                })
            """
            )

            # Create node with same ID from file 2
            session.run(
                """
                CREATE (n:TestPerson {
                    id: 'person1',
                    _upload_id: 'test_integration_upload2',
                    _source_file: 'file2.json',
                    name: 'John from File 2'
                })
            """
            )

            # Query nodes from file 1
            result1 = session.run(
                """
                MATCH (n:TestPerson {
                    id: 'person1',
                    _upload_id: 'test_integration_upload1',
                    _source_file: 'file1.json'
                })
                RETURN n.name as name
            """
            )
            node1 = result1.single()

            # Query nodes from file 2
            result2 = session.run(
                """
                MATCH (n:TestPerson {
                    id: 'person1',
                    _upload_id: 'test_integration_upload2',
                    _source_file: 'file2.json'
                })
                RETURN n.name as name
            """
            )
            node2 = result2.single()

            # Verify both nodes exist and are distinct
            assert node1 is not None, "Node from file 1 should exist"
            assert node2 is not None, "Node from file 2 should exist"
            assert node1["name"] == "John from File 1"
            assert node2["name"] == "John from File 2"

            # Verify total count is 2
            count_result = session.run(
                """
                MATCH (n:TestPerson {id: 'person1'})
                WHERE n._upload_id IN ['test_integration_upload1', 'test_integration_upload2']
                RETURN count(n) as count
            """
            )
            count = count_result.single()["count"]
            assert count == 2, "Should have 2 distinct nodes with same id"

    def test_relationships_do_not_cross_file_boundaries(self, neo4j_driver, clean_database):
        """Test that relationships only connect nodes within the same upload."""
        with neo4j_driver.session() as session:
            # Create nodes from file 1
            session.run(
                """
                CREATE (p1:TestPerson {
                    id: 'person1',
                    _upload_id: 'test_integration_upload1',
                    _source_file: 'file1.json',
                    name: 'Alice'
                })
                CREATE (a1:TestAddress {
                    id: 'addr1',
                    _upload_id: 'test_integration_upload1',
                    _source_file: 'file1.json',
                    street: '123 Main St'
                })
                CREATE (p1)-[:LIVES_AT]->(a1)
            """
            )

            # Create nodes from file 2
            session.run(
                """
                CREATE (p2:TestPerson {
                    id: 'person1',
                    _upload_id: 'test_integration_upload2',
                    _source_file: 'file2.json',
                    name: 'Bob'
                })
                CREATE (a2:TestAddress {
                    id: 'addr1',
                    _upload_id: 'test_integration_upload2',
                    _source_file: 'file2.json',
                    street: '456 Oak Ave'
                })
                CREATE (p2)-[:LIVES_AT]->(a2)
            """
            )

            # Query relationships from file 1
            result1 = session.run(
                """
                MATCH (p:TestPerson)-[r:LIVES_AT]->(a:TestAddress)
                WHERE p._upload_id = 'test_integration_upload1'
                    AND a._upload_id = 'test_integration_upload1'
                RETURN p.name as person_name, a.street as address
            """
            )
            rel1 = result1.single()

            # Query relationships from file 2
            result2 = session.run(
                """
                MATCH (p:TestPerson)-[r:LIVES_AT]->(a:TestAddress)
                WHERE p._upload_id = 'test_integration_upload2'
                    AND a._upload_id = 'test_integration_upload2'
                RETURN p.name as person_name, a.street as address
            """
            )
            rel2 = result2.single()

            # Verify relationships are isolated
            assert rel1 is not None
            assert rel2 is not None
            assert rel1["person_name"] == "Alice"
            assert rel1["address"] == "123 Main St"
            assert rel2["person_name"] == "Bob"
            assert rel2["address"] == "456 Oak Ave"

            # Verify no cross-file relationships exist
            cross_rel_result = session.run(
                """
                MATCH (p:TestPerson)-[r:LIVES_AT]->(a:TestAddress)
                WHERE p._upload_id <> a._upload_id
                    AND (p._upload_id STARTS WITH 'test_integration_'
                         OR a._upload_id STARTS WITH 'test_integration_')
                RETURN count(r) as count
            """
            )
            cross_rel_count = cross_rel_result.single()["count"]
            assert cross_rel_count == 0, "Should have no cross-file relationships"

    def test_same_filename_different_uploads_creates_separate_graphs(self, neo4j_driver, clean_database):
        """Test that uploading same filename twice creates separate isolated graphs."""
        with neo4j_driver.session() as session:
            # First upload of data.json
            session.run(
                """
                CREATE (n:TestPerson {
                    id: 'person1',
                    _upload_id: 'test_integration_upload1',
                    _source_file: 'data.json',
                    version: 'v1'
                })
            """
            )

            # Second upload of data.json (same filename, different upload_id)
            session.run(
                """
                CREATE (n:TestPerson {
                    id: 'person1',
                    _upload_id: 'test_integration_upload2',
                    _source_file: 'data.json',
                    version: 'v2'
                })
            """
            )

            # Query all nodes with that filename
            result = session.run(
                """
                MATCH (n:TestPerson {id: 'person1', _source_file: 'data.json'})
                WHERE n._upload_id IN ['test_integration_upload1', 'test_integration_upload2']
                RETURN n.version as version, n._upload_id as upload_id
                ORDER BY n.version
            """
            )
            records = list(result)

            # Verify both versions exist
            assert len(records) == 2
            assert records[0]["version"] == "v1"
            assert records[0]["upload_id"] == "test_integration_upload1"
            assert records[1]["version"] == "v2"
            assert records[1]["upload_id"] == "test_integration_upload2"

    def test_filtering_by_upload_id_returns_isolated_subgraph(self, neo4j_driver, clean_database):
        """Test that filtering by upload_id returns only nodes from that upload."""
        with neo4j_driver.session() as session:
            # Create graph from upload 1
            session.run(
                """
                CREATE (p1:TestPerson {
                    id: 'p1',
                    _upload_id: 'test_integration_upload1',
                    _source_file: 'file1.json'
                })
                CREATE (p2:TestPerson {
                    id: 'p2',
                    _upload_id: 'test_integration_upload1',
                    _source_file: 'file1.json'
                })
                CREATE (p1)-[:KNOWS]->(p2)
            """
            )

            # Create graph from upload 2
            session.run(
                """
                CREATE (p3:TestPerson {
                    id: 'p3',
                    _upload_id: 'test_integration_upload2',
                    _source_file: 'file2.json'
                })
                CREATE (p4:TestPerson {
                    id: 'p4',
                    _upload_id: 'test_integration_upload2',
                    _source_file: 'file2.json'
                })
                CREATE (p3)-[:KNOWS]->(p4)
            """
            )

            # Filter by upload 1
            result1 = session.run(
                """
                MATCH (n:TestPerson)
                WHERE n._upload_id = 'test_integration_upload1'
                RETURN count(n) as count
            """
            )
            count1 = result1.single()["count"]

            # Filter by upload 2
            result2 = session.run(
                """
                MATCH (n:TestPerson)
                WHERE n._upload_id = 'test_integration_upload2'
                RETURN count(n) as count
            """
            )
            count2 = result2.single()["count"]

            # Verify isolation
            assert count1 == 2, "Upload 1 should have 2 nodes"
            assert count2 == 2, "Upload 2 should have 2 nodes"

    def test_filtering_by_source_file_returns_file_specific_nodes(self, neo4j_driver, clean_database):
        """Test that filtering by source file returns only nodes from that file."""
        with neo4j_driver.session() as session:
            # Create nodes from multiple files in same upload
            session.run(
                """
                CREATE (p1:TestPerson {
                    id: 'p1',
                    _upload_id: 'test_integration_upload1',
                    _source_file: 'persons.json'
                })
                CREATE (p2:TestPerson {
                    id: 'p2',
                    _upload_id: 'test_integration_upload1',
                    _source_file: 'persons.json'
                })
                CREATE (a1:TestAddress {
                    id: 'a1',
                    _upload_id: 'test_integration_upload1',
                    _source_file: 'addresses.json'
                })
                CREATE (a2:TestAddress {
                    id: 'a2',
                    _upload_id: 'test_integration_upload1',
                    _source_file: 'addresses.json'
                })
            """
            )

            # Filter by persons.json
            result_persons = session.run(
                """
                MATCH (n)
                WHERE n._upload_id = 'test_integration_upload1'
                    AND n._source_file = 'persons.json'
                RETURN count(n) as count
            """
            )
            persons_count = result_persons.single()["count"]

            # Filter by addresses.json
            result_addresses = session.run(
                """
                MATCH (n)
                WHERE n._upload_id = 'test_integration_upload1'
                    AND n._source_file = 'addresses.json'
                RETURN count(n) as count
            """
            )
            addresses_count = result_addresses.single()["count"]

            # Verify file-specific filtering
            assert persons_count == 2, "persons.json should have 2 nodes"
            assert addresses_count == 2, "addresses.json should have 2 nodes"

    def test_entity_resolution_can_link_across_uploads(self, neo4j_driver, clean_database):
        """Test that entity resolution relationships can link nodes from different uploads."""
        with neo4j_driver.session() as session:
            # Create nodes from two different uploads
            session.run(
                """
                CREATE (p1:TestPerson {
                    id: 'alice_001',
                    _upload_id: 'test_integration_upload1',
                    _source_file: 'file1.json',
                    name: 'Alice Johnson'
                })
            """
            )

            session.run(
                """
                CREATE (p2:TestPerson {
                    id: 'alice_002',
                    _upload_id: 'test_integration_upload2',
                    _source_file: 'file2.json',
                    name: 'Alice Johnson'
                })
            """
            )

            # Create entity resolution relationship (simulating Senzing match)
            session.run(
                """
                MATCH (p1:TestPerson {id: 'alice_001', _upload_id: 'test_integration_upload1'})
                MATCH (p2:TestPerson {id: 'alice_002', _upload_id: 'test_integration_upload2'})
                MERGE (p1)-[r:RESOLVED_TO]->(p2)
                SET r.confidence = 0.95, r.method = 'senzing'
            """
            )

            # Query for resolved entities across uploads
            result = session.run(
                """
                MATCH (p1:TestPerson)-[r:RESOLVED_TO]->(p2:TestPerson)
                WHERE p1._upload_id = 'test_integration_upload1'
                    AND p2._upload_id = 'test_integration_upload2'
                RETURN p1.name as name1, p2.name as name2, r.confidence as confidence
            """
            )
            record = result.single()

            # Verify cross-upload entity resolution works
            assert record is not None, "Entity resolution relationship should exist"
            assert record["name1"] == "Alice Johnson"
            assert record["name2"] == "Alice Johnson"
            assert record["confidence"] == 0.95

    def test_composite_key_prevents_accidental_merges(self, neo4j_driver, clean_database):
        """Test that MERGE with composite key doesn't accidentally merge nodes from different uploads."""
        with neo4j_driver.session() as session:
            # Create first node
            session.run(
                """
                MERGE (n:TestPerson {
                    id: 'person1',
                    _upload_id: 'test_integration_upload1',
                    _source_file: 'file1.json'
                })
                SET n.created_order = 1
            """
            )

            # Try to MERGE same ID but different upload (should create new node)
            session.run(
                """
                MERGE (n:TestPerson {
                    id: 'person1',
                    _upload_id: 'test_integration_upload2',
                    _source_file: 'file2.json'
                })
                SET n.created_order = 2
            """
            )

            # Verify two distinct nodes exist
            result = session.run(
                """
                MATCH (n:TestPerson {id: 'person1'})
                WHERE n._upload_id IN ['test_integration_upload1', 'test_integration_upload2']
                RETURN n.created_order as order, n._upload_id as upload_id
                ORDER BY n.created_order
            """
            )
            records = list(result)

            assert len(records) == 2, "Should have 2 distinct nodes"
            assert records[0]["order"] == 1
            assert records[0]["upload_id"] == "test_integration_upload1"
            assert records[1]["order"] == 2
            assert records[1]["upload_id"] == "test_integration_upload2"
