#!/usr/bin/env python3
"""XSD-based element tree builder for graph schema design.

This module parses XSD schema files directly to build a hierarchical tree
structure for the graph schema designer UI, providing more accurate
representation of the source schema structure.
"""

from dataclasses import dataclass
from typing import Optional
import re
import logging
import defusedxml.ElementTree as ET
from xml.etree.ElementTree import Element

# Note: Types moved here from element_tree.py to make this module self-contained
from dataclasses import dataclass, field
from enum import Enum

# Constants
ASSOCIATION_TYPE = "nc.AssociationType"
DEEP_NESTING_THRESHOLD = 3

class NodeType(str, Enum):
    """Type of node in the element tree."""
    OBJECT = "object"
    ASSOCIATION = "association"
    REFERENCE = "reference"

class WarningType(str, Enum):
    """Type of warning for best practice detection."""
    DEEP_NESTING = "deep_nesting"
    SPARSE_CONNECTIVITY = "sparse_connectivity"
    INSUFFICIENT_ENDPOINTS = "insufficient_endpoints"

class SuggestionType(str, Enum):
    """Type of suggestion for best practice guidance."""
    ASSOCIATION_CANDIDATE = "association_candidate"
    FLATTEN_WRAPPER = "flatten_wrapper"

@dataclass
class ElementTreeNode:
    """Node in the element tree hierarchy."""
    qname: str                              # Qualified name (e.g., "j:CrashDriver")
    label: str                              # Neo4j label (e.g., "j_CrashDriver")
    node_type: NodeType                     # object, association, or reference
    depth: int                              # Distance from root (0-indexed)
    property_count: int                     # Number of simple/scalar properties
    nested_object_count: int                # Number of nested complex objects
    parent_qname: Optional[str] = None      # Parent in hierarchy
    children: list['ElementTreeNode'] = field(default_factory=list)
    warnings: list[WarningType] = field(default_factory=list)
    suggestions: list[SuggestionType] = field(default_factory=list)
    selected: bool = True                   # Default selected (from auto-generated mapping)
    cardinality: Optional[str] = None       # Min..Max occurrence
    description: Optional[str] = None       # Element documentation
    namespace: Optional[str] = None         # Namespace prefix
    is_nested_association: bool = False     # True if nested under another object
    can_have_id: bool = False               # True if type extends structures:ObjectType (instances can have id/ref/uri)

# XSD namespace
XS_NS = "http://www.w3.org/2001/XMLSchema"
XS = f"{{{XS_NS}}}"

# Maximum tree depth to prevent infinite recursion (configurable)
MAX_TREE_DEPTH = 100

# NIEM structures namespace
STRUCTURES_NS = "https://docs.oasis-open.org/niemopen/ns/model/structures/6.0/"

logger = logging.getLogger(__name__)


@dataclass
class TypeDefinition:
    """Represents a complexType or simpleType definition."""
    name: str
    namespace: str
    is_simple: bool
    base_type: Optional[str]
    elements: list[dict]  # Element references in xs:sequence
    is_association: bool
    extends_object_type: bool = False  # Can have structures:id/ref/uri


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
    # Look for sequences in specific places (not recursively to avoid duplicates)
    elements = []
    sequence_paths = [
        f'./{XS}sequence',                                           # Direct child
        f'./{XS}complexContent/{XS}extension/{XS}sequence',        # Extension
        f'./{XS}complexContent/{XS}restriction/{XS}sequence',      # Restriction
        f'./{XS}choice',                                             # Direct choice
        f'./{XS}complexContent/{XS}extension/{XS}choice',          # Extension choice
        f'./{XS}complexContent/{XS}restriction/{XS}choice',        # Restriction choice
    ]

    # Track seen sequences by their id() to avoid processing the same sequence twice
    seen_sequences = set()
    # Track seen element names to avoid duplicates
    seen_elements = set()

    for path in sequence_paths:
        for seq in type_elem.findall(path):
            # Check if we've already processed this exact sequence object
            seq_id = id(seq)
            if seq_id in seen_sequences:
                continue

            seen_sequences.add(seq_id)

            for elem in seq.findall(f'./{XS}element'):
                elem_decl = _parse_element_declaration(elem, schema_ns_map)

                # Check for duplicates - use name only as key since same element can appear with different attributes
                elem_key = elem_decl.name
                if elem_key in seen_elements:
                    logger.debug(f"Skipping duplicate element '{elem_decl.name}' in type '{name}'")
                    continue

                seen_elements.add(elem_key)
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

            if not prefix:
                logger.warning(f"No prefix found for target namespace '{target_ns}' in {filename}")
                logger.info(f"Available namespace mappings: {list(schema_ns_map.items())[:5]}")
            else:
                logger.info(f"Found prefix '{prefix}' for namespace '{target_ns}' in {filename}")

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
                    logger.info(f"DEBUG: Indexed element declaration '{qname}' from {filename}")

        except ET.ParseError as e:
            print(f"Warning: Failed to parse {filename}: {e}")
            continue

    logger.info(f"DEBUG: Total element declarations indexed: {len(element_declarations)}")
    logger.info(f"DEBUG: Sample element declarations: {list(element_declarations.keys())[:20]}")
    if 'j:Charge' in element_declarations:
        logger.info("DEBUG: ✅ j:Charge IS in element_declarations")
    else:
        logger.info("DEBUG: ❌ j:Charge NOT in element_declarations")

    return type_definitions, element_declarations, namespace_prefixes


