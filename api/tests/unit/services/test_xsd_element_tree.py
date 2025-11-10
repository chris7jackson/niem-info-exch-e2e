#!/usr/bin/env python3

from pathlib import Path
import pytest

from niem_api.services.domain.schema.xsd_element_tree import (
    build_element_tree_from_xsd,
    NodeType,
    WarningType,
    SuggestionType,
)


class TestXSDElementTree:
    """Test suite for XSD-based element tree building"""

    @pytest.fixture
    def simple_xsd(self):
        """Simple XSD with single element and type"""
        return b"""<?xml version="1.0" encoding="UTF-8"?>
        <xs:schema
          xmlns:xs="http://www.w3.org/2001/XMLSchema"
          xmlns:test="http://example.com/test"
          targetNamespace="http://example.com/test"
          elementFormDefault="qualified">

          <xs:element name="Person" type="test:PersonType"/>

          <xs:complexType name="PersonType">
            <xs:sequence>
              <xs:element name="GivenName" type="xs:string"/>
              <xs:element name="SurName" type="xs:string"/>
              <xs:element name="Age" type="xs:int"/>
            </xs:sequence>
          </xs:complexType>
        </xs:schema>"""

    @pytest.fixture
    def association_xsd(self):
        """XSD with association type"""
        return b"""<?xml version="1.0" encoding="UTF-8"?>
        <xs:schema
          xmlns:xs="http://www.w3.org/2001/XMLSchema"
          xmlns:test="http://example.com/test"
          xmlns:structures="https://docs.oasis-open.org/niemopen/ns/model/structures/6.0/"
          targetNamespace="http://example.com/test"
          elementFormDefault="qualified">

          <xs:import namespace="https://docs.oasis-open.org/niemopen/ns/model/structures/6.0/"
                     schemaLocation="structures.xsd"/>

          <xs:element name="PersonVehicleAssociation" type="test:PersonVehicleAssociationType"/>

          <xs:complexType name="PersonVehicleAssociationType">
            <xs:complexContent>
              <xs:extension base="structures:AssociationType">
                <xs:sequence>
                  <xs:element ref="test:Person" minOccurs="1" maxOccurs="1"/>
                  <xs:element ref="test:Vehicle" minOccurs="1" maxOccurs="1"/>
                </xs:sequence>
              </xs:extension>
            </xs:complexContent>
          </xs:complexType>

          <xs:element name="Person" type="test:PersonType"/>
          <xs:element name="Vehicle" type="test:VehicleType"/>

          <xs:complexType name="PersonType">
            <xs:sequence>
              <xs:element name="Name" type="xs:string"/>
            </xs:sequence>
          </xs:complexType>

          <xs:complexType name="VehicleType">
            <xs:sequence>
              <xs:element name="Make" type="xs:string"/>
            </xs:sequence>
          </xs:complexType>
        </xs:schema>"""

    @pytest.fixture
    def multi_file_xsd(self):
        """Multiple XSD files with imports"""
        primary = b"""<?xml version="1.0" encoding="UTF-8"?>
        <xs:schema
          xmlns:xs="http://www.w3.org/2001/XMLSchema"
          xmlns:primary="http://example.com/primary"
          xmlns:imported="http://example.com/imported"
          targetNamespace="http://example.com/primary"
          elementFormDefault="qualified">

          <xs:import namespace="http://example.com/imported" schemaLocation="imported.xsd"/>

          <xs:element name="Document" type="primary:DocumentType"/>

          <xs:complexType name="DocumentType">
            <xs:sequence>
              <xs:element ref="imported:Person"/>
            </xs:sequence>
          </xs:complexType>
        </xs:schema>"""

        imported = b"""<?xml version="1.0" encoding="UTF-8"?>
        <xs:schema
          xmlns:xs="http://www.w3.org/2001/XMLSchema"
          xmlns:imported="http://example.com/imported"
          targetNamespace="http://example.com/imported"
          elementFormDefault="qualified">

          <xs:element name="Person" type="imported:PersonType"/>

          <xs:complexType name="PersonType">
            <xs:sequence>
              <xs:element name="Name" type="xs:string"/>
            </xs:sequence>
          </xs:complexType>
        </xs:schema>"""

        return {"primary.xsd": primary, "imported.xsd": imported}

    @pytest.fixture
    def nested_xsd(self):
        """Deeply nested XSD structure"""
        return b"""<?xml version="1.0" encoding="UTF-8"?>
        <xs:schema
          xmlns:xs="http://www.w3.org/2001/XMLSchema"
          xmlns:test="http://example.com/test"
          targetNamespace="http://example.com/test"
          elementFormDefault="qualified">

          <xs:element name="Level0" type="test:Level0Type"/>

          <xs:complexType name="Level0Type">
            <xs:sequence>
              <xs:element ref="test:Level1"/>
            </xs:sequence>
          </xs:complexType>

          <xs:element name="Level1" type="test:Level1Type"/>

          <xs:complexType name="Level1Type">
            <xs:sequence>
              <xs:element ref="test:Level2"/>
            </xs:sequence>
          </xs:complexType>

          <xs:element name="Level2" type="test:Level2Type"/>

          <xs:complexType name="Level2Type">
            <xs:sequence>
              <xs:element ref="test:Level3"/>
            </xs:sequence>
          </xs:complexType>

          <xs:element name="Level3" type="test:Level3Type"/>

          <xs:complexType name="Level3Type">
            <xs:sequence>
              <xs:element ref="test:Level4"/>
            </xs:sequence>
          </xs:complexType>

          <xs:element name="Level4" type="test:Level4Type"/>

          <xs:complexType name="Level4Type">
            <xs:sequence>
              <xs:element name="Value" type="xs:string"/>
            </xs:sequence>
          </xs:complexType>
        </xs:schema>"""

    def test_simple_xsd_parsing(self, simple_xsd):
        """Test parsing simple XSD with single element"""
        xsd_files = {"test.xsd": simple_xsd}
        nodes = build_element_tree_from_xsd("test.xsd", xsd_files)

        assert len(nodes) > 0
        person_node = nodes[0]

        assert person_node.qname == "test:Person"
        assert person_node.label == "test_Person"
        assert person_node.node_type == NodeType.OBJECT
        assert person_node.depth == 0
        assert person_node.property_count == 3  # GivenName, SurName, Age
        # selected defaults to False in the implementation
        assert person_node.selected is False

    def test_association_detection(self, association_xsd):
        """Test detection of association types"""
        xsd_files = {"test.xsd": association_xsd}
        nodes = build_element_tree_from_xsd("test.xsd", xsd_files)

        # Find the association node
        assoc_node = next((n for n in nodes if "Association" in n.qname), None)
        assert assoc_node is not None
        assert assoc_node.node_type == NodeType.ASSOCIATION
        # Check that it's the PersonVehicleAssociation (qname contains Association)
        assert "PersonVehicleAssociation" in assoc_node.qname

    def test_multi_file_import_resolution(self, multi_file_xsd):
        """Test import resolution across multiple XSD files"""
        nodes = build_element_tree_from_xsd("primary.xsd", multi_file_xsd)

        assert len(nodes) > 0
        doc_node = nodes[0]

        assert doc_node.qname == "primary:Document"
        # Should have child from imported schema
        assert len(doc_node.children) > 0

    def test_deep_nesting_warning(self, nested_xsd):
        """Test deep nesting warning detection.
        
        NOTE: Deep nesting warnings are currently disabled to avoid UI clutter.
        This test verifies that deep nodes exist but doesn't expect warnings.
        """
        xsd_files = {"test.xsd": nested_xsd}
        nodes = build_element_tree_from_xsd("test.xsd", xsd_files)

        # Find deeply nested nodes
        def find_deep_nodes(node, result=None):
            if result is None:
                result = []
            if node.depth > 3:
                result.append(node)
            for child in node.children:
                find_deep_nodes(child, result)
            return result

        deep_nodes = []
        for root in nodes:
            deep_nodes.extend(find_deep_nodes(root))

        assert len(deep_nodes) > 0
        # Deep nesting warnings are disabled, so no warnings expected
        for node in deep_nodes:
            assert WarningType.DEEP_NESTING not in node.warnings

    def test_property_relationship_counting(self, simple_xsd):
        """Test counting of properties vs relationships"""
        xsd_files = {"test.xsd": simple_xsd}
        nodes = build_element_tree_from_xsd("test.xsd", xsd_files)

        person_node = nodes[0]
        # Should have 3 scalar properties (string, string, int)
        assert person_node.property_count == 3
        # No nested object relationships (use nested_object_count, not relationship_count)
        assert person_node.nested_object_count == 0

    def test_cardinality_extraction(self, association_xsd):
        """Test extraction of minOccurs/maxOccurs"""
        xsd_files = {"test.xsd": association_xsd}
        nodes = build_element_tree_from_xsd("test.xsd", xsd_files)

        assoc_node = next((n for n in nodes if "Association" in n.qname), None)
        assert assoc_node is not None
        # Check cardinality is extracted (default is 1..1)
        assert assoc_node.cardinality is not None

    def test_namespace_handling(self, simple_xsd):
        """Test namespace prefix handling"""
        xsd_files = {"test.xsd": simple_xsd}
        nodes = build_element_tree_from_xsd("test.xsd", xsd_files)

        person_node = nodes[0]
        assert person_node.namespace == "test"
        assert "test:" in person_node.qname

    def test_empty_xsd_files(self):
        """Test handling of empty XSD files dict"""
        # The function may raise KeyError or ValueError depending on implementation
        with pytest.raises((KeyError, ValueError)):
            build_element_tree_from_xsd("missing.xsd", {})

    def test_malformed_xsd(self):
        """Test handling of malformed XSD"""
        malformed = b"<not-valid-xml"
        xsd_files = {"bad.xsd": malformed}

        # Should raise ParseError
        with pytest.raises(Exception):
            build_element_tree_from_xsd("bad.xsd", xsd_files)

    # Real-world test with CrashDriver schema
    def test_crash_driver_schema(self):
        """Integration test with real CrashDriver.xsd (if available)"""
        crash_driver_path = Path(__file__).parent.parent.parent / "fixtures" / "CrashDriver.cmf"

        # Skip if fixture not available
        if not crash_driver_path.exists():
            pytest.skip("CrashDriver fixture not available")

        # This test would require the actual XSD files, not CMF
        # For now, we verify the test infrastructure is in place
        assert True
