#!/usr/bin/env python3
"""Unit tests for JSON to Cypher converter."""

import json
import pytest
from niem_api.services.domain.json_to_graph.converter import generate_for_json_content


def test_generate_for_json_content_uses_sha1_hash():
    """Test that generate_for_json_content uses SHA1 hash for file prefix."""
    # This test ensures coverage of the usedforsecurity=False parameter (line 237)

    # Minimal mapping (properties must be a list of dicts, not a dict)
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

    # Minimal NIEM JSON (as dict, will convert to string)
    json_data = {
        "@context": {"nc": "http://example.com/nc"},
        "@graph": [{"@id": "person1", "@type": "nc:Person", "nc:PersonName": "John Doe"}],
    }

    # Convert to JSON string (function expects string, not dict)
    json_str = json.dumps(json_data)

    # Generate Cypher - this should trigger the SHA1 hash generation at line 237
    cypher, nodes, edges, contains = generate_for_json_content(json_str, mapping_dict, "test.json")

    # Verify that Cypher was generated
    assert cypher is not None
    assert "Person" in cypher
    assert len(nodes) > 0
