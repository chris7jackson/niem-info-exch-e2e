#!/usr/bin/env python3
"""
Integration tests for Senzing entity resolution.

These tests require:
- Neo4j running with test data
- Senzing gRPC server running
- PostgreSQL running

Run with: pytest api/tests/integration/test_senzing_entity_resolution.py -v
"""

import pytest
from niem_api.clients.neo4j_client import Neo4jClient
from niem_api.handlers.entity_resolution import (
    handle_run_entity_resolution,
    handle_get_resolution_status,
    handle_reset_entity_resolution,
    handle_get_available_node_types,
)


@pytest.fixture
def neo4j_client():
    """Get Neo4j client for testing."""
    return Neo4jClient()


@pytest.fixture
def sample_entities(neo4j_client):
    """Create sample test entities in Neo4j."""
    # Create test entities with PersonName nodes
    create_query = """
    // Create first Peter Wimsey entity
    CREATE (d1:j_CrashDriver {
        id: 'test_driver_1',
        qname: 'j:CrashDriver',
        sourceDoc: 'test1.xml',
        _upload_id: 'test_upload_1',
        _schema_id: 'test_schema'
    })
    CREATE (pn1:nc_PersonName {
        qname: 'nc:PersonName',
        nc_PersonGivenName: 'Peter',
        nc_PersonSurName: 'Wimsey'
    })
    CREATE (d1)-[:CONTAINS]->(pn1)

    // Create second Peter Wimsey entity (duplicate)
    CREATE (d2:j_CrashDriver {
        id: 'test_driver_2',
        qname: 'j:CrashDriver',
        sourceDoc: 'test2.xml',
        _upload_id: 'test_upload_2',
        _schema_id: 'test_schema'
    })
    CREATE (pn2:nc_PersonName {
        qname: 'nc:PersonName',
        nc_PersonGivenName: 'Peter',
        nc_PersonSurName: 'Wimsey'
    })
    CREATE (d2)-[:CONTAINS]->(pn2)

    // Create unique entity (should not resolve)
    CREATE (d3:j_CrashDriver {
        id: 'test_driver_3',
        qname: 'j:CrashDriver',
        sourceDoc: 'test3.xml',
        _upload_id: 'test_upload_3',
        _schema_id: 'test_schema'
    })
    CREATE (pn3:nc_PersonName {
        qname: 'nc:PersonName',
        nc_PersonGivenName: 'Harriet',
        nc_PersonSurName: 'Vane'
    })
    CREATE (d3)-[:CONTAINS]->(pn3)

    RETURN count(d1) + count(d2) + count(d3) as created
    """

    neo4j_client.query(create_query, {})

    yield

    # Cleanup after test
    cleanup_query = """
    MATCH (n)
    WHERE n.id IN ['test_driver_1', 'test_driver_2', 'test_driver_3']
       OR n.nc_PersonGivenName IN ['Peter', 'Harriet']
    DETACH DELETE n
    """
    neo4j_client.query(cleanup_query, {})

    # Also clean up any ResolvedEntity nodes from test
    handle_reset_entity_resolution()