def _count_properties_and_relationships(
    type_def: TypeDefinition,
    type_definitions: dict[str, TypeDefinition],
    element_declarations: dict[str, ElementDeclaration]
) -> tuple[int, int]:
    """Count simple properties vs nested objects in a type.

    Returns:
        tuple[int, int]: (property_count, nested_object_count)
    """
    property_count = 0
    nested_object_count = 0

    logger.info(f"DEBUG: Counting for type {type_def.name}, has {len(type_def.elements)} elements")
    logger.info(f"DEBUG: Available type_definitions keys (first 10): {list(type_definitions.keys())[:10]}")

    for elem in type_def.elements:
        elem_type = elem.get('type')
        elem_name = elem.get('name')

        logger.info(f"DEBUG:   Element '{elem_name}' has type '{elem_type}'")

        # If no direct type, try to resolve via element declaration (handles refs)
        if not elem_type and elem_name:
            elem_decl = element_declarations.get(elem_name)
            if elem_decl:
                elem_type = elem_decl.type_ref
                logger.info(f"DEBUG:     -> Resolved type from element declaration: '{elem_type}'")

        if not elem_type:
            logger.info(f"DEBUG:     -> Skipping (no type)")
            continue

        # Check if it's a reference to another complex type
        if elem_type in type_definitions:
            nested_object_count += 1
            logger.info(f"DEBUG:     -> NESTED OBJECT (found in type_definitions)")
        else:
            # Assume simple/scalar if not found in type definitions
            # (could be xs:string, xs:int, etc.)
            property_count += 1
            logger.info(f"DEBUG:     -> PROPERTY (not found in type_definitions)")

    logger.info(f"DEBUG: Result: {property_count} properties, {nested_object_count} nested objects")
    return property_count, nested_object_count


