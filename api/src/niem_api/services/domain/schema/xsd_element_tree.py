#!/usr/bin/env python3
"""XSD-based element tree builder for graph schema design.

This module parses XSD schema files directly to build a hierarchical tree
structure for the graph schema designer UI, providing more accurate
representation of the source schema structure.
"""

from dataclasses import dataclass
from typing import Optional
import re
import defusedxml.ElementTree as ET
from xml.etree.ElementTree import Element

from .element_tree import (
    ElementTreeNode,
    NodeType,
    WarningType,
    SuggestionType,
    DEEP_NESTING_THRESHOLD,
)

# XSD namespace
XS_NS = "http://www.w3.org/2001/XMLSchema"
XS = f"{{{XS_NS}}}"

# NIEM structures namespace
STRUCTURES_NS = "https://docs.oasis-open.org/niemopen/ns/model/structures/6.0/"


@dataclass
class TypeDefinition:
    """Represents a complexType or simpleType definition."""
    name: str
    namespace: str
    is_simple: bool
    base_type: Optional[str]
    elements: list[dict]  # Element references in xs:sequence
    is_association: bool


@dataclass
class ElementDeclaration:
    """Represents an element declaration."""
    name: str
    namespace: str
    type_name: Optional[str]
    type_ref: Optional[str]  # Qualified type reference
    min_occurs: str
    max_occurs: str
    documentation: Optional[str]


def _get_qname(element: Element, attr: str, namespaces: dict[str, str]) -> Optional[str]:
    """Extract qualified name from attribute value.

    Converts prefix:localName to qualified name using namespace map.
    """
    value = element.attrib.get(attr)
    if not value:
        return None

    if ':' in value:
        prefix, local = value.split(':', 1)
        namespace = namespaces.get(prefix)
        if namespace:
            return f"{prefix}:{local}"

    return value


def _extract_namespace_map_from_xml(xml_content: bytes) -> dict[str, str]:
    """Extract namespace prefix mappings from raw XML content.

    ElementTree doesn't preserve xmlns attributes, so we parse them from raw XML.
    """
    namespaces = {}

    # Decode bytes to string
    xml_str = xml_content.decode('utf-8')

    # Find all xmlns declarations using regex
    # Match xmlns:prefix="uri" or xmlns="uri"
    xmlns_pattern = r'xmlns(?::([a-zA-Z0-9_-]+))?="([^"]+)"'
    matches = re.findall(xmlns_pattern, xml_str)

    for prefix, uri in matches:
        if prefix:
            namespaces[prefix] = uri
        else:
            namespaces[''] = uri

    return namespaces


def _parse_element_declaration(elem: Element, schema_ns_map: dict[str, str]) -> ElementDeclaration:
    """Parse an xs:element declaration."""
    name = elem.attrib.get('name')
    ref = elem.attrib.get('ref')
    type_attr = elem.attrib.get('type')
    min_occurs = elem.attrib.get('minOccurs', '1')
    max_occurs = elem.attrib.get('maxOccurs', '1')

    # Extract documentation
    doc_elem = elem.find(f'./{XS}annotation/{XS}documentation')
    documentation = doc_elem.text.strip() if doc_elem is not None and doc_elem.text else None

    # Determine namespace
    namespace = ''
    if ref:
        # Reference to another element
        if ':' in ref:
            prefix = ref.split(':')[0]
            namespace = schema_ns_map.get(prefix, '')
            name = ref
    elif name:
        # Local declaration
        namespace = schema_ns_map.get('', '')

    return ElementDeclaration(
        name=name or ref or '',
        namespace=namespace,
        type_name=type_attr,
        type_ref=_get_qname(elem, 'type', schema_ns_map) if type_attr else None,
        min_occurs=min_occurs,
        max_occurs=max_occurs,
        documentation=documentation
    )