class TestSenzingEntityResolution:
    """Integration tests for Senzing entity resolution."""

    def test_get_available_node_types(self, sample_entities):
        """Test discovery of resolvable entity types."""
        result = handle_get_available_node_types()

        assert result["status"] == "success"
        assert "nodeTypes" in result
        assert result["totalTypes"] > 0

        # Find CrashDriver in results
        crash_driver = next((nt for nt in result["nodeTypes"] if nt["qname"] == "j:CrashDriver"), None)
        assert crash_driver is not None
        assert crash_driver["category"] == "person"
        assert crash_driver["count"] >= 3  # Our 3 test entities
        assert crash_driver["recommended"] is True  # Has Senzing-mappable fields

    def test_entity_resolution_with_duplicates(self, sample_entities):
        """Test resolving duplicate entities."""
        # Run entity resolution
        result = handle_run_entity_resolution(["j:CrashDriver"])

        # Verify response structure
        assert result["status"] == "success"
        assert result["entitiesExtracted"] >= 3
        assert result["resolvedEntitiesCreated"] >= 1
        assert result["relationshipsCreated"] >= 2
        assert result["resolutionMethod"] in ["senzing", "text_based"]

        # Verify in Neo4j
        neo4j_client = Neo4jClient()

        # Check ResolvedEntity node exists
        re_query = "MATCH (re:ResolvedEntity) RETURN re"
        re_results = neo4j_client.query(re_query, {})
        assert len(re_results) >= 1

        # Check graph isolation properties
        re_node = re_results[0]["re"]
        assert "_upload_ids" in re_node
        assert isinstance(re_node["_upload_ids"], list)
        assert len(re_node["_upload_ids"]) >= 2  # From 2 different uploads

        assert "_schema_ids" in re_node
        assert isinstance(re_node["_schema_ids"], list)

        assert "sourceDocs" in re_node
        assert isinstance(re_node["sourceDocs"], list)
        assert len(re_node["sourceDocs"]) >= 2  # From multiple source files

        # Check RESOLVED_TO relationships
        rel_query = "MATCH ()-[r:RESOLVED_TO]->() RETURN count(r) as count"
        rel_results = neo4j_client.query(rel_query, {})
        assert rel_results[0]["count"] >= 2  # At least 2 duplicates resolved

    def test_resolution_status(self, sample_entities):
        """Test resolution status endpoint."""
        # Run resolution first
        handle_run_entity_resolution(["j:CrashDriver"])

        # Check status
        status = handle_get_resolution_status()

        assert status["status"] == "success"
        assert status["is_active"] is True
        assert status["resolved_entity_clusters"] >= 1
        assert status["entities_resolved"] >= 2

    def test_reset_entity_resolution(self, sample_entities):
        """Test reset functionality."""
        # Run resolution first
        handle_run_entity_resolution(["j:CrashDriver"])

        # Verify data exists
        neo4j_client = Neo4jClient()
        before_query = """
        MATCH (re:ResolvedEntity)
        OPTIONAL MATCH ()-[r:RESOLVED_TO]->()
        RETURN count(DISTINCT re) as nodes, count(r) as rels
        """
        before_results = neo4j_client.query(before_query, {})
        assert before_results[0]["nodes"] > 0
        assert before_results[0]["rels"] > 0

        # Reset
        reset_result = handle_reset_entity_resolution()

        assert reset_result["status"] == "success"
        assert reset_result["resolved_entities_deleted"] > 0
        assert reset_result["relationships_deleted"] >= 0

        # Verify cleanup
        after_query = """
        MATCH (re:ResolvedEntity)
        OPTIONAL MATCH ()-[r:RESOLVED_TO]->()
        RETURN count(DISTINCT re) as nodes, count(r) as rels
        """
        after_results = neo4j_client.query(after_query, {})
        assert after_results[0]["nodes"] == 0
        assert after_results[0]["rels"] == 0

        # Verify status reflects reset
        status = handle_get_resolution_status()
        assert status["is_active"] is False

    def test_cross_document_resolution(self, sample_entities):
        """Test that entities from multiple source files are resolved together."""
        result = handle_run_entity_resolution(["j:CrashDriver"])

        # Get ResolvedEntity node
        neo4j_client = Neo4jClient()
        re_query = """
        MATCH (re:ResolvedEntity)
        WHERE re.resolved_count > 1
        RETURN re.sourceDocs as docs, re.resolved_count as count
        LIMIT 1
        """
        re_results = neo4j_client.query(re_query, {})

        if len(re_results) > 0:
            docs = re_results[0]["docs"]
            count = re_results[0]["count"]

            # Verify multiple source documents
            assert isinstance(docs, list)
            assert len(docs) >= 2  # Cross-document

            # Verify all sources are different
            assert len(docs) == len(set(docs))  # All unique

    def test_senzing_match_details(self, sample_entities):
        """Test that Senzing match details are populated."""
        result = handle_run_entity_resolution(["j:CrashDriver"])

        # When using Senzing (not text-based), matchDetails should be present
        if result.get("resolutionMethod") == "senzing":
            assert "matchDetails" in result
            match_details = result["matchDetails"]

            # Verify structure
            assert "totalEntitiesMatched" in match_details
            assert "totalResolvedGroups" in match_details
            assert "matchQualityDistribution" in match_details
            assert "commonMatchKeys" in match_details
            assert "featureScores" in match_details

            # Verify counts make sense
            assert match_details["totalEntitiesMatched"] >= result["entitiesResolved"]
            assert match_details["totalResolvedGroups"] >= result["resolvedEntitiesCreated"]

    def test_graph_isolation_properties(self, sample_entities):
        """Test that graph isolation properties are properly aggregated."""
        result = handle_run_entity_resolution(["j:CrashDriver"])

        neo4j_client = Neo4jClient()
        re_query = """
        MATCH (re:ResolvedEntity)
        RETURN re._upload_ids as uploads,
               re._schema_ids as schemas,
               re.sourceDocs as docs
        LIMIT 1
        """
        re_results = neo4j_client.query(re_query, {})

        if len(re_results) > 0:
            re_node = re_results[0]

            # Verify all isolation properties are arrays
            assert isinstance(re_node["uploads"], list)
            assert isinstance(re_node["schemas"], list)
            assert isinstance(re_node["docs"], list)

            # Verify they're not empty (if we have resolved entities)
            if result["resolvedEntitiesCreated"] > 0:
                assert len(re_node["uploads"]) > 0
                assert len(re_node["schemas"]) > 0
                assert len(re_node["docs"]) > 0

    def test_no_duplicates_scenario(self, neo4j_client):
        """Test resolution when there are no duplicates."""
        # Create single unique entity
        create_query = """
        CREATE (d:j_CrashDriver {
            id: 'unique_test_driver',
            qname: 'j:CrashDriver',
            sourceDoc: 'unique.xml',
            _upload_id: 'unique_upload',
            _schema_id: 'test_schema'
        })
        CREATE (pn:nc_PersonName {
            qname: 'nc:PersonName',
            nc_PersonGivenName: 'Unique',
            nc_PersonSurName: 'Person'
        })
        CREATE (d)-[:CONTAINS]->(pn)
        """
        neo4j_client.query(create_query, {})

        try:
            result = handle_run_entity_resolution(["j:CrashDriver"])

            # Should succeed but create no ResolvedEntity nodes
            assert result["status"] == "success"
            assert result["entitiesExtracted"] >= 1
            assert result["resolvedEntitiesCreated"] == 0  # No duplicates
            assert result["relationshipsCreated"] == 0

        finally:
            # Cleanup
            cleanup_query = """
            MATCH (n)
            WHERE n.id = 'unique_test_driver' OR n.nc_PersonGivenName = 'Unique'
            DETACH DELETE n
            """
            neo4j_client.query(cleanup_query, {})

    def test_empty_dataset(self):
        """Test resolution with no entities."""
        # Try to resolve non-existent entity type
        result = handle_run_entity_resolution(["non:Existent"])

        assert result["status"] == "success"
        assert result["entitiesExtracted"] == 0
        assert result["resolvedEntitiesCreated"] == 0


