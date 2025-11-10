"""
Unit tests for XSD-based type discovery module.

Tests the schema-driven entity type discovery system that identifies
person and organization types from NIEM XSD schemas.
"""

import pytest
from niem_api.services.domain.schema.type_discovery import (
    build_substitution_index,
    build_type_hierarchy_index,
    find_elements_by_type,
    find_person_types,
    find_organization_types,
    is_person_entity_schema_based,
    is_organization_entity_schema_based,
    get_entity_category_from_schema,
    build_entity_discovery_indices,
)
from niem_api.services.domain.schema.xsd_element_tree import (
    TypeDefinition,
    ElementDeclaration,
)


class TestSubstitutionIndex:
    """Tests for substitution group index building."""

    def test_build_substitution_index_empty(self):
        """Test building index with no elements."""
        element_declarations = {}
        index = build_substitution_index(element_declarations)
        assert index == {}

    def test_build_substitution_index_single_group(self):
        """Test building index with single substitution group."""
        element_declarations = {
            "j:CrashDriver": ElementDeclaration(
                name="CrashDriver",
                namespace="http://justice",
                type_name="CrashDriverType",
                type_ref="j:CrashDriverType",
                min_occurs="0",
                max_occurs="1",
                documentation="Crash driver",
                is_augmentation_point=False,
                substitution_group="nc:Person",
            ),
            "j:Arrestee": ElementDeclaration(
                name="Arrestee",
                namespace="http://justice",
                type_name="ArresteeType",
                type_ref="j:ArresteeType",
                min_occurs="0",
                max_occurs="1",
                documentation="Arrestee",
                is_augmentation_point=False,
                substitution_group="nc:Person",
            ),
        }

        index = build_substitution_index(element_declarations)

        assert "nc:Person" in index
        assert len(index["nc:Person"]) == 2
        assert "j:CrashDriver" in index["nc:Person"]
        assert "j:Arrestee" in index["nc:Person"]

    def test_build_substitution_index_multiple_groups(self):
        """Test building index with multiple substitution groups."""
        element_declarations = {
            "j:CrashDriver": ElementDeclaration(
                name="CrashDriver",
                namespace="http://justice",
                type_name="CrashDriverType",
                type_ref="j:CrashDriverType",
                min_occurs="0",
                max_occurs="1",
                documentation="Crash driver",
                is_augmentation_point=False,
                substitution_group="nc:Person",
            ),
            "j:Agency": ElementDeclaration(
                name="Agency",
                namespace="http://justice",
                type_name="AgencyType",
                type_ref="j:AgencyType",
                min_occurs="0",
                max_occurs="1",
                documentation="Agency",
                is_augmentation_point=False,
                substitution_group="nc:Organization",
            ),
        }

        index = build_substitution_index(element_declarations)

        assert "nc:Person" in index
        assert "nc:Organization" in index
        assert "j:CrashDriver" in index["nc:Person"]
        assert "j:Agency" in index["nc:Organization"]


class TestTypeHierarchyIndex:
    """Tests for type hierarchy index building."""

    def test_build_type_hierarchy_index_empty(self):
        """Test building index with no types."""
        type_definitions = {}
        index = build_type_hierarchy_index(type_definitions)
        assert index == {}

    def test_build_type_hierarchy_index_direct_inheritance(self):
        """Test building index with direct type inheritance."""
        type_definitions = {
            "j:CrashDriverType": TypeDefinition(
                name="CrashDriverType",
                namespace="http://justice",
                is_simple=False,
                base_type="nc:PersonType",
                elements=[],
                is_association=False,
            ),
            "j:CrashPersonType": TypeDefinition(
                name="CrashPersonType",
                namespace="http://justice",
                is_simple=False,
                base_type="nc:PersonType",
                elements=[],
                is_association=False,
            ),
        }

        index = build_type_hierarchy_index(type_definitions)

        assert "nc:PersonType" in index
        assert len(index["nc:PersonType"]) == 2
        assert "j:CrashDriverType" in index["nc:PersonType"]
        assert "j:CrashPersonType" in index["nc:PersonType"]

    def test_build_type_hierarchy_index_transitive(self):
        """Test building index with transitive inheritance."""
        type_definitions = {
            "j:CrashDriverType": TypeDefinition(
                name="CrashDriverType",
                namespace="http://justice",
                is_simple=False,
                base_type="nc:PersonType",
                elements=[],
                is_association=False,
            ),
            "j:SpecialDriverType": TypeDefinition(
                name="SpecialDriverType",
                namespace="http://justice",
                is_simple=False,
                base_type="j:CrashDriverType",
                elements=[],
                is_association=False,
            ),
        }

        index = build_type_hierarchy_index(type_definitions)

        # nc:PersonType should have both CrashDriverType and SpecialDriverType
        assert "nc:PersonType" in index
        assert "j:CrashDriverType" in index["nc:PersonType"]
        assert "j:SpecialDriverType" in index["nc:PersonType"]

        # j:CrashDriverType should have SpecialDriverType
        assert "j:CrashDriverType" in index
        assert "j:SpecialDriverType" in index["j:CrashDriverType"]


