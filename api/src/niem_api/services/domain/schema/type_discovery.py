"""
XSD-based type discovery for entity resolution.

This module provides schema-driven discovery of person and organization types
by analyzing NIEM XSD schemas. It identifies types through:
1. Substitution group membership (e.g., elements that substitute for nc:Person)
2. Type hierarchy (e.g., types that extend nc:PersonType)

This enables automatic recognition of entity types without hardcoded patterns.
"""

from typing import Optional
import logging

from .xsd_element_tree import TypeDefinition, ElementDeclaration

logger = logging.getLogger(__name__)


def build_substitution_index(
    element_declarations: dict[str, ElementDeclaration]
) -> dict[str, list[str]]:
    """
    Build an index mapping substitution group heads to their substitutable elements.

    For example:
    {
        "nc:Person": ["j:CrashDriver", "j:CrashPerson", "j:Arrestee", ...],
        "nc:Organization": ["j:Agency", ...]
    }

    Args:
        element_declarations: Dict mapping qualified names to ElementDeclaration objects

    Returns:
        Dict mapping substitution group head qnames to lists of element qnames
    """
    substitution_index: dict[str, list[str]] = {}

    for qname, elem_decl in element_declarations.items():
        if elem_decl.substitution_group:
            # Normalize the substitution group to qualified name format
            sub_group = elem_decl.substitution_group

            # Add to index
            if sub_group not in substitution_index:
                substitution_index[sub_group] = []
            substitution_index[sub_group].append(qname)

    logger.debug(f"Built substitution index with {len(substitution_index)} groups")
    return substitution_index


def build_type_hierarchy_index(
    type_definitions: dict[str, TypeDefinition]
) -> dict[str, list[str]]:
    """
    Build an index mapping base types to all derived types (recursively).

    For example:
    {
        "nc:PersonType": ["j:CrashDriverType", "j:CrashPersonType", ...],
        "nc:OrganizationType": ["j:AgencyType", ...]
    }

    Args:
        type_definitions: Dict mapping qualified names to TypeDefinition objects

    Returns:
        Dict mapping base type qnames to lists of derived type qnames
    """
    hierarchy_index: dict[str, list[str]] = {}

    # Build direct parent-child relationships
    for qname, type_def in type_definitions.items():
        if type_def.base_type:
            base = type_def.base_type
            if base not in hierarchy_index:
                hierarchy_index[base] = []
            hierarchy_index[base].append(qname)

    # Recursively expand to include all descendants
    def get_all_descendants(base_type: str, visited: set[str] | None = None) -> list[str]:
        if visited is None:
            visited = set()

        if base_type in visited:
            return []
        visited.add(base_type)

        descendants = []
        direct_children = hierarchy_index.get(base_type, [])

        for child in direct_children:
            descendants.append(child)
            # Recursively get grandchildren
            descendants.extend(get_all_descendants(child, visited))

        return descendants

    # Expand all entries to include transitive descendants
    expanded_index: dict[str, list[str]] = {}
    for base_type in hierarchy_index.keys():
        expanded_index[base_type] = get_all_descendants(base_type)

    logger.debug(f"Built type hierarchy index with {len(expanded_index)} base types")
    return expanded_index


def find_elements_by_type(
    type_qname: str,
    element_declarations: dict[str, ElementDeclaration]
) -> list[str]:
    """
    Find all elements that reference a specific type.

    Args:
        type_qname: Qualified name of the type to search for
        element_declarations: Dict mapping qualified names to ElementDeclaration objects

    Returns:
        List of element qnames that have the specified type
    """
    matching_elements = []

    for qname, elem_decl in element_declarations.items():
        if elem_decl.type_ref == type_qname:
            matching_elements.append(qname)

    return matching_elements


def find_person_types(
    type_definitions: dict[str, TypeDefinition],
    element_declarations: dict[str, ElementDeclaration],
    substitution_index: dict[str, list[str]],
    type_hierarchy_index: dict[str, list[str]]
) -> set[str]:
    """
    Find all element qnames that represent person entities.

    Discovery criteria:
    1. Elements in nc:Person substitution group
    2. Elements with types derived from nc:PersonType
    3. Elements with types derived from structures:ObjectType that contain person-related elements

    Args:
        type_definitions: Dict mapping type qnames to TypeDefinition objects
        element_declarations: Dict mapping element qnames to ElementDeclaration objects
        substitution_index: Mapping of substitution groups to elements
        type_hierarchy_index: Mapping of base types to derived types

    Returns:
        Set of element qnames representing person entities
    """
    person_types: set[str] = set()

    # 1. Find elements that substitute for nc:Person
    nc_person_substitutes = substitution_index.get("nc:Person", [])
    person_types.update(nc_person_substitutes)
    logger.debug(f"Found {len(nc_person_substitutes)} elements in nc:Person substitution group")

    # 2. Find types derived from nc:PersonType
    person_derived_types = type_hierarchy_index.get("nc:PersonType", [])
    logger.debug(f"Found {len(person_derived_types)} types derived from nc:PersonType: {person_derived_types[:10]}")

    # Find elements with these types
    for derived_type in person_derived_types:
        elements = find_elements_by_type(derived_type, element_declarations)
        if elements:
            logger.debug(f"Type {derived_type} has elements: {elements}")
        person_types.update(elements)

    # 3. Also include elements that directly have nc:PersonType
    direct_person_elements = find_elements_by_type("nc:PersonType", element_declarations)
    person_types.update(direct_person_elements)

    logger.info(f"Discovered {len(person_types)} person entity types from schema: {sorted(person_types)}")
    return person_types


