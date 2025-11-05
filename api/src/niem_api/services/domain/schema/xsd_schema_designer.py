#!/usr/bin/env python3
"""XSD-based schema designer for applying user selections to graph schema.

This module applies user node selections to generate customized mapping.yaml
files directly from XSD, preserving all data with the same resolution as CMF.
"""

from typing import Any, Optional

from .xsd_element_tree import (
    build_element_hierarchy,
    classify_xsd_type,
    extract_scalar_properties_from_type,
    _build_indices,
    TypeDefinition,
    ElementDeclaration,
)


def _find_nearest_selected_ancestor(
    qname: str,
    selected_set: set[str],
    hierarchy: dict[str, str],
    ancestor_cache: dict[str, Optional[str]]
) -> Optional[str]:
    """Find the nearest selected ancestor for an unselected element.

    Time: O(d) where d = depth, amortized O(1) with caching.

    Args:
        qname: QName of the current element
        selected_set: Set of selected qnames for O(1) lookup
        hierarchy: Dictionary mapping child qnames to parent qnames
        ancestor_cache: Cache of previously computed ancestors

    Returns:
        QName of nearest selected ancestor, or None if no ancestor is selected
    """
    # Check cache first
    if qname in ancestor_cache:
        return ancestor_cache[qname]

    current = qname
    visited = set()
    path = []

    while current and current not in visited:
        # Check cache at each step
        if current in ancestor_cache:
            result = ancestor_cache[current]
            # Cache for entire path
            for elem in path:
                ancestor_cache[elem] = result
            return result

        visited.add(current)
        path.append(current)

        # Check if selected
        if current in selected_set:
            for elem in path:
                ancestor_cache[elem] = current
            return current

        current = hierarchy.get(current)

    # No ancestor found
    for elem in path:
        ancestor_cache[elem] = None
    return None


def _flatten_properties_into_parent(
    unselected_type_ref: str,
    type_definitions: dict[str, TypeDefinition],
    path_prefix: str = ""
) -> list[dict[str, str]]:
    """Flatten unselected element's scalar properties into parent.

    Matches CMF version behavior exactly - only flattens direct scalar properties.
    Time: O(p) where p = scalar properties in type.

    Args:
        unselected_type_ref: Type reference of unselected element
        type_definitions: Index of type definitions
        path_prefix: Prefix for property paths

    Returns:
        List of scalar property dictionaries to add to parent
    """
    flattened_props = []

    type_def = type_definitions.get(unselected_type_ref)
    if not type_def:
        return flattened_props

    # Extract only scalar properties (matches CMF behavior)
    scalar_props = extract_scalar_properties_from_type(type_def, type_definitions)

    for prop in scalar_props:
        prop_name = prop['name']
        prop_type = prop['type']
        cardinality = prop['cardinality']

        # Build property path with prefix (matches CMF: path_prefix/prop_qname)
        # Assuming prop_name includes namespace prefix (e.g., "nc:PersonGivenName")
        prop_path = f"{path_prefix}/{prop_name}" if path_prefix else prop_name

        # Convert to Neo4j property name (replace : and / with _)
        neo4j_property = prop_path.replace(":", "_").replace("/", "_")

        flattened_props.append({
            "path": prop_path,
            "neo4j_property": neo4j_property,
            "type": prop_type,
            "cardinality": cardinality
        })

    return flattened_props


