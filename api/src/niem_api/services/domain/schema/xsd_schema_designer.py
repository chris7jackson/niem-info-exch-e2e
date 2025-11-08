#!/usr/bin/env python3
"""XSD-based schema designer for applying user selections to graph schema.

This module applies user node selections to generate customized mapping.yaml
files directly from XSD, preserving all data with the same resolution as CMF.
"""

from typing import Any, Optional

from .xsd_element_tree import (
    build_element_hierarchy,
    build_augmentation_index,
    classify_xsd_type,
    extract_scalar_properties_from_type,
    _build_indices,
    TypeDefinition,
    ElementDeclaration,
    is_wrapper_type,
    is_entity_type,
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

    # Build augmentation index - O(a)
    augmentation_index = build_augmentation_index(type_definitions, element_declarations)

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

    # Auto-select association endpoints for selected associations
    # This ensures associations can become edges even if endpoints weren't explicitly selected
    # Only auto-select entity endpoints, not wrapper properties (they're always flattened)
    for assoc_qname in list(selected_set):  # Use list() to avoid modifying set during iteration
        if assoc_qname not in association_elements:
            continue

        _, type_def = association_elements[assoc_qname]
        for child_elem in type_def.elements:
            child_ref = child_elem.get('ref')
            if child_ref and child_ref in object_elements:
                # Check if this is an entity endpoint (not a wrapper property)
                child_elem_decl, child_type_def = object_elements[child_ref]
                if not is_wrapper_type(child_elem_decl.type_ref, child_type_def):
                    # Auto-add entity endpoint to selected set
                    selected_set.add(child_ref)

    # Build objects mapping - preserves all data
    objects_mapping = []
    for elem_qname in selected_set:
        if elem_qname not in object_elements:
            continue

        elem_decl, type_def = object_elements[elem_qname]

        # ====================================================================
        # AUGMENTATION EXCLUSION (CRITICAL!)
        # ====================================================================
        # Skip augmentations - they should NEVER become nodes in the graph.
        # Augmentations are schema-level constructs for extending types.
        # Their properties are automatically included in the base type's properties.
        #
        # Example: exch:ChargeAugmentation extends j:ChargeType
        # Result: When user selects j:Charge, they get augmentation properties automatically
        # But exch:ChargeAugmentation itself never appears in:
        # - objects mapping (skipped here)
        # - associations mapping (skipped below)
        # - references mapping (skipped below)
        # - graph nodes (transparent during ingestion)
        if type_def.is_augmentation_type:
            continue

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

        # ====================================================================
        # AUTOMATIC AUGMENTATION INCLUSION
        # ====================================================================
        # When a base type is selected, automatically include all augmentation properties.
        # This ensures augmentation data is preserved even though augmentation elements
        # don't appear as nodes.
        #
        # Example: User selects j:Charge
        # → Automatically includes j_ArrestTrackingNumberID from exch:ChargeAugmentation
        #
        # Properties are added to base type with:
        # - Flat naming: j:PersonAdultIndicator → j_PersonAdultIndicator
        # - Path metadata: j:PersonAugmentation/j:PersonAdultIndicator
        # - Augmentation flag: is_augmentation = true
        type_ref = elem_decl.type_ref
        if type_ref and type_ref in augmentation_index:
            for aug_def in augmentation_index[type_ref]:
                aug_elem_qname = aug_def['augmentation_element_qname']
                for aug_prop in aug_def['properties']:
                    # Use flat naming: j:PersonAdultIndicator -> j_PersonAdultIndicator
                    prop_qname = aug_prop['qname']
                    neo4j_property = prop_qname.replace(':', '_')
                    scalar_type = classify_xsd_type(aug_prop['type_ref'], type_definitions)

                    scalar_props.append({
                        "path": f"{aug_elem_qname}/{prop_qname}",
                        "neo4j_property": neo4j_property,
                        "type": scalar_type,
                        "cardinality": f"{aug_prop['min_occurs']}..{aug_prop['max_occurs']}",
                        "is_augmentation": True
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

            # Only include selected entity endpoints (not wrapper properties or augmentations)
            if target_qname in selected_set:
                # Check if this is an entity endpoint (not a wrapper property or augmentation)
                if target_qname in object_elements:
                    target_elem_decl, target_type_def = object_elements[target_qname]
                    if is_wrapper_type(target_elem_decl.type_ref, target_type_def):
                        # Skip wrapper properties - they're always flattened
                        continue
                    if target_type_def.is_augmentation_type:
                        # Skip augmentations - they're flattened into base types
                        continue

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

        # Skip augmentations - they should never own references
        if type_def.is_augmentation_type:
            continue

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

            # Create reference only if target is selected AND not an association or augmentation
            if (target_qname in selected_set and
                target_qname not in association_elements):

                # Skip if target is an augmentation
                if target_qname in object_elements:
                    target_elem_decl, target_type_def = object_elements[target_qname]
                    if target_type_def.is_augmentation_type:
                        continue

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

    # Build augmentations mapping
    augmentations_mapping = []
    for base_type_qname, aug_list in augmentation_index.items():
        for aug_def in aug_list:
            augmentations_mapping.append({
                'base_type_qname': base_type_qname,
                'augmentation_element_qname': aug_def['augmentation_element_qname'],
                'augmentation_type_qname': aug_def['augmentation_type_qname'],
                'properties': [
                    {
                        'qname': prop['qname'],
                        'type_ref': prop['type_ref'],
                        'cardinality': f"{prop['min_occurs']}..{prop['max_occurs']}"
                    }
                    for prop in aug_def['properties']
                ]
            })

    # Assemble final mapping (matches CMF lines 437-447)
    return {
        "namespaces": namespace_map,
        "objects": objects_mapping,
        "associations": associations_mapping,
        "references": references_mapping,
        "augmentations": augmentations_mapping,
        "polymorphism": {
            "strategy": "extraLabel",
            "store_actual_type_property": "xsiType"
        }
    }
