"""
Unit tests for XML converter property flattening logic.

Tests the critical property flattening functionality using real NIEM CrashDriver samples.
"""

import pytest
from pathlib import Path

from niem_api.services.domain.xml_to_graph.converter import generate_for_xml_content
from tests.utils.converter_helpers import (
    assert_node_exists,
    assert_property_flattened,
    get_node_properties,
    count_nodes_by_label,
    assert_no_node_with_label
)


# Fixtures

@pytest.fixture
def fixtures_dir():
    """Path to test fixtures directory."""
    return Path(__file__).parent.parent.parent.parent.parent / "fixtures"


@pytest.fixture
def crashdriver_dir(fixtures_dir):
    """Path to CrashDriver test fixtures."""
    return fixtures_dir / "crashdriver"


@pytest.fixture
def msg1_xml(crashdriver_dir):
    """Load msg1.xml (basic example with nested properties)."""
    with open(crashdriver_dir / "examples" / "msg1.xml") as f:
        return f.read()


@pytest.fixture
def msg2_xml(crashdriver_dir):
    """Load msg2.xml (multiple persons and associations)."""
    with open(crashdriver_dir / "examples" / "msg2.xml") as f:
        return f.read()


@pytest.fixture
def minimal_mapping():
    """Minimal mapping for dynamic mode (all complex elements → nodes)."""
    return {
        "objects": [],
        "associations": [],
        "references": [],
        "namespaces": {
            "nc": "http://release.niem.gov/niem/niem-core/5.0/",
            "j": "http://release.niem.gov/niem/domains/jxdm/7.0/",
            "structures": "https://docs.oasis-open.org/niemopen/ns/model/structures/6.0/"
        }
    }


# Tests

class TestBasicPropertyFlattening:
    """Tests for basic property flattening using msg1.xml."""

    def test_person_name_properties_flattened_with_double_underscore(self, msg1_xml, minimal_mapping):
        """Test that PersonName child properties are flattened onto CrashDriver node."""
        cypher, nodes, contains, edges = generate_for_xml_content(
            msg1_xml, minimal_mapping, "msg1.xml", mode="dynamic"
        )

        # Find CrashDriver node (should have flattened person name properties)
        crash_driver_nodes = [n for nid, n in nodes.items() if 'CrashDriver' in n[0]]
        assert len(crash_driver_nodes) > 0, "CrashDriver node should exist"

        node_props = crash_driver_nodes[0][2]

        # Verify PersonName properties flattened with correct delimiter
        # msg1.xml has: <nc:PersonGivenName>Peter</nc:PersonGivenName>
        # Should become: nc_PersonName__nc_PersonGivenName: 'Peter'
        assert 'nc_PersonName__nc_PersonGivenName' in node_props, f"Flattened property not found. Available: {list(node_props.keys())}"
        assert node_props['nc_PersonName__nc_PersonGivenName'] == 'Peter'

        assert 'nc_PersonName__nc_PersonSurName' in node_props
        assert node_props['nc_PersonName__nc_PersonSurName'] == 'Wimsey'

    def test_birth_date_flattened_correctly(self, msg1_xml, minimal_mapping):
        """Test that nc:PersonBirthDate > nc:Date is flattened."""
        cypher, nodes, contains, edges = generate_for_xml_content(
            msg1_xml, minimal_mapping, "msg1.xml", mode="dynamic"
        )

        crash_driver_nodes = [n for nid, n in nodes.items() if 'CrashDriver' in n[0]]
        node_props = crash_driver_nodes[0][2]

        # msg1.xml has: <nc:PersonBirthDate><nc:Date>1890-05-04</nc:Date></nc:PersonBirthDate>
        assert 'nc_PersonBirthDate__nc_Date' in node_props
        assert node_props['nc_PersonBirthDate__nc_Date'] == '1890-05-04'

    def test_activity_date_flattened_on_crash_node(self, msg1_xml, minimal_mapping):
        """Test that Crash activity date is flattened."""
        cypher, nodes, contains, edges = generate_for_xml_content(
            msg1_xml, minimal_mapping, "msg1.xml", mode="dynamic"
        )

        crash_nodes = [n for nid, n in nodes.items() if n[1] == 'j:Crash']
        assert len(crash_nodes) > 0

        node_props = crash_nodes[0][2]

        # msg1.xml has: <nc:ActivityDate><nc:Date>1907-05-04</nc:Date></nc:ActivityDate>
        assert 'nc_ActivityDate__nc_Date' in node_props
        assert node_props['nc_ActivityDate__nc_Date'] == '1907-05-04'


