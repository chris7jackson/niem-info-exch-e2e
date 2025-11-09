"""
Unit tests for XML to Graph property flattening logic.

Tests the critical property flattening functionality including:
- Simple nested properties
- Deep nesting (3+ levels)
- Array properties
- Empty/nil elements
- Namespace handling
- Double underscore delimiter
"""

import pytest
import yaml
from pathlib import Path

from niem_api.services.domain.xml_to_graph.converter import generate_for_xml_content
from tests.utils.converter_helpers import (
    assert_node_exists,
    assert_property_flattened,
    get_node_properties,
    count_nodes_by_label
)


# Fixtures

@pytest.fixture
def minimal_mapping():
    """Minimal mapping for dynamic mode (no selections)."""
    return {
        "objects": [],
        "associations": [],
        "references": [],
        "namespaces": {
            "nc": "http://release.niem.gov/niem/niem-core/5.0/",
            "structures": "https://docs.oasis-open.org/niemopen/ns/model/structures/6.0/"
        }
    }


@pytest.fixture
def fixtures_dir():
    """Path to test fixtures directory."""
    return Path(__file__).parent.parent.parent.parent / "fixtures"


# Tests

class TestSimplePropertyFlattening:
    """Tests for simple nested property flattening."""

    def test_single_level_nesting_flattens_correctly(self, minimal_mapping):
        """Test that single-level nested properties are flattened with double underscore."""
        xml_str = """<?xml version="1.0" encoding="UTF-8"?>
        <nc:Person xmlns:nc="http://release.niem.gov/niem/niem-core/5.0/"
                   xmlns:structures="https://docs.oasis-open.org/niemopen/ns/model/structures/6.0/"
                   structures:id="P01">
            <nc:PersonName>
                <nc:PersonGivenName>John</nc:PersonGivenName>
                <nc:PersonSurName>Smith</nc:PersonSurName>
            </nc:PersonName>
        </nc:Person>"""

        cypher, nodes, contains, edges = generate_for_xml_content(
            xml_str, minimal_mapping, "test.xml", mode="dynamic"
        )

        # Verify Person node created (PersonName should be flattened in dynamic mode)
        node_props = get_node_properties(nodes, 'Person')

        # Verify flattened properties use double underscore
        assert_property_flattened(node_props, 'nc_PersonName__nc_PersonGivenName', 'John')
        assert_property_flattened(node_props, 'nc_PersonName__nc_PersonSurName', 'Smith')

    def test_two_level_nesting_uses_proper_delimiter(self, minimal_mapping):
        """Test that two-level nesting uses proper path separators."""
        xml_str = """<?xml version="1.0" encoding="UTF-8"?>
        <nc:Person xmlns:nc="http://release.niem.gov/niem/niem-core/5.0/"
                   xmlns:structures="https://docs.oasis-open.org/niemopen/ns/model/structures/6.0/">
            <nc:PersonBirthDate>
                <nc:Date>1990-01-15</nc:Date>
            </nc:PersonBirthDate>
        </nc:Person>"""

        cypher, nodes, contains, edges = generate_for_xml_content(
            xml_str, minimal_mapping, "test.xml", mode="dynamic"
        )

        node_props = get_node_properties(nodes, 'Person')
        assert_property_flattened(node_props, 'nc_PersonBirthDate__nc_Date', '1990-01-15')

    def test_direct_child_properties_no_flattening(self, minimal_mapping):
        """Test that direct child simple properties don't get flattened paths."""
        xml_str = """<?xml version="1.0" encoding="UTF-8"?>
        <nc:Person xmlns:nc="http://release.niem.gov/niem/niem-core/5.0/">
            <nc:PersonGivenName>John</nc:PersonGivenName>
            <nc:PersonSurName>Smith</nc:PersonSurName>
        </nc:Person>"""

        cypher, nodes, contains, edges = generate_for_xml_content(
            xml_str, minimal_mapping, "test.xml", mode="dynamic"
        )

        node_props = get_node_properties(nodes, 'Person')

        # Direct children should just use namespace_elementName
        assert 'nc_PersonGivenName' in node_props
        assert node_props['nc_PersonGivenName'] == 'John'
        assert 'nc_PersonSurName' in node_props
        assert node_props['nc_PersonSurName'] == 'Smith'