def _check_senzing_available():
    """Check if Senzing is fully available (SDK + license)."""
    try:
        from niem_api.clients.senzing_client import get_senzing_client

        client = get_senzing_client()
        return client.is_available()
    except:
        return False


@pytest.mark.skipif(not _check_senzing_available(), reason="Senzing not available (missing SDK or license)")
class TestSenzingSpecificFeatures:
    """Tests that require actual Senzing (not text-based fallback)."""

    def test_senzing_sdk_available(self):
        """Verify Senzing SDK can be imported."""
        from niem_api.clients.senzing_client import SENZING_AVAILABLE, SzAbstractFactory

        assert SENZING_AVAILABLE is True
        assert SzAbstractFactory is not None

    def test_senzing_client_initialization(self):
        """Test Senzing client can initialize."""
        from niem_api.clients.senzing_client import get_senzing_client

        client = get_senzing_client()
        assert client is not None
        assert client.is_available() is True

        # Should be initialized automatically
        assert client.initialized is True

    def test_senzing_entity_id_tracking(self, sample_entities):
        """Test that Senzing entity IDs are properly stored."""
        result = handle_run_entity_resolution(["j:CrashDriver"])

        if result.get("resolutionMethod") == "senzing":
            neo4j_client = Neo4jClient()

            # Check ResolvedEntity has senzing_entity_id
            re_query = """
            MATCH (re:ResolvedEntity)
            RETURN re.senzing_entity_id as senzing_id
            LIMIT 1
            """
            re_results = neo4j_client.query(re_query, {})

            if len(re_results) > 0:
                senzing_id = re_results[0]["senzing_id"]
                assert senzing_id is not None
                assert isinstance(senzing_id, int)
                assert senzing_id > 0

                # Check RESOLVED_TO relationships have same senzing_entity_id
                rel_query = """
                MATCH ()-[r:RESOLVED_TO]->(re:ResolvedEntity)
                WHERE re.senzing_entity_id = $senzing_id
                RETURN r.senzing_entity_id as rel_senzing_id
                """
                rel_results = neo4j_client.query(rel_query, {"senzing_id": senzing_id})

                for rel in rel_results:
                    assert rel["rel_senzing_id"] == senzing_id

    def test_crash_person_type_discovery(self):
        """Test that j:CrashPerson is automatically discovered as a person entity type.

        This tests the schema-based type discovery system which should recognize
        CrashPerson as a person entity without explicit pattern configuration.
        """
        # Create sample CrashPerson entities
        neo4j_client = Neo4jClient()

        create_query = """
        // Create first CrashPerson entity
        CREATE (cp1:j_CrashPerson {
            id: 'test_crashperson_1',
            qname: 'j:CrashPerson',
            sourceDoc: 'crash_test1.xml',
            _upload_id: 'test_upload_cp1',
            _schema_id: 'test_schema'
        })
        CREATE (pn1:nc_PersonName {
            qname: 'nc:PersonName',
            nc_PersonGivenName: 'Alice',
            nc_PersonSurName: 'Johnson'
        })
        CREATE (cp1)-[:CONTAINS]->(pn1)

        // Create second CrashPerson entity (duplicate)
        CREATE (cp2:j_CrashPerson {
            id: 'test_crashperson_2',
            qname: 'j:CrashPerson',
            sourceDoc: 'crash_test2.xml',
            _upload_id: 'test_upload_cp2',
            _schema_id: 'test_schema'
        })
        CREATE (pn2:nc_PersonName {
            qname: 'nc:PersonName',
            nc_PersonGivenName: 'Alice',
            nc_PersonSurName: 'Johnson'
        })
        CREATE (cp2)-[:CONTAINS]->(pn2)

        RETURN count(cp1) + count(cp2) as created
        """

        neo4j_client.query(create_query, {})

        try:
            # Test 1: Verify CrashPerson is discovered in available node types
            result = handle_get_available_node_types()

            assert result["status"] == "success"
            crash_person = next(
                (nt for nt in result["nodeTypes"] if nt["qname"] == "j:CrashPerson"),
                None
            )

            # CrashPerson should be discovered and categorized as 'person'
            # This works because of schema-based discovery, not hardcoded patterns
            assert crash_person is not None, "j:CrashPerson should be discovered as a resolvable type"
            assert crash_person["category"] == "person", "j:CrashPerson should be categorized as person entity"
            assert crash_person["count"] >= 2, "Should have at least 2 CrashPerson entities"

            # Test 2: Verify CrashPerson entities can be resolved
            resolution_result = handle_run_entity_resolution(["j:CrashPerson"])

            assert resolution_result["status"] == "success"
            assert resolution_result["entitiesExtracted"] >= 2
            assert resolution_result["resolvedEntitiesCreated"] >= 1
            assert resolution_result["relationshipsCreated"] >= 2

        finally:
            # Cleanup
            cleanup_query = """
            MATCH (n)
            WHERE n.id IN ['test_crashperson_1', 'test_crashperson_2']
               OR (n.nc_PersonGivenName = 'Alice' AND n.nc_PersonSurName = 'Johnson')
            DETACH DELETE n
            """
            neo4j_client.query(cleanup_query, {})

            # Clean up resolved entities
            handle_reset_entity_resolution()


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v", "--tb=short"])