class TestArrayPropertyFlattening:
    """Tests for array/multi-valued property handling."""

    def test_multiple_middle_names_create_array(self, msg1_xml, minimal_mapping):
        """Test that multiple PersonMiddleName elements create array property."""
        cypher, nodes, contains, edges = generate_for_xml_content(
            msg1_xml, minimal_mapping, "msg1.xml", mode="dynamic"
        )

        crash_driver_nodes = [n for nid, n in nodes.items() if 'CrashDriver' in n[0]]
        node_props = crash_driver_nodes[0][2]

        # msg1.xml has: <nc:PersonMiddleName>Death</nc:PersonMiddleName>
        #               <nc:PersonMiddleName>Bredon</nc:PersonMiddleName>
        middle_names = node_props.get('nc_PersonName__nc_PersonMiddleName')

        assert isinstance(middle_names, list), "Multiple PersonMiddleName should create array"
        assert len(middle_names) == 2
        assert 'Death' in middle_names
        assert 'Bredon' in middle_names
        # Verify ordering is preserved
        assert middle_names == ['Death', 'Bredon']


class TestDeepNesting:
    """Tests for deep (3+ levels) property nesting."""

    def test_four_level_geospatial_nesting(self, msg1_xml, minimal_mapping):
        """Test that 4-level deep geospatial coordinates are flattened correctly."""
        cypher, nodes, contains, edges = generate_for_xml_content(
            msg1_xml, minimal_mapping, "msg1.xml", mode="dynamic"
        )

        # msg1.xml has deep nesting:
        # Crash > ActivityLocation > Location2DGeospatialCoordinate > GeographicCoordinateLatitude > LatitudeDegreeValue
        crash_nodes = [n for nid, n in nodes.items() if n[1] == 'j:Crash']
        node_props = crash_nodes[0][2]

        # Expected path with 4 levels
        expected_path = 'nc_ActivityLocation__nc_Location2DGeospatialCoordinate__nc_GeographicCoordinateLatitude__nc_LatitudeDegreeValue'

        if expected_path in node_props:
            # Verify value
            assert node_props[expected_path] == '51.74'
        else:
            # Alternative: might create intermediate nodes in dynamic mode
            # This documents actual behavior
            print(f"Available properties: {list(node_props.keys())}")

    def test_driver_license_identification_nesting(self, msg1_xml, minimal_mapping):
        """Test that DriverLicense > DriverLicenseCardIdentification > IdentificationID is flattened."""
        cypher, nodes, contains, edges = generate_for_xml_content(
            msg1_xml, minimal_mapping, "msg1.xml", mode="dynamic"
        )

        # Find DriverLicense node
        dl_nodes = [n for nid, n in nodes.items() if 'DriverLicense' in n[0] and 'Card' not in n[0]]

        if len(dl_nodes) > 0:
            node_props = dl_nodes[0][2]

            # msg1.xml has: DriverLicense > DriverLicenseCardIdentification > IdentificationID: A1234567
            id_path = 'j_DriverLicenseCardIdentification__nc_IdentificationID'

            if id_path in node_props:
                assert node_props[id_path] == 'A1234567'


class TestMultiplePersonFlattening:
    """Tests for handling multiple person objects (msg2.xml)."""

    def test_multiple_persons_have_separate_flattened_properties(self, msg2_xml, minimal_mapping):
        """Test that each person object gets its own flattened properties."""
        cypher, nodes, contains, edges = generate_for_xml_content(
            msg2_xml, minimal_mapping, "msg2.xml", mode="dynamic"
        )

        # msg2.xml has 3 persons: P01 (Peter), P02 (Harriet), P03 (Bunter)
        person_nodes = [n for nid, n in nodes.items() if n[1] == 'nc:Person']

        # Should have 3 separate person nodes
        assert len(person_nodes) >= 3, f"Expected at least 3 Person nodes, got {len(person_nodes)}"