def _parse_complex_type(type_elem: Element, schema_ns_map: dict[str, str]) -> TypeDefinition:
    """Parse an xs:complexType definition."""
    name = type_elem.attrib.get('name', '')

    # Check for extension/restriction base
    base_type = None
    extension = type_elem.find(f'.//{XS}extension')
    restriction = type_elem.find(f'.//{XS}restriction')

    if extension is not None:
        base_type = _get_qname(extension, 'base', schema_ns_map)
    elif restriction is not None:
        base_type = _get_qname(restriction, 'base', schema_ns_map)

    # Check if this is an association type
    is_association = (
        'AssociationType' in name or
        (base_type and 'AssociationType' in base_type)
    )

    # Extract element children from xs:sequence or xs:choice
    elements = []
    for seq in type_elem.findall(f'.//{XS}sequence'):
        for elem in seq.findall(f'./{XS}element'):
            elem_decl = _parse_element_declaration(elem, schema_ns_map)
            elements.append({
                'name': elem_decl.name,
                'type': elem_decl.type_ref,
                'min_occurs': elem_decl.min_occurs,
                'max_occurs': elem_decl.max_occurs,
            })

    return TypeDefinition(
        name=name,
        namespace=schema_ns_map.get('', ''),
        is_simple=False,
        base_type=base_type,
        elements=elements,
        is_association=is_association
    )


def _build_indices(xsd_files: dict[str, bytes]) -> tuple[dict, dict, dict]:
    """Build indices of all types and elements across all XSD files.

    Returns:
        Tuple of (type_definitions, element_declarations, namespace_prefixes)
    """
    type_definitions = {}  # qname -> TypeDefinition
    element_declarations = {}  # qname -> ElementDeclaration
    namespace_prefixes = {}  # namespace_uri -> prefix

    for filename, content in xsd_files.items():
        try:
            root = ET.fromstring(content)

            # Skip if not a schema element
            if root.tag != f'{XS}schema':
                continue

            # Extract namespace mappings from raw XML content
            schema_ns_map = _extract_namespace_map_from_xml(content)
            target_ns = root.attrib.get('targetNamespace', '')

            # Get prefix for this target namespace
            prefix = None
            for p, ns in schema_ns_map.items():
                if ns == target_ns and p:
                    prefix = p
                    namespace_prefixes[target_ns] = p
                    break

            # Parse complexType definitions
            for type_elem in root.findall(f'./{XS}complexType'):
                type_def = _parse_complex_type(type_elem, schema_ns_map)
                if type_def.name and prefix:
                    qname = f"{prefix}:{type_def.name}"
                    type_definitions[qname] = type_def

            # Parse top-level element declarations
            for elem in root.findall(f'./{XS}element'):
                elem_decl = _parse_element_declaration(elem, schema_ns_map)
                if elem_decl.name and prefix:
                    qname = f"{prefix}:{elem_decl.name}" if ':' not in elem_decl.name else elem_decl.name
                    element_declarations[qname] = elem_decl

        except ET.ParseError as e:
            print(f"Warning: Failed to parse {filename}: {e}")
            continue

    return type_definitions, element_declarations, namespace_prefixes


def _count_properties_and_relationships(
    type_def: TypeDefinition,
    type_definitions: dict[str, TypeDefinition]
) -> tuple[int, int]:
    """Count scalar properties vs object relationships in a type."""
    property_count = 0
    relationship_count = 0

    for elem in type_def.elements:
        elem_type = elem.get('type')

        if not elem_type:
            continue

        # Check if it's a reference to another complex type
        if elem_type in type_definitions:
            relationship_count += 1
        else:
            # Assume scalar if not found in type definitions
            # (could be xs:string, xs:int, etc.)
            property_count += 1

    return property_count, relationship_count