class TestFindElementsByType:
    """Tests for finding elements by type reference."""

    def test_find_elements_by_type_empty(self):
        """Test with no elements."""
        element_declarations = {}
        result = find_elements_by_type("nc:PersonType", element_declarations)
        assert result == []

    def test_find_elements_by_type_match(self):
        """Test finding elements with matching type."""
        element_declarations = {
            "nc:Person": ElementDeclaration(
                name="Person",
                namespace="http://niem-core",
                type_name="PersonType",
                type_ref="nc:PersonType",
                min_occurs="0",
                max_occurs="1",
                documentation="Person",
                is_augmentation_point=False,
                substitution_group=None,
            ),
            "j:CrashDriver": ElementDeclaration(
                name="CrashDriver",
                namespace="http://justice",
                type_name="CrashDriverType",
                type_ref="j:CrashDriverType",
                min_occurs="0",
                max_occurs="1",
                documentation="Crash driver",
                is_augmentation_point=False,
                substitution_group="nc:Person",
            ),
        }

        result = find_elements_by_type("nc:PersonType", element_declarations)
        assert len(result) == 1
        assert "nc:Person" in result


class TestFindPersonTypes:
    """Tests for person type discovery."""

    def test_find_person_types_substitution_group(self):
        """Test finding person types via substitution group."""
        type_definitions = {}
        element_declarations = {
            "j:CrashDriver": ElementDeclaration(
                name="CrashDriver",
                namespace="http://justice",
                type_name="CrashDriverType",
                type_ref="j:CrashDriverType",
                min_occurs="0",
                max_occurs="1",
                documentation="Crash driver",
                is_augmentation_point=False,
                substitution_group="nc:Person",
            ),
            "j:CrashPerson": ElementDeclaration(
                name="CrashPerson",
                namespace="http://justice",
                type_name="CrashPersonType",
                type_ref="j:CrashPersonType",
                min_occurs="0",
                max_occurs="1",
                documentation="Crash person",
                is_augmentation_point=False,
                substitution_group="nc:Person",
            ),
        }

        substitution_index = build_substitution_index(element_declarations)
        type_hierarchy_index = build_type_hierarchy_index(type_definitions)

        person_types = find_person_types(
            type_definitions, element_declarations, substitution_index, type_hierarchy_index
        )

        assert len(person_types) == 2
        assert "j:CrashDriver" in person_types
        assert "j:CrashPerson" in person_types

    def test_find_person_types_type_extension(self):
        """Test finding person types via type extension."""
        type_definitions = {
            "j:CrashDriverType": TypeDefinition(
                name="CrashDriverType",
                namespace="http://justice",
                is_simple=False,
                base_type="nc:PersonType",
                elements=[],
                is_association=False,
            ),
        }
        element_declarations = {
            "j:CrashDriver": ElementDeclaration(
                name="CrashDriver",
                namespace="http://justice",
                type_name="CrashDriverType",
                type_ref="j:CrashDriverType",
                min_occurs="0",
                max_occurs="1",
                documentation="Crash driver",
                is_augmentation_point=False,
                substitution_group=None,
            ),
        }

        substitution_index = build_substitution_index(element_declarations)
        type_hierarchy_index = build_type_hierarchy_index(type_definitions)

        person_types = find_person_types(
            type_definitions, element_declarations, substitution_index, type_hierarchy_index
        )

        assert "j:CrashDriver" in person_types


