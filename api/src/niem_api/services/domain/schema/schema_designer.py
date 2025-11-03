#!/usr/bin/env python3
"""Schema designer service for applying user selections to graph schema.

This module applies user node selections to generate customized mapping.yaml
files with flattening logic for unselected nodes.
"""

from typing import Any, Optional
import defusedxml.ElementTree as ET
from xml.etree.ElementTree import Element

from .mapping import (
    build_prefix_map,
    parse_classes,
    build_element_to_class,
    build_dataproperty_index,
    build_datatype_index,
    to_qname,
    to_label,
    to_rel_type,
    text_of,
    ref_of,
    NS,
    STRUCT_NS,
)


def _find_nearest_selected_ancestor(
    qname: str,
    selections: dict[str, bool],
    class_hierarchy: dict[str, Optional[str]]
) -> Optional[str]:
    """Find the nearest selected ancestor for an unselected node.

    Args:
        qname: QName of the current node
        selections: Dictionary mapping qnames to selection state
        class_hierarchy: Dictionary mapping qnames to parent qnames

    Returns:
        QName of nearest selected ancestor, or None if no ancestor is selected
    """
    current = qname
    visited = set()

    while current and current not in visited:
        visited.add(current)

        if selections.get(current, False):
            return current

        parent = class_hierarchy.get(current)
        if not parent:
            break
        current = parent

    return None


def _build_class_hierarchy(root: Element, element_to_class: dict[str, str]) -> dict[str, Optional[str]]:
    """Build a hierarchy map of class relationships from CMF.

    Args:
        root: CMF XML root element
        element_to_class: Mapping from element IDs to class IDs

    Returns:
        Dictionary mapping child qnames to parent qnames
    """
    hierarchy = {}

    # Build hierarchy from ObjectProperty child relationships
    for class_element in root.findall(".//cmf:Class", NS):
        class_id = class_element.attrib.get(f"{{{STRUCT_NS}}}id") or class_element.attrib.get("id")
        if not class_id:
            continue

        parent_qname = to_qname(class_id)

        # Find child properties
        for cpa in class_element.findall("./cmf:ChildPropertyAssociation", NS):
            obj_prop_ref = ref_of(cpa, "ObjectProperty")

            if obj_prop_ref:
                target_class_id = element_to_class.get(obj_prop_ref)
                if target_class_id:
                    child_qname = to_qname(target_class_id)
                    hierarchy[child_qname] = parent_qname

    return hierarchy


def _flatten_properties_into_parent(
    unselected_class: dict[str, Any],
    parent_qname: str,
    dataprop_index: dict[str, dict[str, Any]],
    datatype_index: dict[str, dict[str, Any]],
    path_prefix: str = ""
) -> list[dict[str, str]]:
    """Flatten unselected class properties into parent node properties.

    Args:
        unselected_class: Class information for unselected node
        parent_qname: QName of parent to flatten into
        dataprop_index: Index of data properties
        datatype_index: Index of datatypes
        path_prefix: Prefix for property paths

    Returns:
        List of scalar property dictionaries to add to parent
    """
    flattened_props = []

    for prop in unselected_class.get("props", []):
        data_prop_ref = prop.get("dataProperty")

        if data_prop_ref:
            # This is a scalar property - flatten it
            prop_info = dataprop_index.get(data_prop_ref, {})
            prop_qname = to_qname(data_prop_ref)

            # Build property path with prefix
            prop_path = f"{path_prefix}/{prop_qname}" if path_prefix else prop_qname

            # Convert to Neo4j property name
            neo4j_property = prop_path.replace(":", "_").replace("/", "_")

            datatype_ref = prop_info.get("datatype")
            dtype_info = datatype_index.get(datatype_ref, {}) if datatype_ref else {}
            simple_type = _classify_datatype(dtype_info)

            flattened_props.append({
                "path": prop_path,
                "neo4j_property": neo4j_property,
                "type": simple_type,
                "cardinality": f"{prop['min'] or '0'}..{prop['max'] or '*'}"
            })

    return flattened_props


def _classify_datatype(dtype_info: dict[str, Any]) -> str:
    """Classify datatype into simple type category.

    Args:
        dtype_info: Datatype information dictionary

    Returns:
        Simple type category (string, integer, boolean, date, etc.)
    """
    if not dtype_info:
        return "string"

    # Check restriction base or datatype name
    base = dtype_info.get("restriction_base", "")
    name = dtype_info.get("name", "")

    if any(x in base.lower() or x in name.lower() for x in ["int", "long", "short", "byte"]):
        return "integer"
    elif any(x in base.lower() or x in name.lower() for x in ["decimal", "double", "float"]):
        return "decimal"
    elif any(x in base.lower() or x in name.lower() for x in ["bool"]):
        return "boolean"
    elif any(x in base.lower() or x in name.lower() for x in ["date", "time"]):
        return "date"
    else:
        return "string"