def apply_schema_design_from_xsd(
    xsd_files: dict[str, bytes],
    primary_filename: str,
    selections: dict[str, bool]
) -> dict[str, Any]:
    """Apply user schema design selections to generate custom mapping from XSD.

    Preserves all data with same resolution as CMF-based version.
    Optimized for efficiency: O(n + e*d) time, O(n + c) space.

    Args:
        xsd_files: Dictionary mapping filenames to XSD content
        primary_filename: Name of primary XSD file
        selections: Dictionary mapping qnames to selection state

    Returns:
        Dictionary containing the customized mapping structure
    """
    # Parse XSD and build indices - O(n)
    type_definitions, element_declarations, namespace_prefixes = _build_indices(xsd_files)

    # Build element hierarchy - O(e)
    element_hierarchy = build_element_hierarchy(type_definitions, element_declarations)

    # Create selected set for O(1) lookups
    selected_set = {qname for qname, selected in selections.items() if selected}

    # Ancestor cache for O(1) amortized lookups
    ancestor_cache: dict[str, Optional[str]] = {}

    # Build namespace map
    namespace_map = {prefix: uri for uri, prefix in namespace_prefixes.items()}

    # Partition elements - O(e)
    association_elements = {}
    object_elements = {}

    for elem_qname, elem_decl in element_declarations.items():
        if not elem_decl.type_ref:
            continue

        type_def = type_definitions.get(elem_decl.type_ref)
        if not type_def:
            continue

        if type_def.is_association:
            association_elements[elem_qname] = (elem_decl, type_def)
        else:
            object_elements[elem_qname] = (elem_decl, type_def)

    # Build objects mapping - preserves all data
    objects_mapping = []
    for elem_qname in selected_set:
        if elem_qname not in object_elements:
            continue

        elem_decl, type_def = object_elements[elem_qname]
        label = elem_qname.replace(':', '_')

        # Start with direct scalar properties
        direct_scalars = extract_scalar_properties_from_type(type_def, type_definitions)
        scalar_props = []

        for prop in direct_scalars:
            prop_path = prop['name']  # Direct property, no prefix
            neo4j_property = label + "_" + prop['name'].replace(':', '_')

            scalar_props.append({
                "path": prop_path,
                "neo4j_property": neo4j_property,
                "type": prop['type'],
                "cardinality": prop['cardinality']
            })

        # Check object properties for flattening (matches CMF logic at lines 336-352)
        for child_elem in type_def.elements:
            child_name = child_elem.get('name')
            child_ref = child_elem.get('ref')
            child_type = child_elem.get('type')

            # Determine child qname
            if child_ref:
                child_qname = child_ref
            elif child_name:
                ns_prefix = elem_qname.split(':')[0] if ':' in elem_qname else ''
                child_qname = f"{ns_prefix}:{child_name}" if ns_prefix else child_name
            else:
                continue

            # Check if child_type is a complex object type (not scalar)
            if not child_type or child_type not in type_definitions:
                continue

            child_type_def = type_definitions[child_type]

            # Skip if it's a simple type or has no elements (already handled as scalar)
            if child_type_def.is_simple or len(child_type_def.elements) == 0:
                continue

            # Check if target is NOT selected - if so, flatten its properties
            if child_qname not in selected_set:
                # Flatten target properties into this object (matches CMF lines 341-352)
                flattened = _flatten_properties_into_parent(
                    child_type,
                    type_definitions,
                    path_prefix=child_qname  # Use child qname as prefix
                )
                scalar_props.extend(flattened)

        objects_mapping.append({
            "qname": elem_qname,
            "label": label,
            "carries_structures_id": True,
            "scalar_props": scalar_props
        })

    # Build associations mapping
    associations_mapping = []
    for elem_qname in selected_set:
        if elem_qname not in association_elements:
            continue

        elem_decl, type_def = association_elements[elem_qname]
        label = elem_qname.replace(':', '_')
        rel_type = label.upper()

        endpoints = []
        for idx, child_elem in enumerate(type_def.elements):
            child_name = child_elem.get('name')
            child_ref = child_elem.get('ref')

            if child_ref:
                target_qname = child_ref
            elif child_name:
                ns_prefix = elem_qname.split(':')[0] if ':' in elem_qname else ''
                target_qname = f"{ns_prefix}:{child_name}" if ns_prefix else child_name
            else:
                continue

            # Only include selected endpoints (matches CMF line 376)
            if target_qname in selected_set:
                target_type = child_elem.get('type')
                # Get actual target qname from type if available
                if target_type and target_type in type_definitions:
                    target_label = target_qname.replace(':', '_')
                else:
                    target_label = target_qname.replace(':', '_')

                endpoints.append({
                    "role_qname": target_qname,
                    "maps_to_label": target_label,
                    "direction": "source" if idx == 0 else "target",
                    "via": "structures:ref",
                    "cardinality": f"{child_elem.get('min_occurs', '0')}..{child_elem.get('max_occurs', '*')}"
                })

        # Only include associations with 2+ endpoints (matches CMF line 386)
        if len(endpoints) >= 2:
            associations_mapping.append({
                "qname": elem_qname,
                "rel_type": rel_type,
                "endpoints": endpoints,
                "rel_props": []
            })

    # Build references mapping (matches CMF lines 394-420)
    references_mapping = []
    for elem_qname in selected_set:
        if elem_qname not in object_elements:
            continue

        elem_decl, type_def = object_elements[elem_qname]

        for child_elem in type_def.elements:
            child_ref = child_elem.get('ref')
            child_name = child_elem.get('name')
            child_type = child_elem.get('type')

            if child_ref:
                target_qname = child_ref
                field_qname = child_ref
            elif child_name:
                ns_prefix = elem_qname.split(':')[0] if ':' in elem_qname else ''
                target_qname = f"{ns_prefix}:{child_name}" if ns_prefix else child_name
                field_qname = target_qname
            else:
                continue

            # Skip if not a complex type
            if not child_type or child_type not in type_definitions:
                continue

            child_type_def = type_definitions[child_type]
            if child_type_def.is_simple or len(child_type_def.elements) == 0:
                continue

            # Create reference only if target is selected AND not an association (matches CMF lines 409-411)
            if (target_qname in selected_set and
                target_qname not in association_elements):

                target_label = target_qname.replace(':', '_')
                rel_type = field_qname.replace(':', '_').replace('/', '_').upper()

                references_mapping.append({
                    "owner_object": elem_qname,
                    "field_qname": field_qname,
                    "target_label": target_label,
                    "rel_type": rel_type,
                    "via": "structures:ref",
                    "cardinality": f"{child_elem.get('min_occurs', '0')}..{child_elem.get('max_occurs', '*')}"
                })

    # Assemble final mapping (matches CMF lines 437-447)
    return {
        "namespaces": namespace_map,
        "objects": objects_mapping,
        "associations": associations_mapping,
        "references": references_mapping,
        "augmentations": [],
        "polymorphism": {
            "strategy": "extraLabel",
            "store_actual_type_property": "xsiType"
        }
    }
