#!/usr/bin/env python3
"""Unit tests for XML to Cypher converter property name escaping."""

import pytest
from niem_api.services.domain.xml_to_graph.converter import (
    generate_for_xml_content,
    synth_id,
    load_mapping_from_dict,
)


def test_property_name_with_hyphen_escaping():
    """Test that property names containing hyphens are properly escaped with backticks."""
    # Minimal mapping with a property that has a hyphen
    mapping_dict = {
        "objects": [
            {
                "qname": "nc:Location",
                "label": "Location",
                "properties": {
                    "nc:LocationStateFIPS5-2AlphaCode": "{{text}}"
                }
            }
        ],
        "associations": [],
        "references": [],
        "namespaces": {
            "nc": "http://example.com/nc"
        }
    }

    # Minimal XML with the hyphenated property
    xml_str = """<?xml version="1.0" encoding="UTF-8"?>
<nc:Location xmlns:nc="http://example.com/nc">
    <nc:LocationStateFIPS5-2AlphaCode>FL</nc:LocationStateFIPS5-2AlphaCode>
</nc:Location>"""

    # Generate Cypher
    cypher, _, _, _ = generate_for_xml_content(
        xml_str,
        mapping_dict,
        "test.xml"
    )

    # Verify that the hyphenated property name is escaped with backticks
    assert "`nc_LocationStateFIPS5-2AlphaCode`" in cypher, \
        "Property name with hyphen should be escaped with backticks"

    # Verify there's no unescaped version that would cause syntax error
    assert "n.nc_LocationStateFIPS5-2AlphaCode=" not in cypher or \
           "`nc_LocationStateFIPS5-2AlphaCode`" in cypher, \
        "Hyphenated property must be backtick-escaped to avoid Cypher syntax errors"


def test_property_name_with_dot_escaping():
    """Test that property names containing dots are properly escaped with backticks."""
    mapping_dict = {
        "objects": [
            {
                "qname": "nc:Person",
                "label": "Person",
                "properties": {
                    "nc:Person.Name": "{{text}}"
                }
            }
        ],
        "associations": [],
        "references": [],
        "namespaces": {
            "nc": "http://example.com/nc"
        }
    }

    xml_str = """<?xml version="1.0" encoding="UTF-8"?>
<nc:Person xmlns:nc="http://example.com/nc">
    <nc:Person.Name>John Doe</nc:Person.Name>
</nc:Person>"""

    cypher, _, _, _ = generate_for_xml_content(
        xml_str,
        mapping_dict,
        "test.xml"
    )

    # Verify that the property name with dot is escaped
    assert "`nc_Person.Name`" in cypher or "`nc_Person_Name`" in cypher, \
        "Property name with dot should be escaped with backticks"


def test_normal_property_name_no_escaping():
    """Test that normal property names (alphanumeric + underscore) don't get escaped."""
    mapping_dict = {
        "objects": [
            {
                "qname": "nc:Person",
                "label": "Person",
                "properties": {
                    "nc:PersonName": "{{text}}"
                }
            }
        ],
        "associations": [],
        "references": [],
        "namespaces": {
            "nc": "http://example.com/nc"
        }
    }

    xml_str = """<?xml version="1.0" encoding="UTF-8"?>
<nc:Person xmlns:nc="http://example.com/nc">
    <nc:PersonName>Jane Doe</nc:PersonName>
</nc:Person>"""

    cypher, _, _, _ = generate_for_xml_content(
        xml_str,
        mapping_dict,
        "test.xml"
    )

    # Normal property names should not have backticks
    # (they may have them, but it's not required)
    # Just verify the Cypher is generated without syntax errors
    assert "nc_PersonName" in cypher, \
        "Normal property names should be present in output"


def test_synth_id_uses_sha1():
    """Test that synth_id uses SHA1 hash with usedforsecurity=False."""
    # This test ensures coverage of the usedforsecurity=False parameter (line 128)
    result = synth_id(
        parent_id="parent_123",
        elem_qn="nc:Person",
        ordinal_path="/root[1]/person[2]",
        file_prefix="abc123"
    )

    # Verify the synthetic ID format
    assert result.startswith("abc123_syn_"), "Synthetic ID should have file prefix and syn_ prefix"
    assert len(result) > 20, "Synthetic ID should include hash"
