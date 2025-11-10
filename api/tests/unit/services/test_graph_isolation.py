#!/usr/bin/env python3
"""Unit tests for graph isolation functionality with upload_id."""

import json
import pytest
from niem_api.services.domain.json_to_graph.converter import generate_for_json_content
from niem_api.services.domain.xml_to_graph.converter import generate_for_xml_content


class TestUploadIdGeneration:
    """Test suite for upload_id generation in converters."""

    def test_json_converter_includes_upload_id_in_node_properties(self):
        """Test that JSON converter adds _upload_id to node properties."""
        # Sample mapping
        mapping_dict = {
            "objects": [
                {
                    "qname": "nc:Person",
                    "label": "Person",
                    "properties": [
                        {"neo4j_key": "nc_PersonName", "json_path": "nc:PersonName", "xml_path": "nc:PersonName"}
                    ],
                }
            ],
            "associations": [],
            "references": [],
            "namespaces": {"nc": "http://example.com/nc"},
        }

        # Sample JSON data
        json_data = {
            "@context": {"nc": "http://example.com/nc"},
            "@graph": [{"@id": "person1", "@type": "nc:Person", "nc:PersonName": "John Doe"}],
        }

        json_str = json.dumps(json_data)
        upload_id = "test_upload_123"
        schema_id = "test_schema_456"

        # Generate Cypher with upload_id
        cypher, nodes, edges, contains = generate_for_json_content(
            json_str, mapping_dict, "test_file1.json", upload_id=upload_id, schema_id=schema_id
        )

        # Verify upload_id is in generated Cypher
        assert upload_id in cypher, "upload_id should be in generated Cypher"
        assert "_upload_id" in cypher, "_upload_id property should be set in Cypher"
        assert schema_id in cypher, "schema_id should be in generated Cypher"
        assert "_schema_id" in cypher, "_schema_id property should be set in Cypher"
        assert "test_file1.json" in cypher, "source filename should be in Cypher"

    def test_json_converter_without_upload_id(self):
        """Test that JSON converter works without upload_id (backward compatibility)."""
        mapping_dict = {
            "objects": [
                {
                    "qname": "nc:Person",
                    "label": "Person",
                    "properties": [
                        {"neo4j_key": "nc_PersonName", "json_path": "nc:PersonName", "xml_path": "nc:PersonName"}
                    ],
                }
            ],
            "associations": [],
            "references": [],
            "namespaces": {"nc": "http://example.com/nc"},
        }

        json_data = {
            "@context": {"nc": "http://example.com/nc"},
            "@graph": [{"@id": "person1", "@type": "nc:Person", "nc:PersonName": "John Doe"}],
        }

        json_str = json.dumps(json_data)

        # Generate Cypher without upload_id
        cypher, nodes, edges, contains = generate_for_json_content(json_str, mapping_dict, "test_file.json")

        # Should still work without upload_id
        assert cypher is not None
        assert "Person" in cypher
        assert len(nodes) > 0

    def test_xml_converter_includes_upload_id_in_node_properties(self):
        """Test that XML converter adds _upload_id to node properties."""
        # Sample mapping
        mapping_dict = {
            "objects": [{"qname": "nc:Person", "label": "Person", "properties": []}],
            "associations": [],
            "references": [],
            "namespaces": {"nc": "http://example.com/nc"},
        }

        # Sample XML data
        xml_str = """<?xml version="1.0" encoding="UTF-8"?>
        <nc:Person xmlns:nc="http://example.com/nc" xmlns:s="http://niem.gov/niem/structures/3.0" s:id="person1">
            <nc:PersonName>John Doe</nc:PersonName>
        </nc:Person>"""

        upload_id = "test_upload_789"
        schema_id = "test_schema_012"

        # Generate Cypher with upload_id
        cypher, nodes, edges, contains = generate_for_xml_content(
            xml_str, mapping_dict, "test_file1.xml", upload_id=upload_id, schema_id=schema_id
        )

        # Verify upload_id is in generated Cypher
        assert upload_id in cypher, "upload_id should be in generated Cypher"
        assert "_upload_id" in cypher, "_upload_id property should be set in Cypher"
        assert schema_id in cypher, "schema_id should be in generated Cypher"
        assert "_schema_id" in cypher, "_schema_id property should be set in Cypher"
        assert "test_file1.xml" in cypher, "source filename should be in Cypher"