def _build_tree_recursive(
    element_qname: str,
    depth: int,
    parent_qname: Optional[str],
    element_declarations: dict[str, ElementDeclaration],
    type_definitions: dict[str, TypeDefinition],
    visited: set[str]
) -> Optional[ElementTreeNode]:
    """Recursively build element tree from XSD structure.

    Args:
        element_qname: Qualified name of element to process
        depth: Current depth in tree
        parent_qname: Parent element qname
        element_declarations: Index of all element declarations
        type_definitions: Index of all type definitions
        visited: Set of visited qnames (prevent cycles)

    Returns:
        ElementTreeNode or None if element not found
    """
    # Prevent infinite recursion
    if element_qname in visited:
        return None

    visited.add(element_qname)

    # Find element declaration
    elem_decl = element_declarations.get(element_qname)
    if not elem_decl:
        return None

    # Find type definition
    type_def = None
    if elem_decl.type_ref:
        type_def = type_definitions.get(elem_decl.type_ref)

    if not type_def:
        # No type definition found - treat as scalar
        return None

    # Determine node type
    node_type = NodeType.ASSOCIATION if type_def.is_association else NodeType.OBJECT

    # Count properties and relationships
    property_count, relationship_count = _count_properties_and_relationships(
        type_def, type_definitions
    )

    # Create node
    label = element_qname.replace(':', '_')
    node = ElementTreeNode(
        qname=element_qname,
        label=label,
        node_type=node_type,
        depth=depth,
        property_count=property_count,
        relationship_count=relationship_count,
        parent_qname=parent_qname,
        children=[],
        warnings=[],
        suggestions=[],
        selected=True,
        cardinality=f"{elem_decl.min_occurs}..{elem_decl.max_occurs}",
        description=elem_decl.documentation,
        namespace=element_qname.split(':')[0] if ':' in element_qname else None,
        is_nested_association=(node_type == NodeType.ASSOCIATION and parent_qname is not None)
    )

    # Recursively build children
    for elem_info in type_def.elements:
        child_name = elem_info['name']
        child_qname = child_name if ':' in child_name else child_name

        child_node = _build_tree_recursive(
            child_qname,
            depth + 1,
            element_qname,
            element_declarations,
            type_definitions,
            visited.copy()  # Copy to allow same element in different branches
        )

        if child_node:
            node.children.append(child_node)

    # Apply best practice detection
    if depth > DEEP_NESTING_THRESHOLD:
        node.warnings.append(WarningType.DEEP_NESTING)

    if node.node_type == NodeType.ASSOCIATION and relationship_count < 2:
        node.warnings.append(WarningType.INSUFFICIENT_ENDPOINTS)

    if (node.node_type == NodeType.OBJECT and
        property_count <= 2 and
        relationship_count == 0 and
        depth > 1):
        node.suggestions.append(SuggestionType.FLATTEN_WRAPPER)

    if (node.node_type == NodeType.OBJECT and
        relationship_count >= 2 and
        'association' in element_qname.lower()):
        node.suggestions.append(SuggestionType.ASSOCIATION_CANDIDATE)

    return node


def build_element_tree_from_xsd(
    primary_filename: str,
    xsd_files: dict[str, bytes]
) -> list[ElementTreeNode]:
    """Build element tree from XSD schema files.

    Parses XSD files directly to create hierarchical tree structure with
    metadata for the graph schema designer UI.

    Args:
        primary_filename: Relative path to primary XSD file
        xsd_files: Dictionary mapping relative paths to XSD content

    Returns:
        List of root ElementTreeNode objects

    Raises:
        ET.ParseError: If XSD parsing fails
    """
    # Build indices from all XSD files
    type_definitions, element_declarations, namespace_prefixes = _build_indices(xsd_files)

    # Find root elements across all XSD files (not just primary)
    # This is needed because NIEM schemas often spread elements across multiple files
    root_nodes = []
    for element_qname in element_declarations.keys():
        # Build tree starting from this element
        tree_node = _build_tree_recursive(
            element_qname,
            depth=0,
            parent_qname=None,
            element_declarations=element_declarations,
            type_definitions=type_definitions,
            visited=set()
        )

        if tree_node:
            root_nodes.append(tree_node)

    return root_nodes