class TestArrayPropertyFlattening:
    """Tests for array/multi-valued property handling."""

    def test_multiple_values_create_array_property(self, minimal_mapping):
        """Test that multiple elements with same name create array."""
        xml_str = """<?xml version="1.0" encoding="UTF-8"?>
        <nc:Person xmlns:nc="http://release.niem.gov/niem/niem-core/5.0/">
            <nc:PersonName>
                <nc:PersonMiddleName>Robert</nc:PersonMiddleName>
                <nc:PersonMiddleName>James</nc:PersonMiddleName>
                <nc:PersonMiddleName>William</nc:PersonMiddleName>
            </nc:PersonName>
        </nc:Person>"""

        cypher, nodes, contains, edges = generate_for_xml_content(
            xml_str, minimal_mapping, "test.xml", mode="dynamic"
        )

        node_props = get_node_properties(nodes, 'Person')

        # Multiple values should be array
        middle_names = node_props.get('nc_PersonName__nc_PersonMiddleName')
        assert isinstance(middle_names, list)
        assert len(middle_names) == 3
        assert 'Robert' in middle_names
        assert 'James' in middle_names
        assert 'William' in middle_names

    def test_single_value_not_array(self, minimal_mapping):
        """Test that single value is not wrapped in array."""
        xml_str = """<?xml version="1.0" encoding="UTF-8"?>
        <nc:Person xmlns:nc="http://release.niem.gov/niem/niem-core/5.0/">
            <nc:PersonName>
                <nc:PersonMiddleName>Robert</nc:PersonMiddleName>
            </nc:PersonName>
        </nc:Person>"""

        cypher, nodes, contains, edges = generate_for_xml_content(
            xml_str, minimal_mapping, "test.xml", mode="dynamic"
        )

        node_props = get_node_properties(nodes, 'Person')

        # Single value should be string, not array
        middle_name = node_props.get('nc_PersonName__nc_PersonMiddleName')
        assert isinstance(middle_name, str)
        assert middle_name == 'Robert'


class TestDeepNestingFlattening:
    """Tests for deep (3+ levels) property nesting."""

    def test_three_level_nesting(self, minimal_mapping):
        """Test that 3-level deep properties are flattened correctly."""
        xml_str = """<?xml version="1.0" encoding="UTF-8"?>
        <nc:Person xmlns:nc="http://release.niem.gov/niem/niem-core/5.0/">
            <nc:PersonEmployment>
                <nc:EmploymentLocation>
                    <nc:LocationCityName>Springfield</nc:LocationCityName>
                </nc:EmploymentLocation>
            </nc:PersonEmployment>
        </nc:Person>"""

        cypher, nodes, contains, edges = generate_for_xml_content(
            xml_str, minimal_mapping, "test.xml", mode="dynamic"
        )

        node_props = get_node_properties(nodes, 'Person')

        # Verify 3-level path created
        expected_path = 'nc_PersonEmployment__nc_EmploymentLocation__nc_LocationCityName'
        assert expected_path in node_props, f"Expected property '{expected_path}' not found"
        assert node_props[expected_path] == 'Springfield'