def _build_tree_recursive(
    element_qname: str,
    depth: int,
    parent_qname: Optional[str],
    element_declarations: dict[str, ElementDeclaration],
    type_definitions: dict[str, TypeDefinition],
    max_depth: int = MAX_TREE_DEPTH,
    path_visited: Optional[set[str]] = None
) -> Optional[ElementTreeNode]:
    """Recursively build element tree from XSD structure.

    Args:
        element_qname: Qualified name of element to process
        depth: Current depth in tree
        parent_qname: Parent element qname
        element_declarations: Index of all element declarations
        type_definitions: Index of all type definitions
        max_depth: Maximum allowed depth (prevents infinite recursion)
        path_visited: Set of elements visited in current path (prevents cycles in same branch)

    Returns:
        ElementTreeNode or None if element not found or depth exceeded
    """
    # Initialize path_visited for root calls
    if path_visited is None:
        path_visited = set()

    # Safety check: prevent infinite recursion
    if depth > max_depth:
        logger.warning(f"Max depth {max_depth} exceeded for element '{element_qname}' - stopping recursion")
        return None

    # Check if this element is already in the current path (circular reference)
    if element_qname in path_visited:
        logger.debug(f"Circular reference detected: '{element_qname}' already in path at depth {depth}")
        return None
    # Find element declaration
    elem_decl = element_declarations.get(element_qname)
    if not elem_decl:
        # Element declaration not found - this shouldn't happen for well-formed schemas
        # Log it but return None to skip this branch
        logger.debug(f"Element declaration not found for '{element_qname}' at depth {depth}")
        return None


    # Add current element to path (prevents circular references in same branch)
    current_path = path_visited | {element_qname}

    # Find type definition
    type_def = None
    if elem_decl.type_ref:
        type_def = type_definitions.get(elem_decl.type_ref)

    if not type_def:
        # No type definition found - treat as scalar
        return None

    # Determine node type
    node_type = NodeType.ASSOCIATION if type_def.is_association else NodeType.OBJECT

    # Count properties vs nested objects
    property_count, nested_object_count = _count_properties_and_relationships(
        type_def, type_definitions, element_declarations
    )

    # Create node
    label = element_qname.replace(':', '_')
    node = ElementTreeNode(
        qname=element_qname,
        label=label,
        node_type=node_type,
        depth=depth,
        property_count=property_count,
        nested_object_count=nested_object_count,
        parent_qname=parent_qname,
        children=[],
        warnings=[],
        suggestions=[],
        selected=False,
        cardinality=f"{elem_decl.min_occurs}..{elem_decl.max_occurs}",
        description=elem_decl.documentation,
        namespace=element_qname.split(':')[0] if ':' in element_qname else None,
        is_nested_association=(node_type == NodeType.ASSOCIATION and parent_qname is not None)
    )

    # Recursively build children
    for elem_info in type_def.elements:
        child_name = elem_info['name']

        # Properly qualify child qname
        if ':' in child_name:
            # Already qualified (e.g., "j:Crash")
            child_qname = child_name
        else:
            # Local name - qualify using parent's namespace
            parent_prefix = element_qname.split(':')[0] if ':' in element_qname else ''
            child_qname = f"{parent_prefix}:{child_name}" if parent_prefix else child_name

        # Try to build child node recursively
        # Pass current_path to allow same element in different branches but prevent cycles
        child_node = _build_tree_recursive(
            child_qname,
            depth + 1,
            element_qname,
            element_declarations,
            type_definitions,
            max_depth,
            current_path  # Pass copy of path to this child
        )

        if child_node:
            # Check for duplicate children with same qname
            existing_qnames = [c.qname for c in node.children]
            if child_node.qname in existing_qnames:
                logger.debug(f"Duplicate child '{child_node.qname}' already exists under '{element_qname}'")
            else:
                node.children.append(child_node)
        else:
            # If we couldn't build the child node, log it but don't skip
            logger.debug(f"Could not build child node for '{child_qname}' (parent: {element_qname})")

    # Apply best practice detection
    # Deep nesting warning - DISABLED to avoid UI clutter
    # Deep nesting is common in NIEM schemas and not necessarily a problem
    # if depth > DEEP_NESTING_THRESHOLD:
    #     node.warnings.append(WarningType.DEEP_NESTING)

    if (node.node_type == NodeType.OBJECT and
        property_count <= 2 and
        nested_object_count == 0 and
        depth > 1):
        node.suggestions.append(SuggestionType.FLATTEN_WRAPPER)

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

    # Build hierarchy to identify which elements are children
    hierarchy = build_element_hierarchy(type_definitions, element_declarations)

    # Get primary file's target namespace
    primary_content = xsd_files[primary_filename]
    primary_root = ET.fromstring(primary_content)
    primary_target_ns = primary_root.attrib.get('targetNamespace', '')
    primary_prefix = namespace_prefixes.get(primary_target_ns)

    # Find TRUE root elements (only from primary namespace, not referenced as children)
    root_nodes = []

    for element_qname, elem_decl in element_declarations.items():
        # Only consider elements from the primary namespace
        if primary_prefix and not element_qname.startswith(f"{primary_prefix}:"):
            continue

        # Skip elements that are children of other elements
        if element_qname in hierarchy:
            continue

        # Build tree starting from this true root
        # Each root gets its own path_visited (allows same element in different roots)
        tree_node = _build_tree_recursive(
            element_qname,
            depth=0,
            parent_qname=None,
            element_declarations=element_declarations,
            type_definitions=type_definitions,
            max_depth=MAX_TREE_DEPTH,
            path_visited=set()  # Fresh path for each root
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


def flatten_tree_to_list(nodes: list[ElementTreeNode]) -> list[dict]:
    """Flatten tree structure to a flat list for API response.

    Args:
        nodes: List of root ElementTreeNode objects

    Returns:
        List of dictionaries representing nodes in flattened form
    """
    result = []

    def flatten_recursive(node: ElementTreeNode):
        result.append({
            "qname": node.qname,
            "label": node.label,
            "node_type": node.node_type.value,
            "depth": node.depth,
            "property_count": node.property_count,
            "nested_object_count": node.nested_object_count,
            "parent_qname": node.parent_qname,
            "warnings": [w.value for w in node.warnings],
            "suggestions": [s.value for s in node.suggestions],
            "selected": node.selected,
            "cardinality": node.cardinality,
            "description": node.description,
            "namespace": node.namespace,
            "is_nested_association": node.is_nested_association,
            "can_have_id": node.can_have_id,
        })

        for child in node.children:
            flatten_recursive(child)

    for root in nodes:
        flatten_recursive(root)

    return result