def classify_xsd_type(type_ref: str, type_definitions: dict[str, TypeDefinition]) -> str:
    """Classify XSD type into simple type category for Neo4j.

    Args:
        type_ref: Qualified type reference (e.g., "xs:string", "nc:TextType")
        type_definitions: Index of all type definitions

    Returns:
        Simple type category: "string", "integer", "date", "boolean", "decimal"
    """
    # Direct XSD simple types
    xsd_type_map = {
        'xs:string': 'string',
        'xs:normalizedString': 'string',
        'xs:token': 'string',
        'xs:int': 'integer',
        'xs:integer': 'integer',
        'xs:long': 'integer',
        'xs:short': 'integer',
        'xs:byte': 'integer',
        'xs:positiveInteger': 'integer',
        'xs:nonNegativeInteger': 'integer',
        'xs:decimal': 'decimal',
        'xs:float': 'decimal',
        'xs:double': 'decimal',
        'xs:boolean': 'boolean',
        'xs:date': 'date',
        'xs:dateTime': 'date',
        'xs:time': 'date',
        'xs:gYear': 'date',
        'xs:gYearMonth': 'date',
    }

    # Check if it's a direct XSD type
    if type_ref in xsd_type_map:
        return xsd_type_map[type_ref]

    # Check if it's a custom type with a restriction/extension base
    type_def = type_definitions.get(type_ref)
    if type_def and type_def.base_type:
        # Recursively check base type
        return classify_xsd_type(type_def.base_type, type_definitions)

    # Default to string if unknown
    return 'string'


def extract_scalar_properties_from_type(
    type_def: TypeDefinition,
    type_definitions: dict[str, TypeDefinition]
) -> list[dict]:
    """Extract scalar properties from a type definition.

    Args:
        type_def: Type definition to extract properties from
        type_definitions: Index of all type definitions

    Returns:
        List of scalar property dictionaries with name, type, cardinality
    """
    scalar_props = []

    for elem in type_def.elements:
        elem_name = elem.get('name')
        elem_type = elem.get('type')
        min_occurs = elem.get('min_occurs', '1')
        max_occurs = elem.get('max_occurs', '1')

        if not elem_name or not elem_type:
            continue

        # Check if this element's type is a scalar or complex type
        if elem_type in type_definitions:
            target_type_def = type_definitions[elem_type]
            # If it's a simple type or has no child elements, it's scalar
            if target_type_def.is_simple or len(target_type_def.elements) == 0:
                scalar_type = classify_xsd_type(elem_type, type_definitions)
                scalar_props.append({
                    'name': elem_name,
                    'type': scalar_type,
                    'min_occurs': min_occurs,
                    'max_occurs': max_occurs,
                    'cardinality': f"{min_occurs}..{max_occurs}"
                })
        else:
            # Assume scalar if not in type definitions (likely XSD built-in type)
            scalar_type = classify_xsd_type(elem_type, type_definitions)
            scalar_props.append({
                'name': elem_name,
                'type': scalar_type,
                'min_occurs': min_occurs,
                'max_occurs': max_occurs,
                'cardinality': f"{min_occurs}..{max_occurs}"
            })

    return scalar_props


def build_element_hierarchy(
    type_definitions: dict[str, TypeDefinition],
    element_declarations: dict[str, ElementDeclaration]
) -> dict[str, str]:
    """Build element hierarchy mapping from type definitions.

    Maps child element qname to parent element qname based on
    which types contain references to other elements.

    Args:
        type_definitions: Index of all type definitions
        element_declarations: Index of all element declarations

    Returns:
        Dictionary mapping child_qname → parent_qname
    """
    hierarchy = {}

    # For each element declaration, find its type and check children
    for parent_qname, parent_decl in element_declarations.items():
        if not parent_decl.type_ref:
            continue

        # Get the type definition for this element
        type_def = type_definitions.get(parent_decl.type_ref)
        if not type_def:
            continue

        # Check each child element in this type
        for child_elem in type_def.elements:
            child_name = child_elem.get('name')
            child_ref = child_elem.get('ref')

            # If it references another element, establish parent-child relationship
            if child_ref and child_ref in element_declarations:
                hierarchy[child_ref] = parent_qname
            elif child_name:
                # Construct child qname from parent namespace + child name
                parent_ns = parent_qname.split(':')[0] if ':' in parent_qname else ''
                child_qname = f"{parent_ns}:{child_name}" if parent_ns else child_name
                if child_qname in element_declarations:
                    hierarchy[child_qname] = parent_qname

    return hierarchy
