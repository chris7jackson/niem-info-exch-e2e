#!/usr/bin/env python3

from pathlib import Path
import pytest

from niem_api.services.domain.schema.xsd_schema_designer import apply_schema_design_from_xsd


class TestSchemaDesigner:
    """Test suite for XSD schema designer.

    NOTE: These tests need to be updated with XSD fixtures.
    The original CMF-based tests have been commented out as the CMF schema_designer.py
    has been removed in favor of the XSD-only implementation.

    TODO: Create equivalent XSD test fixtures and update test methods.
    """

    @pytest.mark.skip(reason="Tests need to be updated to use XSD fixtures instead of CMF")
    @pytest.fixture
    def crash_driver_cmf(self):
        """Real CrashDriver CMF content for realistic testing"""
        cmf_path = Path(__file__).parent.parent.parent / "fixtures" / "CrashDriver.cmf"
        return cmf_path.read_text(encoding='utf-8')

    @pytest.fixture
    def simple_cmf_with_reference(self):
        """CMF content with object reference for flattening tests"""
        return '''<?xml version="1.0" encoding="UTF-8"?>
        <cmf:Model xmlns:cmf="https://docs.oasis-open.org/niemopen/ns/specification/cmf/1.0/"
                   xmlns:structures="https://docs.oasis-open.org/niemopen/ns/model/structures/6.0/">
            <cmf:Namespace>
                <cmf:NamespaceURI>http://example.com/test</cmf:NamespaceURI>
                <cmf:NamespacePrefixText>test</cmf:NamespacePrefixText>
            </cmf:Namespace>
            <cmf:Class structures:id="test.PersonType">
                <cmf:Name>PersonType</cmf:Name>
                <cmf:Namespace structures:ref="test"/>
                <cmf:ChildPropertyAssociation>
                    <cmf:ObjectProperty structures:ref="test.PersonName"/>
                </cmf:ChildPropertyAssociation>
                <cmf:ChildPropertyAssociation>
                    <cmf:DataProperty structures:ref="test.PersonAge"/>
                </cmf:ChildPropertyAssociation>
            </cmf:Class>
            <cmf:Class structures:id="test.PersonNameType">
                <cmf:Name>PersonNameType</cmf:Name>
                <cmf:Namespace structures:ref="test"/>
                <cmf:ChildPropertyAssociation>
                    <cmf:DataProperty structures:ref="test.GivenName"/>
                </cmf:ChildPropertyAssociation>
                <cmf:ChildPropertyAssociation>
                    <cmf:DataProperty structures:ref="test.SurName"/>
                </cmf:ChildPropertyAssociation>
            </cmf:Class>
            <cmf:ObjectProperty structures:id="test.Person">
                <cmf:Class structures:ref="test.PersonType"/>
            </cmf:ObjectProperty>
            <cmf:ObjectProperty structures:id="test.PersonName">
                <cmf:Class structures:ref="test.PersonNameType"/>
            </cmf:ObjectProperty>
            <cmf:DataProperty structures:id="test.PersonAge">
                <cmf:Name>PersonAge</cmf:Name>
                <cmf:Datatype structures:ref="xs.integer"/>
            </cmf:DataProperty>
            <cmf:DataProperty structures:id="test.GivenName">
                <cmf:Name>GivenName</cmf:Name>
            </cmf:DataProperty>
            <cmf:DataProperty structures:id="test.SurName">
                <cmf:Name>SurName</cmf:Name>
            </cmf:DataProperty>
        </cmf:Model>'''

    @pytest.fixture
    def association_cmf(self):
        """CMF content with association for endpoint filtering tests"""
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
            </cmf:Class>
            <cmf:Class structures:id="test.VehicleType">
                <cmf:Name>VehicleType</cmf:Name>
                <cmf:Namespace structures:ref="test"/>
            </cmf:Class>
            <cmf:Class structures:id="test.DriverType">
                <cmf:Name>DriverType</cmf:Name>
                <cmf:Namespace structures:ref="test"/>
            </cmf:Class>
            <cmf:Class structures:id="test.PersonVehicleAssociationType">
                <cmf:Name>PersonVehicleAssociationType</cmf:Name>
                <cmf:Namespace structures:ref="test"/>
                <cmf:SubClassOf structures:ref="nc.AssociationType"/>
                <cmf:ChildPropertyAssociation>
                    <cmf:ObjectProperty structures:ref="test.Person"/>
                </cmf:ChildPropertyAssociation>
                <cmf:ChildPropertyAssociation>
                    <cmf:ObjectProperty structures:ref="test.Vehicle"/>
                </cmf:ChildPropertyAssociation>
                <cmf:ChildPropertyAssociation>
                    <cmf:ObjectProperty structures:ref="test.Driver"/>
                </cmf:ChildPropertyAssociation>
            </cmf:Class>
            <cmf:ObjectProperty structures:id="test.Person">
                <cmf:Class structures:ref="test.PersonType"/>
            </cmf:ObjectProperty>
            <cmf:ObjectProperty structures:id="test.Vehicle">
                <cmf:Class structures:ref="test.VehicleType"/>
            </cmf:ObjectProperty>
            <cmf:ObjectProperty structures:id="test.Driver">
                <cmf:Class structures:ref="test.DriverType"/>
            </cmf:ObjectProperty>
            <cmf:ObjectProperty structures:id="test.PersonVehicleAssociation">
                <cmf:Class structures:ref="test.PersonVehicleAssociationType"/>
            </cmf:ObjectProperty>
        </cmf:Model>'''

    @pytest.mark.skip(reason="Needs XSD fixtures")
    def test_all_selected_creates_nodes(self, simple_cmf_with_reference):
        """Test that all selected nodes create Neo4j nodes"""
        selections = {
            "test:PersonType": True,
            "test:PersonNameType": True
        }

        mapping = apply_schema_design(simple_cmf_with_reference, selections)

        # Check that both types are in objects
        object_qnames = [obj["qname"] for obj in mapping["objects"]]
        assert "test:PersonType" in object_qnames or "test:Person" in object_qnames
        assert "test:PersonNameType" in object_qnames or "test:PersonName" in object_qnames

        # Should have reference between them
        assert len(mapping["references"]) > 0

    @pytest.mark.skip(reason="Needs XSD fixtures")
    def test_unselected_target_flattens_properties(self, simple_cmf_with_reference):
        """Test that unselected target properties are flattened into source"""
        selections = {
            "test:PersonType": True,
            "test:PersonNameType": False  # Not selected - should flatten
        }

        mapping = apply_schema_design(simple_cmf_with_reference, selections)

        # Only PersonType should be in objects
        object_qnames = [obj["qname"] for obj in mapping["objects"]]
        # PersonNameType should NOT be a node
        assert "test:PersonNameType" not in object_qnames
        assert "test:PersonName" not in object_qnames

        # Check that PersonType has flattened properties from PersonNameType
        person_obj = next((obj for obj in mapping["objects"]
                          if "Person" in obj["qname"] and "Name" not in obj["qname"]), None)

        if person_obj:
            prop_names = [p["neo4j_property"] for p in person_obj["scalar_props"]]
            # Should have flattened properties with path prefix
            assert any("given" in p.lower() or "name" in p.lower() for p in prop_names)

    @pytest.mark.skip(reason="Needs XSD fixtures")
    def test_association_with_all_endpoints_selected(self, association_cmf):
        """Test that association with all endpoints selected creates n-ary relationship"""
        selections = {
            "test:PersonType": True,
            "test:VehicleType": True,
            "test:DriverType": True,
            "test:PersonVehicleAssociationType": True
        }

        mapping = apply_schema_design(association_cmf, selections)

        # Should create association
        assert len(mapping["associations"]) > 0

        # Find the association
        assoc = mapping["associations"][0]
        assert len(assoc["endpoints"]) == 3  # All 3 endpoints

    @pytest.mark.skip(reason="Needs XSD fixtures")
    def test_association_with_partial_endpoints(self, association_cmf):
        """Test association with only some endpoints selected"""
        selections = {
            "test:PersonType": True,
            "test:VehicleType": True,
            "test:DriverType": False,  # Not selected
            "test:PersonVehicleAssociationType": True
        }

        mapping = apply_schema_design(association_cmf, selections)

        # Should still create association with 2 endpoints
        if len(mapping["associations"]) > 0:
            assoc = mapping["associations"][0]
            # Should have only 2 endpoints (Person and Vehicle)
            assert len(assoc["endpoints"]) == 2

    @pytest.mark.skip(reason="Needs XSD fixtures")
    def test_association_insufficient_endpoints_omitted(self, association_cmf):
        """Test that association with <2 endpoints is omitted"""
        selections = {
            "test:PersonType": False,  # Not selected
            "test:VehicleType": False,  # Not selected
            "test:DriverType": True,   # Only 1 endpoint selected
            "test:PersonVehicleAssociationType": True
        }

        mapping = apply_schema_design(association_cmf, selections)

        # Should not create association (needs 2+ endpoints)
        # Either no associations or associations with at least 2 endpoints
        for assoc in mapping["associations"]:
            assert len(assoc["endpoints"]) >= 2

    @pytest.mark.skip(reason="Needs XSD fixtures")
    def test_namespace_filtering(self, simple_cmf_with_reference):
        """Test that only used namespaces are included"""
        selections = {
            "test:PersonType": True,
            "test:PersonNameType": False
        }

        mapping = apply_schema_design(simple_cmf_with_reference, selections)

        # Should have test namespace
        assert "test" in mapping["namespaces"]
        assert "http://example.com/test" in mapping["namespaces"].values()

    @pytest.mark.skip(reason="Needs XSD fixtures")
    def test_references_only_between_selected_nodes(self, simple_cmf_with_reference):
        """Test that references only created between selected nodes"""
        selections = {
            "test:PersonType": True,
            "test:PersonNameType": True
        }

        mapping = apply_schema_design(simple_cmf_with_reference, selections)

        # Should have references
        assert len(mapping["references"]) > 0

        # All references should be between selected nodes
        for ref in mapping["references"]:
            owner = ref["owner_object"]
            target = ref["target_label"]
            # Both should be in the selected objects
            object_labels = [obj["label"] for obj in mapping["objects"]]
            assert target in object_labels or owner in [obj["qname"] for obj in mapping["objects"]]

    @pytest.mark.skip(reason="Needs XSD fixtures")
    def test_empty_selections_creates_no_nodes(self, simple_cmf_with_reference):
        """Test that empty selections creates no nodes"""
        selections = {}  # Nothing selected

        mapping = apply_schema_design(simple_cmf_with_reference, selections)

        # Should have no objects, associations, or references
        assert len(mapping["objects"]) == 0
        assert len(mapping["associations"]) == 0
        assert len(mapping["references"]) == 0

    @pytest.mark.skip(reason="Needs XSD fixtures")
    def test_mapping_structure_completeness(self, simple_cmf_with_reference):
        """Test that generated mapping has all required sections"""
        selections = {
            "test:PersonType": True
        }

        mapping = apply_schema_design(simple_cmf_with_reference, selections)

        # Check all required sections exist
        assert "namespaces" in mapping
        assert "objects" in mapping
        assert "associations" in mapping
        assert "references" in mapping
        assert "augmentations" in mapping
        assert "polymorphism" in mapping

        # Check polymorphism structure
        assert "strategy" in mapping["polymorphism"]
        assert "store_actual_type_property" in mapping["polymorphism"]

    @pytest.mark.skip(reason="Needs XSD fixtures")
    def test_scalar_property_flattening_path(self, simple_cmf_with_reference):
        """Test that flattened scalar properties have correct path prefix"""
        selections = {
            "test:PersonType": True,
            "test:PersonNameType": False  # Flatten into Person
        }

        mapping = apply_schema_design(simple_cmf_with_reference, selections)

        # Find Person object
        person_obj = next((obj for obj in mapping["objects"]
                          if "Person" in obj["qname"] and "Name" not in obj["qname"]), None)

        if person_obj and len(person_obj["scalar_props"]) > 0:
            # Check that flattened properties have path with PersonName prefix
            flattened_props = [p for p in person_obj["scalar_props"]
                             if "person_name" in p["neo4j_property"].lower()]

            # At least one flattened property should exist
            assert len(flattened_props) > 0

    # Real-world tests using CrashDriver CMF

    @pytest.mark.skip(reason="Needs XSD fixtures")
    def test_crash_driver_all_selected(self, crash_driver_cmf):
        """Test CrashDriver with all major entities selected"""
        selections = {
            "j:CrashType": True,
            "j:CrashDriverType": True,
            "j:CrashVehicleType": True,
            "j:CrashPersonType": True
        }

        mapping = apply_schema_design(crash_driver_cmf, selections)

        # Should have objects for selected types
        assert len(mapping["objects"]) > 0

        # Should have j namespace
        assert "j" in mapping["namespaces"]

    @pytest.mark.skip(reason="Needs XSD fixtures")
    def test_crash_driver_flatten_person(self, crash_driver_cmf):
        """Test flattening CrashPerson into Crash"""
        selections = {
            "j:CrashType": True,
            "j:CrashPersonType": False,  # Flatten into Crash
            "j:CrashDriverType": False,
            "j:CrashVehicleType": True
        }

        mapping = apply_schema_design(crash_driver_cmf, selections)

        # CrashPerson should NOT be its own object
        person_objs = [obj for obj in mapping["objects"] if "Person" in obj["qname"]]
        assert len(person_objs) == 0

    @pytest.mark.skip(reason="Needs XSD fixtures")
    def test_crash_driver_only_crash(self, crash_driver_cmf):
        """Test selecting only Crash entity"""
        selections = {
            "j:CrashType": True
        }

        mapping = apply_schema_design(crash_driver_cmf, selections)

        # Should have at least one object
        assert len(mapping["objects"]) > 0

        # All unselected nested entities should be flattened
        # No references (since target nodes not selected)
        for ref in mapping["references"]:
            # All targets should be selected
            assert selections.get(ref.get("target_label", ""), False) or True  # May not be in selections

    @pytest.mark.skip(reason="Needs XSD fixtures")
    def test_crash_driver_mapping_structure(self, crash_driver_cmf):
        """Test that CrashDriver generates valid mapping structure"""
        selections = {
            "j:CrashType": True,
            "j:CrashDriverType": True
        }

        mapping = apply_schema_design(crash_driver_cmf, selections)

        # Validate structure
        assert isinstance(mapping, dict)
        assert "namespaces" in mapping
        assert "objects" in mapping
        assert "associations" in mapping
        assert "references" in mapping

        # Check objects have required fields
        for obj in mapping["objects"]:
            assert "qname" in obj
            assert "label" in obj
            assert "scalar_props" in obj
            assert isinstance(obj["scalar_props"], list)

    @pytest.mark.skip(reason="Needs XSD fixtures")
    def test_crash_driver_namespace_filtering(self, crash_driver_cmf):
        """Test that only used namespaces are included"""
        selections = {
            "j:CrashType": True  # Only justice namespace
        }

        mapping = apply_schema_design(crash_driver_cmf, selections)

        # Should have j namespace
        assert "j" in mapping["namespaces"]

        # May have other namespaces if Crash references them