def find_organization_types(
    type_definitions: dict[str, TypeDefinition],
    element_declarations: dict[str, ElementDeclaration],
    substitution_index: dict[str, list[str]],
    type_hierarchy_index: dict[str, list[str]]
) -> set[str]:
    """
    Find all element qnames that represent organization entities.

    Discovery criteria:
    1. Elements in nc:Organization substitution group
    2. Elements with types derived from nc:OrganizationType

    Args:
        type_definitions: Dict mapping type qnames to TypeDefinition objects
        element_declarations: Dict mapping element qnames to ElementDeclaration objects
        substitution_index: Mapping of substitution groups to elements
        type_hierarchy_index: Mapping of base types to derived types

    Returns:
        Set of element qnames representing organization entities
    """
    org_types: set[str] = set()

    # 1. Find elements that substitute for nc:Organization
    nc_org_substitutes = substitution_index.get("nc:Organization", [])
    org_types.update(nc_org_substitutes)
    logger.debug(f"Found {len(nc_org_substitutes)} elements in nc:Organization substitution group")

    # 2. Find types derived from nc:OrganizationType
    org_derived_types = type_hierarchy_index.get("nc:OrganizationType", [])
    logger.debug(f"Found {len(org_derived_types)} types derived from nc:OrganizationType")

    # Find elements with these types
    for derived_type in org_derived_types:
        elements = find_elements_by_type(derived_type, element_declarations)
        org_types.update(elements)

    # 3. Also include elements that directly have nc:OrganizationType
    direct_org_elements = find_elements_by_type("nc:OrganizationType", element_declarations)
    org_types.update(direct_org_elements)

    logger.info(f"Discovered {len(org_types)} organization entity types from schema")
    return org_types


def is_person_entity_schema_based(
    qname: str,
    person_types: set[str]
) -> bool:
    """
    Check if a qname represents a person entity using schema-based discovery.

    Args:
        qname: Qualified name to check (e.g., "j:CrashDriver")
        person_types: Set of person entity qnames discovered from schema

    Returns:
        True if the qname is a known person type from schema
    """
    return qname in person_types


def is_organization_entity_schema_based(
    qname: str,
    org_types: set[str]
) -> bool:
    """
    Check if a qname represents an organization entity using schema-based discovery.

    Args:
        qname: Qualified name to check (e.g., "j:Agency")
        org_types: Set of organization entity qnames discovered from schema

    Returns:
        True if the qname is a known organization type from schema
    """
    return qname in org_types


def get_entity_category_from_schema(
    qname: str,
    person_types: set[str],
    org_types: set[str]
) -> Optional[str]:
    """
    Determine entity category (person or organization) from schema-based discovery.

    Args:
        qname: Qualified name to categorize
        person_types: Set of person entity qnames from schema
        org_types: Set of organization entity qnames from schema

    Returns:
        "person", "organization", or None if not found in schema
    """
    if is_person_entity_schema_based(qname, person_types):
        return "person"
    elif is_organization_entity_schema_based(qname, org_types):
        return "organization"
    return None


def build_entity_discovery_indices(
    type_definitions: dict[str, TypeDefinition],
    element_declarations: dict[str, ElementDeclaration]
) -> dict:
    """
    Build all indices needed for entity discovery.

    This is a convenience function that builds all necessary indices
    and discovers person/organization types in one call.

    Args:
        type_definitions: Dict mapping type qnames to TypeDefinition objects
        element_declarations: Dict mapping element qnames to ElementDeclaration objects

    Returns:
        Dict with keys:
        - substitution_index: Mapping of substitution groups to elements
        - type_hierarchy_index: Mapping of base types to derived types
        - person_types: Set of person entity qnames
        - organization_types: Set of organization entity qnames
    """
    logger.info("Building entity discovery indices from XSD schemas")

    # Build indices
    substitution_index = build_substitution_index(element_declarations)
    type_hierarchy_index = build_type_hierarchy_index(type_definitions)

    # Discover entity types
    person_types = find_person_types(
        type_definitions,
        element_declarations,
        substitution_index,
        type_hierarchy_index
    )

    organization_types = find_organization_types(
        type_definitions,
        element_declarations,
        substitution_index,
        type_hierarchy_index
    )

    return {
        "substitution_index": substitution_index,
        "type_hierarchy_index": type_hierarchy_index,
        "person_types": person_types,
        "organization_types": organization_types
    }
