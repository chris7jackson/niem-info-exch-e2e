#!/usr/bin/env python3

from xml.etree import ElementTree as ET

import pytest

from niem_api.services.domain.schema.mapping import (
    build_element_to_class,
    build_prefix_map,
    generate_mapping_from_cmf_content,
    parse_classes,
    to_label,
    to_qname,
    to_rel_type,
)


class TestCMFToMapping:
    """Test suite for CMF to mapping conversion functions"""

    @pytest.fixture
    def sample_cmf_content(self):
        """Sample CMF content for testing"""
        return '''<?xml version="1.0" encoding="UTF-8"?>
        <cmf:Model xmlns:cmf="https://docs.oasis-open.org/niemopen/ns/specification/cmf/1.0/"
                   xmlns:structures="https://docs.oasis-open.org/niemopen/ns/model/structures/6.0/">
            <cmf:Namespace>
                <cmf:NamespaceURI>http://example.com/test</cmf:NamespaceURI>
                <cmf:NamespacePrefixText>test</cmf:NamespacePrefixText>
            </cmf:Namespace>
            <cmf:Namespace>
                <cmf:NamespaceURI>http://release.niem.gov/niem/niem-core/5.0/</cmf:NamespaceURI>
                <cmf:NamespacePrefixText>nc</cmf:NamespacePrefixText>
            </cmf:Namespace>
            <cmf:Class structures:id="test.PersonType">
                <cmf:Name>PersonType</cmf:Name>
                <cmf:Namespace structures:ref="test"/>
                <cmf:SubClassOf structures:ref="nc.ObjectType"/>
                <cmf:ChildPropertyAssociation>
                    <cmf:ObjectProperty structures:ref="test.PersonName"/>
                    <cmf:MinOccursQuantity>1</cmf:MinOccursQuantity>
                    <cmf:MaxOccursQuantity>1</cmf:MaxOccursQuantity>
                </cmf:ChildPropertyAssociation>
            </cmf:Class>
            <cmf:Class structures:id="test.PersonAssociationType">
                <cmf:Name>PersonAssociationType</cmf:Name>
                <cmf:Namespace structures:ref="test"/>
                <cmf:SubClassOf structures:ref="nc.AssociationType"/>
                <cmf:ChildPropertyAssociation>
                    <cmf:ObjectProperty structures:ref="test.PersonSource"/>
                    <cmf:MinOccursQuantity>1</cmf:MinOccursQuantity>
                </cmf:ChildPropertyAssociation>
                <cmf:ChildPropertyAssociation>
                    <cmf:ObjectProperty structures:ref="test.PersonTarget"/>
                    <cmf:MinOccursQuantity>1</cmf:MinOccursQuantity>
                </cmf:ChildPropertyAssociation>
            </cmf:Class>
            <cmf:ObjectProperty structures:id="test.Person">
                <cmf:Class structures:ref="test.PersonType"/>
            </cmf:ObjectProperty>
            <cmf:ObjectProperty structures:id="test.PersonName">
                <cmf:Class structures:ref="nc.TextType"/>
            </cmf:ObjectProperty>
        </cmf:Model>'''

    def test_to_qname_conversion(self):
        """Test dotted notation to QName conversion"""
        assert to_qname("test.PersonType") == "test:PersonType"
        assert to_qname("nc.ObjectType") == "nc:ObjectType"
        assert to_qname("simple") == "simple"

    def test_to_label_conversion(self):
        """Test QName to label conversion"""
        assert to_label("test:PersonType") == "test_PersonType"
        assert to_label("nc:ObjectType") == "nc_ObjectType"
        assert to_label("test.PersonType") == "test_PersonType"

    def test_to_rel_type_conversion(self):
        """Test relationship type conversion"""
        assert to_rel_type("test:PersonAssociation") == "TEST_PERSONASSOCIATION"
        assert to_rel_type("nc:Association") == "NC_ASSOCIATION"
        assert to_rel_type("test.person-knows") == "TEST_PERSON_KNOWS"

    def test_build_prefix_map(self, sample_cmf_content):
        """Test namespace prefix mapping extraction"""
        root = ET.fromstring(sample_cmf_content)
        prefixes = build_prefix_map(root)

        assert "test" in prefixes
        assert "nc" in prefixes
        assert prefixes["test"] == "http://example.com/test"
        assert prefixes["nc"] == "http://release.niem.gov/niem/niem-core/5.0/"

    def test_parse_classes(self, sample_cmf_content):
        """Test CMF class parsing"""
        root = ET.fromstring(sample_cmf_content)
        classes = parse_classes(root)

        assert len(classes) == 2

        # Find PersonType class
        person_class = next((c for c in classes if c["id"] == "test.PersonType"), None)
        assert person_class is not None
        assert person_class["name"] == "PersonType"
        assert person_class["subclass_of"] == "nc.ObjectType"
        assert len(person_class["props"]) == 1

        # Find AssociationType class
        assoc_class = next((c for c in classes if c["id"] == "test.PersonAssociationType"), None)
        assert assoc_class is not None
        assert assoc_class["subclass_of"] == "nc.AssociationType"
        assert len(assoc_class["props"]) == 2

    def test_build_element_to_class(self, sample_cmf_content):
        """Test element to class mapping"""
        root = ET.fromstring(sample_cmf_content)
        mapping = build_element_to_class(root)

        assert "test.Person" in mapping
        assert mapping["test.Person"] == "test.PersonType"

    def test_generate_mapping_from_cmf_content(self, sample_cmf_content):
        """Test complete mapping generation from CMF"""
        mapping = generate_mapping_from_cmf_content(sample_cmf_content)

        # Check structure
        assert "namespaces" in mapping
        assert "objects" in mapping
        assert "associations" in mapping
        assert "references" in mapping
        assert "augmentations" in mapping
        assert "polymorphism" in mapping

        # Check namespaces (only test namespace has defined classes)
        assert "test" in mapping["namespaces"]
        # nc namespace is referenced but has no classes defined in this CMF, so it won't be in used namespaces

        # Check objects (non-association types)
        objects = mapping["objects"]
        assert len(objects) == 1
        person_obj = objects[0]
        assert person_obj["qname"] == "test:Person"
        assert person_obj["label"] == "test_Person"
        assert person_obj["carries_structures_id"] is True

        # Check associations
        associations = mapping["associations"]
        assert len(associations) == 1
        person_assoc = associations[0]
        assert (
            "test:PersonAssociation" in person_assoc["qname"]
            or "test:PersonAssociationType" in person_assoc["qname"]
        )

        # Check polymorphism settings
        assert mapping["polymorphism"]["strategy"] == "extraLabel"
        assert mapping["polymorphism"]["store_actual_type_property"] == "xsiType"

    def test_generate_mapping_empty_cmf(self):
        """Test mapping generation with minimal CMF"""
        minimal_cmf = '''<?xml version="1.0" encoding="UTF-8"?>
        <cmf:Model xmlns:cmf="https://docs.oasis-open.org/niemopen/ns/specification/cmf/1.0/">
        </cmf:Model>'''

        mapping = generate_mapping_from_cmf_content(minimal_cmf)

        assert mapping["namespaces"] == {}
        assert mapping["objects"] == []
        assert mapping["associations"] == []
        assert mapping["references"] == []

    def test_generate_mapping_with_data_properties(self):
        """Test mapping generation with data properties"""
        cmf_with_data = '''<?xml version="1.0" encoding="UTF-8"?>
        <cmf:Model xmlns:cmf="https://docs.oasis-open.org/niemopen/ns/specification/cmf/1.0/"
                   xmlns:structures="https://docs.oasis-open.org/niemopen/ns/model/structures/6.0/">
            <cmf:Namespace>
                <cmf:NamespaceURI>http://example.com/test</cmf:NamespaceURI>
                <cmf:NamespacePrefixText>test</cmf:NamespacePrefixText>
            </cmf:Namespace>
            <cmf:Class structures:id="test.PersonType">
                <cmf:Name>PersonType</cmf:Name>
                <cmf:Namespace structures:ref="test"/>
                <cmf:SubClassOf structures:ref="nc.ObjectType"/>
                <cmf:ChildPropertyAssociation>
                    <cmf:DataProperty structures:ref="test.PersonAge"/>
                    <cmf:MinOccursQuantity>0</cmf:MinOccursQuantity>
                    <cmf:MaxOccursQuantity>1</cmf:MaxOccursQuantity>
                </cmf:ChildPropertyAssociation>
            </cmf:Class>
            <cmf:ObjectProperty structures:id="test.Person">
                <cmf:Class structures:ref="test.PersonType"/>
            </cmf:ObjectProperty>
        </cmf:Model>'''

        mapping = generate_mapping_from_cmf_content(cmf_with_data)

        # Should still generate objects even with data properties
        assert len(mapping["objects"]) == 1
        assert mapping["objects"][0]["qname"] == "test:Person"

    def test_class_property_parsing_edge_cases(self):
        """Test edge cases in class property parsing"""
        cmf_edge_case = '''<?xml version="1.0" encoding="UTF-8"?>
        <cmf:Model xmlns:cmf="https://docs.oasis-open.org/niemopen/ns/specification/cmf/1.0/"
                   xmlns:structures="https://docs.oasis-open.org/niemopen/ns/model/structures/6.0/">
            <cmf:Class structures:id="test.EmptyClass">
                <cmf:Name>EmptyClass</cmf:Name>
                <!-- No properties -->
            </cmf:Class>
            <cmf:Class structures:id="test.ClassWithMissingCardinality">
                <cmf:ChildPropertyAssociation>
                    <cmf:ObjectProperty structures:ref="test.SomeProperty"/>
                    <!-- Missing min/max occurs -->
                </cmf:ChildPropertyAssociation>
            </cmf:Class>
        </cmf:Model>'''

        root = ET.fromstring(cmf_edge_case)
        classes = parse_classes(root)

        empty_class = next((c for c in classes if c["id"] == "test.EmptyClass"), None)
        assert empty_class is not None
        assert len(empty_class["props"]) == 0

        class_with_missing = next((c for c in classes if c["id"] == "test.ClassWithMissingCardinality"), None)
        assert class_with_missing is not None
        assert len(class_with_missing["props"]) == 1
        prop = class_with_missing["props"][0]
        assert prop["min"] is None
        assert prop["max"] is None