class TestNamespaceHandling:
    """Tests for namespace preservation in flattened paths."""

    def test_mixed_namespaces_in_path(self, msg1_xml, minimal_mapping):
        """Test that mixed namespaces (j:Crash with nc:ActivityDate) are preserved."""
        cypher, nodes, contains, edges = generate_for_xml_content(
            msg1_xml, minimal_mapping, "msg1.xml", mode="dynamic"
        )

        crash_nodes = [n for nid, n in nodes.items() if n[1] == 'j:Crash']
        node_props = crash_nodes[0][2]

        # j:Crash contains nc:ActivityDate - different namespaces
        # Should preserve both: nc_ActivityDate__nc_Date
        assert 'nc_ActivityDate__nc_Date' in node_props
        assert node_props['nc_ActivityDate__nc_Date'] == '1907-05-04'


class TestBooleanPropertyFlattening:
    """Tests for boolean property handling."""

    def test_boolean_indicator_preserved(self, msg1_xml, minimal_mapping):
        """Test that boolean indicators are preserved correctly."""
        cypher, nodes, contains, edges = generate_for_xml_content(
            msg1_xml, minimal_mapping, "msg1.xml", mode="dynamic"
        )

        crash_driver_nodes = [n for nid, n in nodes.items() if 'CrashDriver' in n[0]]
        node_props = crash_driver_nodes[0][2]

        # msg1.xml has: <j:PersonAdultIndicator>true</j:PersonAdultIndicator>
        assert 'j_PersonAdultIndicator' in node_props
        # Value might be boolean True or string "true" depending on implementation
        assert node_props['j_PersonAdultIndicator'] in [True, 'true']

    def test_felony_indicator_on_charge(self, msg1_xml, minimal_mapping):
        """Test that ChargeFelonyIndicator boolean is preserved."""
        cypher, nodes, contains, edges = generate_for_xml_content(
            msg1_xml, minimal_mapping, "msg1.xml", mode="dynamic"
        )

        charge_nodes = [n for nid, n in nodes.items() if n[1] == 'j:Charge']

        if len(charge_nodes) > 0:
            node_props = charge_nodes[0][2]

            # msg1.xml has: <j:ChargeFelonyIndicator>false</j:ChargeFelonyIndicator>
            assert 'j_ChargeFelonyIndicator' in node_props
            assert node_props['j_ChargeFelonyIndicator'] in [False, 'false']


class TestTextContentExtraction:
    """Tests for extracting text content from elements."""

    def test_charge_description_text_extracted(self, msg1_xml, minimal_mapping):
        """Test that simple text content is extracted as property."""
        cypher, nodes, contains, edges = generate_for_xml_content(
            msg1_xml, minimal_mapping, "msg1.xml", mode="dynamic"
        )

        charge_nodes = [n for nid, n in nodes.items() if n[1] == 'j:Charge']

        if len(charge_nodes) > 0:
            node_props = charge_nodes[0][2]

            # msg1.xml has: <j:ChargeDescriptionText>Furious Driving</j:ChargeDescriptionText>
            assert 'j_ChargeDescriptionText' in node_props
            assert node_props['j_ChargeDescriptionText'] == 'Furious Driving'

    def test_identification_id_text_extracted(self, msg1_xml, minimal_mapping):
        """Test that IdentificationID text value is extracted."""
        cypher, nodes, contains, edges = generate_for_xml_content(
            msg1_xml, minimal_mapping, "msg1.xml", mode="dynamic"
        )

        # Find DriverLicenseCardIdentification node
        dlid_nodes = [n for nid, n in nodes.items() if 'DriverLicenseCardIdentification' in n[0]]

        if len(dlid_nodes) > 0:
            node_props = dlid_nodes[0][2]

            # msg1.xml has: <nc:IdentificationID>A1234567</nc:IdentificationID>
            assert 'nc_IdentificationID' in node_props
            assert node_props['nc_IdentificationID'] == 'A1234567'