def _is_association_type(class_element: Element) -> bool:
    """Check if a class is an association type."""
    subclass_ref = ref_of(class_element, "SubClassOf")
    if not subclass_ref:
        return False

    return "Association" in subclass_ref


def _is_nested_association(
    class_id: str,
    class_hierarchy: dict[str, Optional[str]],
    class_index: dict[str, dict[str, Any]],
    root: Element
) -> bool:
    """Check if an association is nested under a non-association parent.

    Args:
        class_id: Class ID to check
        class_hierarchy: Class hierarchy mapping
        class_index: Index of all classes
        root: CMF XML root element

    Returns:
        True if association is nested under a non-association class
    """
    qname = to_qname(class_id)
    parent_qname = class_hierarchy.get(qname)

    if not parent_qname:
        return False  # Top-level

    # Check if parent is an association
    parent_class_id = parent_qname.replace(":", ".")
    parent_class = class_index.get(parent_class_id)

    if not parent_class:
        return False

    # Find parent element in CMF
    for class_element in root.findall(".//cmf:Class", NS):
        elem_class_id = class_element.attrib.get(f"{{{STRUCT_NS}}}id") or class_element.attrib.get("id")
        if elem_class_id == parent_class_id:
            return not _is_association_type(class_element)

    return False


def apply_schema_design(
    cmf_content: str,
    selections: dict[str, bool]
) -> dict[str, Any]:
    """Apply user schema design selections to generate custom mapping.

    This function takes the CMF content and user node selections, then applies
    the flattening strategy documented in ADR-002 to generate a customized
    mapping.yaml.

    Flattening Rules:
    - Selected nodes → Create Neo4j nodes
    - Unselected nodes → Flatten properties into nearest selected ancestor
    - References (source selected, target not) → Flatten target into source
    - Associations (nested) → Flatten into parent
    - Associations (top-level, 2+ endpoints) → Create n-ary relationship
    - Associations (top-level, <2 endpoints) → Flatten into remaining endpoint

    Args:
        cmf_content: CMF XML content as string
        selections: Dictionary mapping qnames to selection state (True = create node)

    Returns:
        Dictionary containing the customized mapping structure

    Raises:
        ET.ParseError: If CMF XML is malformed
    """
    root = ET.fromstring(cmf_content)

    # Build base indices (same as generate_mapping_from_cmf_content)
    prefixes_all = build_prefix_map(root)
    classes = parse_classes(root)
    class_index = {c["id"]: c for c in classes if c["id"]}
    element_to_class = build_element_to_class(root)
    class_to_element = {v: k for k, v in element_to_class.items()}

    dataprop_index = build_dataproperty_index(root)
    datatype_index = build_datatype_index(root)

    # Build class hierarchy for ancestor lookup
    class_hierarchy = _build_class_hierarchy(root, element_to_class)

    # Partition classes into associations and objects
    association_ids = set()
    for class_element in root.findall(".//cmf:Class", NS):
        if _is_association_type(class_element):
            class_id = class_element.attrib.get(f"{{{STRUCT_NS}}}id") or class_element.attrib.get("id")
            if class_id:
                association_ids.add(class_id)

    # Process selected objects
    selected_objects = []
    selected_associations = []

    for class_id, class_info in class_index.items():
        qname = to_qname(class_id)

        if not selections.get(qname, False):
            continue  # Skip unselected

        # Check if association
        if class_id in association_ids:
            # Check if nested
            is_nested = _is_nested_association(class_id, class_hierarchy, class_index, root)

            if not is_nested:
                # Top-level association - include if it has 2+ endpoints
                endpoint_count = sum(1 for p in class_info.get("props", []) if p.get("objectProperty"))

                if endpoint_count >= 2:
                    # Get element QName
                    element_qname = class_to_element.get(class_id)
                    selected_associations.append({
                        "class_id": class_id,
                        "element_qname": element_qname,
                        "info": class_info
                    })
            # Nested associations are not included as separate nodes
        else:
            # Regular object
            element_qname = class_to_element.get(class_id)
            selected_objects.append({
                "class_id": class_id,
                "element_qname": element_qname,
                "info": class_info
            })

    # Build objects mapping with flattening
    objects_mapping = []
    for obj in selected_objects:
        obj_qname = to_qname(obj["element_qname"] or obj["class_id"])
        obj_label = to_label(obj_qname)
        class_info = obj["info"]

        # Start with direct scalar properties
        scalar_props = []

        for prop in class_info.get("props", []):
            data_prop_ref = prop.get("dataProperty")
            obj_prop_ref = prop.get("objectProperty")

            if data_prop_ref:
                # Direct scalar property
                prop_info = dataprop_index.get(data_prop_ref, {})
                prop_qname = to_qname(data_prop_ref)

                datatype_ref = prop_info.get("datatype")
                dtype_info = datatype_index.get(datatype_ref, {}) if datatype_ref else {}
                simple_type = _classify_datatype(dtype_info)

                scalar_props.append({
                    "path": prop_qname,
                    "neo4j_property": to_label(prop_qname),
                    "type": simple_type,
                    "cardinality": f"{prop['min'] or '0'}..{prop['max'] or '*'}"
                })

            elif obj_prop_ref:
                # Object property - check if target is selected
                target_class_id = element_to_class.get(obj_prop_ref)
                target_qname = to_qname(target_class_id) if target_class_id else None

                if target_qname and not selections.get(target_qname, False):
                    # Target not selected - flatten target properties into this object
                    target_class = class_index.get(target_class_id)
                    if target_class:
                        flattened = _flatten_properties_into_parent(
                            target_class,
                            obj_qname,
                            dataprop_index,
                            datatype_index,
                            path_prefix=to_qname(obj_prop_ref)
                        )
                        scalar_props.extend(flattened)

        objects_mapping.append({
            "qname": obj_qname,
            "label": obj_label,
            "carries_structures_id": True,
            "scalar_props": scalar_props
        })

    # Build associations mapping
    associations_mapping = []
    for assoc in selected_associations:
        assoc_qname = to_qname(assoc["element_qname"] or assoc["class_id"])
        class_info = assoc["info"]

        endpoints = []
        for idx, prop in enumerate(class_info.get("props", [])):
            obj_prop_ref = prop.get("objectProperty")

            if obj_prop_ref:
                target_class_id = element_to_class.get(obj_prop_ref)
                target_qname = to_qname(target_class_id) if target_class_id else to_qname(obj_prop_ref)

                # Only include endpoint if target is selected
                if target_class_id and selections.get(to_qname(target_class_id), False):
                    endpoints.append({
                        "role_qname": to_qname(obj_prop_ref),
                        "maps_to_label": to_label(target_qname),
                        "direction": "source" if idx == 0 else "target",
                        "via": "structures:ref",
                        "cardinality": f"{prop['min'] or '0'}..{prop['max'] or '*'}"
                    })

        # Only include association if it still has 2+ endpoints after filtering
        if len(endpoints) >= 2:
            associations_mapping.append({
                "qname": assoc_qname,
                "rel_type": to_rel_type(assoc_qname),
                "endpoints": endpoints,
                "rel_props": []
            })

    # Build references mapping (only between selected nodes)
    references_mapping = []
    for obj in selected_objects:
        owner_qn = to_qname(obj["element_qname"] or obj["class_id"])
        class_info = obj["info"]

        for prop in class_info.get("props", []):
            obj_prop = prop.get("objectProperty")
            if not obj_prop:
                continue

            target_class_id = element_to_class.get(obj_prop)
            target_qname = to_qname(target_class_id) if target_class_id else None

            # Only create reference if target is selected AND not an association
            if (target_qname and
                selections.get(target_qname, False) and
                target_class_id not in association_ids):

                references_mapping.append({
                    "owner_object": owner_qn,
                    "field_qname": to_qname(obj_prop),
                    "target_label": to_label(target_qname),
                    "rel_type": to_rel_type(obj_prop),
                    "via": "structures:ref",
                    "cardinality": f"{prop['min'] or '0'}..{prop['max'] or '*'}"
                })

    # Collect used prefixes
    used_prefixes = set()
    for obj in objects_mapping:
        prefix = obj["qname"].split(":")[0] if ":" in obj["qname"] else ""
        if prefix:
            used_prefixes.add(prefix)

    for assoc in associations_mapping:
        prefix = assoc["qname"].split(":")[0] if ":" in assoc["qname"] else ""
        if prefix:
            used_prefixes.add(prefix)

    used_ns_map = {k: v for k, v in prefixes_all.items() if k in used_prefixes}

    # Assemble final mapping
    return {
        "namespaces": used_ns_map,
        "objects": objects_mapping,
        "associations": associations_mapping,
        "references": references_mapping,
        "augmentations": [],
        "polymorphism": {
            "strategy": "extraLabel",
            "store_actual_type_property": "xsiType"
        }
    }
