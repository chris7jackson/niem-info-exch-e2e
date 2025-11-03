#!/usr/bin/env python3
"""Element tree builder for graph schema design.

This module parses CMF XML to build a hierarchical tree structure with metadata
for the graph schema designer UI. It identifies objects, associations, and
references, calculates depth and counts, and detects best practice issues.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
import defusedxml.ElementTree as ET
from xml.etree.ElementTree import Element

# NIEM CMF and structures namespaces
CMF_NS = "https://docs.oasis-open.org/niemopen/ns/specification/cmf/1.0/"
STRUCT_NS = "https://docs.oasis-open.org/niemopen/ns/model/structures/6.0/"
NS = {"cmf": CMF_NS, "structures": STRUCT_NS}

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
    property_count: int                     # Number of scalar properties
    relationship_count: int                 # Number of object references
    parent_qname: Optional[str] = None      # Parent in hierarchy
    children: list['ElementTreeNode'] = field(default_factory=list)
    warnings: list[WarningType] = field(default_factory=list)
    suggestions: list[SuggestionType] = field(default_factory=list)
    selected: bool = True                   # Default selected (from auto-generated mapping)
    cardinality: Optional[str] = None       # Min..Max occurrence
    description: Optional[str] = None       # Element documentation
    namespace: Optional[str] = None         # Namespace prefix
    is_nested_association: bool = False     # True if nested under another object


def _text_of(element: Element, tag: str) -> Optional[str]:
    """Extract text content from a child element."""
    child = element.find(f"./cmf:{tag}", NS)
    return child.text.strip() if child is not None and child.text else None


def _ref_of(element: Element, tag: str) -> Optional[str]:
    """Extract structures:ref attribute from a child element."""
    child = element.find(f"./cmf:{tag}", NS)
    if child is not None:
        return child.attrib.get(f"{{{STRUCT_NS}}}ref")
    return None


def _to_qname(dotted: str) -> str:
    """Convert 'prefix.LocalName' to 'prefix:LocalName' (CMF uses dotted ids)."""
    return dotted.replace(".", ":") if dotted else dotted


def _to_label(qn: str) -> str:
    """Convert a QName to a safe Neo4j label (prefix_LocalName)."""
    return qn.replace(":", "_").replace(".", "_")


def _is_association_type(class_element: Element) -> bool:
    """Check if a class is an association type."""
    subclass_ref = _ref_of(class_element, "SubClassOf")
    if not subclass_ref:
        return False

    # Check if subclass is AssociationType or contains "Association"
    return (subclass_ref == ASSOCIATION_TYPE or
            "Association" in subclass_ref)


def _parse_property_associations(class_element: Element) -> tuple[int, int]:
    """Parse child property associations and count scalars vs objects.

    Returns:
        Tuple of (scalar_count, object_count)
    """
    scalar_count = 0
    object_count = 0

    for cpa in class_element.findall("./cmf:ChildPropertyAssociation", NS):
        obj_prop_ref = _ref_of(cpa, "ObjectProperty")
        data_prop_ref = _ref_of(cpa, "DataProperty")

        if obj_prop_ref:
            object_count += 1
        elif data_prop_ref:
            scalar_count += 1

    return (scalar_count, object_count)


def _detect_warnings(node: ElementTreeNode) -> list[WarningType]:
    """Detect best practice warnings for a node."""
    warnings = []

    # Deep nesting warning
    if node.depth > DEEP_NESTING_THRESHOLD:
        warnings.append(WarningType.DEEP_NESTING)

    # Insufficient association endpoints
    if node.node_type == NodeType.ASSOCIATION and node.relationship_count < 2:
        warnings.append(WarningType.INSUFFICIENT_ENDPOINTS)

    return warnings


def _detect_suggestions(node: ElementTreeNode) -> list[SuggestionType]:
    """Detect best practice suggestions for a node."""
    suggestions = []

    # Association candidate detection
    if (node.node_type == NodeType.OBJECT and
        node.relationship_count >= 2 and
        "association" in node.qname.lower()):
        suggestions.append(SuggestionType.ASSOCIATION_CANDIDATE)

    # Flatten wrapper suggestion (only 1-2 scalar properties, no relationships)
    if (node.node_type == NodeType.OBJECT and
        node.property_count <= 2 and
        node.relationship_count == 0 and
        node.depth > 1):
        suggestions.append(SuggestionType.FLATTEN_WRAPPER)

    return suggestions


def _build_node_from_class(
    class_element: Element,
    depth: int,
    parent_qname: Optional[str] = None,
    class_id_to_element: dict[str, Element] = None
) -> ElementTreeNode:
    """Build an ElementTreeNode from a CMF Class element."""
    class_id = class_element.attrib.get(f"{{{STRUCT_NS}}}id") or class_element.attrib.get("id")
    namespace_ref = _ref_of(class_element, "Namespace")

    qname = _to_qname(class_id) if class_id else ""
    label = _to_label(qname)

    # Determine node type
    is_association = _is_association_type(class_element)
    node_type = NodeType.ASSOCIATION if is_association else NodeType.OBJECT

    # Count properties and relationships
    scalar_count, object_count = _parse_property_associations(class_element)

    # Determine if nested association (if parent is not an association)
    is_nested = False
    if is_association and parent_qname and class_id_to_element:
        parent_element = class_id_to_element.get(parent_qname.replace(":", "."))
        if parent_element and not _is_association_type(parent_element):
            is_nested = True

    # Create node
    node = ElementTreeNode(
        qname=qname,
        label=label,
        node_type=node_type,
        depth=depth,
        property_count=scalar_count,
        relationship_count=object_count,
        parent_qname=parent_qname,
        namespace=namespace_ref,
        is_nested_association=is_nested
    )

    # Apply best practice detection
    node.warnings = _detect_warnings(node)
    node.suggestions = _detect_suggestions(node)

    return node


def _build_tree_recursive(
    class_element: Element,
    depth: int,
    element_to_class: dict[str, str],
    class_id_to_element: dict[str, Element],
    parent_qname: Optional[str] = None,
    visited: set[str] = None
) -> ElementTreeNode:
    """Recursively build the element tree from CMF classes.

    Args:
        class_element: Current class element
        depth: Current depth in tree
        element_to_class: Mapping from element IDs to class IDs
        class_id_to_element: Mapping from class IDs to class elements
        parent_qname: Parent node's qname
        visited: Set of visited class IDs (prevent cycles)

    Returns:
        ElementTreeNode with children populated
    """
    if visited is None:
        visited = set()

    class_id = class_element.attrib.get(f"{{{STRUCT_NS}}}id") or class_element.attrib.get("id")

    # Prevent infinite recursion
    if class_id in visited:
        return _build_node_from_class(class_element, depth, parent_qname, class_id_to_element)

    visited.add(class_id)

    # Build current node
    node = _build_node_from_class(class_element, depth, parent_qname, class_id_to_element)

    # Build children from object properties
    for cpa in class_element.findall("./cmf:ChildPropertyAssociation", NS):
        obj_prop_ref = _ref_of(cpa, "ObjectProperty")

        if obj_prop_ref:
            # Resolve to target class
            target_class_id = element_to_class.get(obj_prop_ref)
            if target_class_id and target_class_id in class_id_to_element:
                target_element = class_id_to_element[target_class_id]

                # Recursively build child tree
                child_node = _build_tree_recursive(
                    target_element,
                    depth + 1,
                    element_to_class,
                    class_id_to_element,
                    node.qname,
                    visited.copy()  # Copy to allow same class in different branches
                )
                node.children.append(child_node)

    return node


def build_element_tree(cmf_xml: str) -> list[ElementTreeNode]:
    """Build element tree from CMF XML.

    Parses the CMF XML and builds a hierarchical tree structure with metadata
    for each element. Detects best practice issues and provides suggestions.

    Args:
        cmf_xml: CMF XML content as string

    Returns:
        List of root ElementTreeNode objects (typically one per major entity type)

    Raises:
        ET.ParseError: If CMF XML is malformed
    """
    root = ET.fromstring(cmf_xml)

    # Build indices
    element_to_class = {}
    class_id_to_element = {}

    # Map ObjectProperty IDs to Class IDs
    for element in root.findall(".//cmf:ObjectProperty", NS):
        class_ref_element = element.find("./cmf:Class", NS)
        if class_ref_element is not None:
            class_ref = class_ref_element.attrib.get(f"{{{STRUCT_NS}}}ref")
            element_id = element.attrib.get(f"{{{STRUCT_NS}}}id")
            if class_ref and element_id:
                element_to_class[element_id] = class_ref

    # Map Class IDs to Class elements
    for class_element in root.findall(".//cmf:Class", NS):
        class_id = class_element.attrib.get(f"{{{STRUCT_NS}}}id") or class_element.attrib.get("id")
        if class_id:
            class_id_to_element[class_id] = class_element

    # Find root classes (top-level entities, typically not subclassed by others)
    # For simplicity, we'll consider all non-association classes as potential roots
    root_nodes = []

    for class_id, class_element in class_id_to_element.items():
        # Simple heuristic: Include all classes as potential roots
        # The UI will handle hierarchy display and filtering

        # Build tree for each major entity
        tree_node = _build_tree_recursive(
            class_element,
            depth=0,
            element_to_class=element_to_class,
            class_id_to_element=class_id_to_element
        )

        root_nodes.append(tree_node)

    return root_nodes


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
            "relationship_count": node.relationship_count,
            "parent_qname": node.parent_qname,
            "warnings": [w.value for w in node.warnings],
            "suggestions": [s.value for s in node.suggestions],
            "selected": node.selected,
            "cardinality": node.cardinality,
            "description": node.description,
            "namespace": node.namespace,
            "is_nested_association": node.is_nested_association,
            "children": [child.qname for child in node.children]  # Just qnames for children
        })

        for child in node.children:
            flatten_recursive(child)

    for node in nodes:
        flatten_recursive(node)

    return result