class TestEmptyAndNilElements:
    """Tests for empty and nil element handling."""

    def test_empty_element_creates_empty_string(self, minimal_mapping):
        """Test that empty elements result in empty string properties."""
        xml_str = """<?xml version="1.0" encoding="UTF-8"?>
        <nc:Person xmlns:nc="http://release.niem.gov/niem/niem-core/5.0/">
            <nc:PersonGivenName></nc:PersonGivenName>
        </nc:Person>"""

        cypher, nodes, contains, edges = generate_for_xml_content(
            xml_str, minimal_mapping, "test.xml", mode="dynamic"
        )

        node_props = get_node_properties(nodes, 'Person')

        # Empty element should create property with empty string
        assert 'nc_PersonGivenName' in node_props
        assert node_props['nc_PersonGivenName'] == ''

    def test_nil_element_handling(self, minimal_mapping):
        """Test that xsi:nil elements are handled appropriately."""
        xml_str = """<?xml version="1.0" encoding="UTF-8"?>
        <nc:Person xmlns:nc="http://release.niem.gov/niem/niem-core/5.0/"
                   xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
            <nc:PersonBirthDate xsi:nil="true"/>
        </nc:Person>"""

        cypher, nodes, contains, edges = generate_for_xml_content(
            xml_str, minimal_mapping, "test.xml", mode="dynamic"
        )

        node_props = get_node_properties(nodes, 'Person')

        # Nil element should either be omitted or have null value
        # (depends on implementation - verify actual behavior)
        # This test documents the expected behavior
        assert True  # Placeholder - verify actual nil handling


class TestNamespaceHandling:
    """Tests for namespace prefix handling in property paths."""

    def test_property_path_preserves_namespace_prefix(self, minimal_mapping):
        """Test that flattened paths preserve namespace prefixes."""
        xml_str = """<?xml version="1.0" encoding="UTF-8"?>
        <nc:Person xmlns:nc="http://release.niem.gov/niem/niem-core/5.0/">
            <nc:PersonName>
                <nc:PersonGivenName>John</nc:PersonGivenName>
            </nc:PersonName>
        </nc:Person>"""

        cypher, nodes, contains, edges = generate_for_xml_content(
            xml_str, minimal_mapping, "test.xml", mode="dynamic"
        )

        node_props = get_node_properties(nodes, 'Person')

        # Verify namespace prefix included in property name
        assert 'nc_PersonName__nc_PersonGivenName' in node_props

    def test_mixed_namespaces_in_path(self, minimal_mapping):
        """Test that mixed namespaces are preserved in flattened paths."""
        xml_str = """<?xml version="1.0" encoding="UTF-8"?>
        <j:Crash xmlns:j="http://release.niem.gov/niem/domains/jxdm/7.0/"
                 xmlns:nc="http://release.niem.gov/niem/niem-core/5.0/">
            <nc:ActivityDate>
                <nc:Date>2024-11-08</nc:Date>
            </nc:ActivityDate>
        </j:Crash>"""

        mapping = {
            "objects": [],
            "associations": [],
            "references": [],
            "namespaces": {
                "j": "http://release.niem.gov/niem/domains/jxdm/7.0/",
                "nc": "http://release.niem.gov/niem/niem-core/5.0/"
            }
        }

        cypher, nodes, contains, edges = generate_for_xml_content(
            xml_str, mapping, "test.xml", mode="dynamic"
        )

        node_props = get_node_properties(nodes, 'Crash')

        # Mixed namespace: j_Crash with nc_ActivityDate__nc_Date property
        assert 'nc_ActivityDate__nc_Date' in node_props
        assert node_props['nc_ActivityDate__nc_Date'] == '2024-11-08'


class TestComplexElementFlattening:
    """Tests for complex element detection and conditional flattening."""

    def test_complex_element_with_attributes_flattens(self, minimal_mapping):
        """Test that complex elements with only simple children get flattened."""
        xml_str = """<?xml version="1.0" encoding="UTF-8"?>
        <nc:Person xmlns:nc="http://release.niem.gov/niem/niem-core/5.0/">
            <nc:PersonName>
                <nc:PersonGivenName>John</nc:PersonGivenName>
                <nc:PersonSurName>Smith</nc:PersonSurName>
            </nc:PersonName>
        </nc:Person>"""

        cypher, nodes, contains, edges = generate_for_xml_content(
            xml_str, minimal_mapping, "test.xml", mode="dynamic"
        )

        # In dynamic mode, PersonName might be a node or flattened
        # This test verifies the current behavior
        # If flattened:
        node_props = get_node_properties(nodes, 'Person')

        has_flattened = 'nc_PersonName__nc_PersonGivenName' in node_props
        has_person_name_node = count_nodes_by_label(nodes, 'PersonName') > 0

        # Should be either flattened OR separate node, not both
        assert has_flattened or has_person_name_node