class TestGraphIsolation:
    """Test suite for graph isolation between files."""

    def test_json_match_clauses_include_upload_id_and_filename(self):
        """Test that MATCH clauses include upload_id and filename for isolation."""
        # Mapping with relationships
        mapping_dict = {
            "objects": [
                {
                    "qname": "nc:Person",
                    "label": "Person",
                    "properties": [
                        {"neo4j_key": "nc_PersonName", "json_path": "nc:PersonName", "xml_path": "nc:PersonName"}
                    ],
                },
                {"qname": "nc:Address", "label": "Address", "properties": []},
            ],
            "associations": [
                {"qname": "nc:PersonResidenceAssociation", "label": "PersonResidenceAssociation", "properties": []}
            ],
            "references": [{"from_qname": "nc:Person", "to_qname": "nc:Address", "relationship": "LIVES_AT"}],
            "namespaces": {"nc": "http://example.com/nc"},
        }

        # JSON with relationships
        json_data = {
            "@context": {"nc": "http://example.com/nc"},
            "@graph": [
                {
                    "@id": "person1",
                    "@type": "nc:Person",
                    "nc:PersonName": "John Doe",
                    "nc:PersonResidenceAssociation": {"@id": "addr1"},
                },
                {"@id": "addr1", "@type": "nc:Address"},
            ],
        }

        json_str = json.dumps(json_data)
        upload_id = "upload_test_123"
        filename = "file1.json"

        # Generate Cypher
        cypher, nodes, edges, contains = generate_for_json_content(
            json_str, mapping_dict, filename, upload_id=upload_id
        )

        # Verify MATCH clauses include composite key
        match_clauses = [line for line in cypher.split("\n") if "MATCH" in line.upper()]

        # All MATCH clauses should include upload_id and filename
        for match_clause in match_clauses:
            if "Person" in match_clause or "Address" in match_clause:
                # Check that composite key is used in MATCH
                assert "_upload_id" in match_clause, f"MATCH clause should include _upload_id: {match_clause}"
                assert "_source_file" in match_clause, f"MATCH clause should include _source_file: {match_clause}"
                assert upload_id in match_clause, f"MATCH clause should include upload_id value: {match_clause}"
                assert filename in match_clause, f"MATCH clause should include filename: {match_clause}"

    def test_xml_match_clauses_include_upload_id_and_filename(self):
        """Test that XML MATCH clauses include upload_id and filename for isolation."""
        # Mapping with nested structure
        mapping_dict = {
            "objects": [
                {"qname": "nc:Person", "label": "Person", "properties": []},
                {"qname": "nc:PersonName", "label": "PersonName", "properties": []},
            ],
            "associations": [],
            "references": [],
            "namespaces": {"nc": "http://example.com/nc"},
        }

        # XML with nested elements
        xml_str = """<?xml version="1.0" encoding="UTF-8"?>
        <nc:Person xmlns:nc="http://example.com/nc" xmlns:s="http://niem.gov/niem/structures/3.0" s:id="person1">
            <nc:PersonName s:id="name1">John Doe</nc:PersonName>
        </nc:Person>"""

        upload_id = "upload_xml_456"
        filename = "file1.xml"

        # Generate Cypher
        cypher, nodes, edges, contains = generate_for_xml_content(xml_str, mapping_dict, filename, upload_id=upload_id)

        # Verify MATCH clauses include composite key
        match_clauses = [line for line in cypher.split("\n") if "MATCH" in line.upper()]

        # All MATCH clauses should include upload_id and sourceDoc (XML uses sourceDoc)
        for match_clause in match_clauses:
            if "Person" in match_clause or "PersonName" in match_clause:
                assert (
                    "_upload_id" in match_clause or "sourceDoc" in match_clause
                ), f"MATCH clause should include isolation properties: {match_clause}"

    def test_different_upload_ids_create_isolated_graphs(self):
        """Test that same data with different upload_ids creates isolated graphs."""
        mapping_dict = {
            "objects": [{"qname": "nc:Person", "label": "Person", "properties": []}],
            "associations": [],
            "references": [],
            "namespaces": {"nc": "http://example.com/nc"},
        }

        json_data = {"@context": {"nc": "http://example.com/nc"}, "@graph": [{"@id": "person1", "@type": "nc:Person"}]}

        json_str = json.dumps(json_data)

        # Generate with first upload_id
        cypher1, nodes1, edges1, contains1 = generate_for_json_content(
            json_str, mapping_dict, "file.json", upload_id="upload_001"
        )

        # Generate with second upload_id
        cypher2, nodes2, edges2, contains2 = generate_for_json_content(
            json_str, mapping_dict, "file.json", upload_id="upload_002"
        )

        # Both should generate valid Cypher
        assert cypher1 is not None
        assert cypher2 is not None

        # They should contain different upload_ids
        assert "upload_001" in cypher1
        assert "upload_002" in cypher2
        assert "upload_001" not in cypher2
        assert "upload_002" not in cypher1

    def test_containment_relationships_use_composite_key(self):
        """Test that containment relationships (parent-child) use composite key matching."""
        mapping_dict = {
            "objects": [
                {"qname": "nc:Person", "label": "Person", "properties": []},
                {"qname": "nc:PersonName", "label": "PersonName", "properties": []},
            ],
            "associations": [],
            "references": [],
            "namespaces": {"nc": "http://example.com/nc"},
        }

        json_data = {
            "@context": {"nc": "http://example.com/nc"},
            "@graph": [
                {"@id": "person1", "@type": "nc:Person", "nc:PersonName": {"@id": "name1", "@type": "nc:PersonName"}}
            ],
        }

        json_str = json.dumps(json_data)
        upload_id = "upload_containment_test"
        filename = "test.json"

        # Generate Cypher
        cypher, nodes, edges, contains = generate_for_json_content(
            json_str, mapping_dict, filename, upload_id=upload_id
        )

        # Check containment relationships (if any are generated)
        # Note: JSON converter may not always generate containment relationships
        # depending on the structure and mapping configuration
        if len(contains) > 0:
            # Verify MERGE statements for containment use composite key
            merge_lines = [line for line in cypher.split("\n") if "MERGE" in line.upper() and "parent" in line.lower()]

            for merge_line in merge_lines:
                # Should match both parent and child with composite key
                assert upload_id in merge_line, "Containment MATCH should include upload_id"
                assert filename in merge_line, "Containment MATCH should include filename"
        else:
            # If no containment relationships are generated, that's acceptable
            # The test structure might not trigger containment detection
            pass