class TestFindOrganizationTypes:
    """Tests for organization type discovery."""

    def test_find_organization_types_substitution_group(self):
        """Test finding organization types via substitution group."""
        type_definitions = {}
        element_declarations = {
            "j:Agency": ElementDeclaration(
                name="Agency",
                namespace="http://justice",
                type_name="AgencyType",
                type_ref="j:AgencyType",
                min_occurs="0",
                max_occurs="1",
                documentation="Agency",
                is_augmentation_point=False,
                substitution_group="nc:Organization",
            ),
        }

        substitution_index = build_substitution_index(element_declarations)
        type_hierarchy_index = build_type_hierarchy_index(type_definitions)

        org_types = find_organization_types(
            type_definitions, element_declarations, substitution_index, type_hierarchy_index
        )

        assert "j:Agency" in org_types


class TestEntityCategorization:
    """Tests for entity categorization functions."""

    def test_is_person_entity_schema_based(self):
        """Test schema-based person entity detection."""
        person_types = {"j:CrashDriver", "j:CrashPerson", "j:Arrestee"}

        assert is_person_entity_schema_based("j:CrashDriver", person_types)
        assert is_person_entity_schema_based("j:CrashPerson", person_types)
        assert not is_person_entity_schema_based("j:Agency", person_types)

    def test_is_organization_entity_schema_based(self):
        """Test schema-based organization entity detection."""
        org_types = {"j:Agency", "j:Organization"}

        assert is_organization_entity_schema_based("j:Agency", org_types)
        assert not is_organization_entity_schema_based("j:CrashDriver", org_types)

    def test_get_entity_category_from_schema_person(self):
        """Test getting entity category for person."""
        person_types = {"j:CrashDriver", "j:CrashPerson"}
        org_types = {"j:Agency"}

        category = get_entity_category_from_schema("j:CrashDriver", person_types, org_types)
        assert category == "person"

        category = get_entity_category_from_schema("j:CrashPerson", person_types, org_types)
        assert category == "person"

    def test_get_entity_category_from_schema_organization(self):
        """Test getting entity category for organization."""
        person_types = {"j:CrashDriver"}
        org_types = {"j:Agency", "j:Organization"}

        category = get_entity_category_from_schema("j:Agency", person_types, org_types)
        assert category == "organization"

    def test_get_entity_category_from_schema_none(self):
        """Test getting entity category for unknown type."""
        person_types = {"j:CrashDriver"}
        org_types = {"j:Agency"}

        category = get_entity_category_from_schema("j:Unknown", person_types, org_types)
        assert category is None


class TestBuildEntityDiscoveryIndices:
    """Tests for the convenience function that builds all indices."""

    def test_build_entity_discovery_indices(self):
        """Test building all discovery indices together."""
        type_definitions = {
            "j:CrashDriverType": TypeDefinition(
                name="CrashDriverType",
                namespace="http://justice",
                is_simple=False,
                base_type="nc:PersonType",
                elements=[],
                is_association=False,
            ),
        }
        element_declarations = {
            "j:CrashDriver": ElementDeclaration(
                name="CrashDriver",
                namespace="http://justice",
                type_name="CrashDriverType",
                type_ref="j:CrashDriverType",
                min_occurs="0",
                max_occurs="1",
                documentation="Crash driver",
                is_augmentation_point=False,
                substitution_group="nc:Person",
            ),
            "j:Agency": ElementDeclaration(
                name="Agency",
                namespace="http://justice",
                type_name="AgencyType",
                type_ref="j:AgencyType",
                min_occurs="0",
                max_occurs="1",
                documentation="Agency",
                is_augmentation_point=False,
                substitution_group="nc:Organization",
            ),
        }

        result = build_entity_discovery_indices(type_definitions, element_declarations)

        # Check structure
        assert "substitution_index" in result
        assert "type_hierarchy_index" in result
        assert "person_types" in result
        assert "organization_types" in result

        # Check content
        assert "nc:Person" in result["substitution_index"]
        assert "nc:Organization" in result["substitution_index"]
        assert "j:CrashDriver" in result["person_types"]
        assert "j:Agency" in result["organization_types"]