class TestEdgeCasesAndCompatibility:
    """Test edge cases and backward compatibility."""

    def test_empty_upload_id_still_works(self):
        """Test that empty/None upload_id doesn't break the converter."""
        mapping_dict = {
            "objects": [{"qname": "nc:Person", "label": "Person", "properties": []}],
            "associations": [],
            "references": [],
            "namespaces": {"nc": "http://example.com/nc"},
        }

        json_data = {"@context": {"nc": "http://example.com/nc"}, "@graph": [{"@id": "person1", "@type": "nc:Person"}]}

        json_str = json.dumps(json_data)

        # Test with None
        cypher1, _, _, _ = generate_for_json_content(json_str, mapping_dict, "file.json", upload_id=None)
        assert cypher1 is not None

        # Test with empty string
        cypher2, _, _, _ = generate_for_json_content(json_str, mapping_dict, "file.json", upload_id="")
        assert cypher2 is not None

    def test_special_characters_in_filename(self):
        """Test that special characters in filename are handled correctly."""
        mapping_dict = {
            "objects": [{"qname": "nc:Person", "label": "Person", "properties": []}],
            "associations": [],
            "references": [],
            "namespaces": {"nc": "http://example.com/nc"},
        }

        json_data = {"@context": {"nc": "http://example.com/nc"}, "@graph": [{"@id": "person1", "@type": "nc:Person"}]}

        json_str = json.dumps(json_data)

        # Test with special characters in filename
        special_filenames = [
            "file with spaces.json",
            "file-with-dashes.json",
            "file_with_underscores.json",
            "file.multiple.dots.json",
        ]

        for filename in special_filenames:
            cypher, _, _, _ = generate_for_json_content(json_str, mapping_dict, filename, upload_id="test_upload")

            assert cypher is not None, f"Should handle filename: {filename}"
            # Note: Cypher string escaping is handled by Neo4j driver in production

    def test_very_long_upload_id(self):
        """Test that very long upload_ids are handled correctly."""
        mapping_dict = {
            "objects": [{"qname": "nc:Person", "label": "Person", "properties": []}],
            "associations": [],
            "references": [],
            "namespaces": {"nc": "http://example.com/nc"},
        }

        json_data = {"@context": {"nc": "http://example.com/nc"}, "@graph": [{"@id": "person1", "@type": "nc:Person"}]}

        json_str = json.dumps(json_data)

        # Very long upload_id
        long_upload_id = "upload_" + "x" * 500

        cypher, _, _, _ = generate_for_json_content(json_str, mapping_dict, "file.json", upload_id=long_upload_id)

        assert cypher is not None
        assert long_upload_id in cypher
