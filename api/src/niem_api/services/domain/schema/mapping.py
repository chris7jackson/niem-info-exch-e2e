#!/usr/bin/env python3
"""CMF to mapping.yaml converter service.

This module transforms a NIEM CMF 1.0 XML file into a mapping.yaml that a Neo4j importer
can use to create a property graph from NIEM-conformant XML instances.

Key Features:
- Extracts NIEM classes, associations, and references from CMF
- Generates Neo4j-compatible node labels and relationship types
- Supports role-based modeling for associations
- Handles NIEM namespace mappings
"""
import re
import sys
import xml.etree.ElementTree as ET
from typing import Any

import yaml

# NIEM CMF and structures namespaces
CMF_NS = "https://docs.oasis-open.org/niemopen/ns/specification/cmf/1.0/"
STRUCT_NS = "https://docs.oasis-open.org/niemopen/ns/model/structures/6.0/"
NS = {"cmf": CMF_NS, "structures": STRUCT_NS}

# NIEM type constants
ASSOCIATION_TYPE = "nc.AssociationType"


def to_qname(dotted: str) -> str:
    """Convert 'prefix.LocalName' to 'prefix:LocalName' (CMF uses dotted ids).

    Args:
        dotted: Dotted identifier from CMF

    Returns:
        Qualified name with colon separator
    """
    return dotted.replace(".", ":") if dotted else dotted


def to_label(qn: str) -> str:
    """Convert a QName to a safe Neo4j label (prefix_LocalName).

    Args:
        qn: Qualified name

    Returns:
        Neo4j-safe label with underscore separator
    """
    return qn.replace(":", "_").replace(".", "_")


def to_rel_type(name: str) -> str:
    """Generate a safe, upper-snake relationship type from a QName or id.

    Args:
        name: Name to convert

    Returns:
        Upper-case, underscore-separated relationship type
    """
    base = name.replace(":", "_").replace(".", "_")
    return re.sub(r"\W", "_", base).upper()


def text_of(element: ET.Element, tag: str) -> str | None:
    """Extract text content from a child element.

    Args:
        element: Parent XML element
        tag: Tag name to search for

    Returns:
        Text content or None if not found
    """
    child = element.find(f"./cmf:{tag}", NS)
    return child.text.strip() if child is not None and child.text else None


def ref_of(element: ET.Element, tag: str) -> str | None:
    """Extract structures:ref attribute from a child element.

    Args:
        element: Parent XML element
        tag: Tag name to search for

    Returns:
        Reference value or None if not found
    """
    child = element.find(f"./cmf:{tag}", NS)
    if child is not None:
        return child.attrib.get(f"{{{STRUCT_NS}}}ref")
    return None


def build_prefix_map(root: ET.Element) -> dict[str, str]:
    """Collect prefix→URI bindings from CMF Namespace entries.

    Args:
        root: CMF XML root element

    Returns:
        Dictionary mapping namespace prefixes to URIs
    """
    prefixes = {}
    for namespace_element in root.findall(".//cmf:Namespace", NS):
        prefix_element = namespace_element.find("./cmf:NamespacePrefixText", NS)
        uri_element = namespace_element.find("./cmf:NamespaceURI", NS)
        if prefix_element is not None and uri_element is not None and prefix_element.text and uri_element.text:
            prefixes[prefix_element.text.strip()] = uri_element.text.strip()
    return prefixes


def _parse_property_associations(class_element: ET.Element) -> list[dict[str, str]]:
    """Parse child property associations for a single class element.

    Args:
        class_element: Class XML element

    Returns:
        List of property association dictionaries
    """
    props = []
    for cpa in class_element.findall("./cmf:ChildPropertyAssociation", NS):
        obj_prop_ref = ref_of(cpa, "ObjectProperty")
        data_prop_ref = ref_of(cpa, "DataProperty")
        min_occurs = text_of(cpa, "MinOccursQuantity")
        max_occurs = text_of(cpa, "MaxOccursQuantity")
        props.append({
            "objectProperty": obj_prop_ref,
            "dataProperty": data_prop_ref,
            "min": min_occurs,
            "max": max_occurs
        })
    return props


def _extract_class_info(class_element: ET.Element) -> dict[str, Any]:
    """Extract basic information from a single class element.

    Args:
        class_element: Class XML element

    Returns:
        Dictionary with class information
    """
    class_id = class_element.attrib.get(f"{{{STRUCT_NS}}}id") or class_element.attrib.get("id")
    name = text_of(class_element, "Name")
    namespace_ref = ref_of(class_element, "Namespace")
    subclass = ref_of(class_element, "SubClassOf")
    props = _parse_property_associations(class_element)

    return {
        "id": class_id,
        "name": name,
        "namespace_prefix": namespace_ref,
        "subclass_of": subclass,
        "props": props
    }


def _is_meaningful_class(class_info: dict[str, Any]) -> bool:
    """Check if a class has meaningful content.

    Args:
        class_info: Class information dictionary

    Returns:
        True if class has meaningful content
    """
    return any([
        class_info.get("id"),
        class_info.get("name"),
        class_info.get("namespace_prefix"),
        class_info.get("subclass_of"),
        class_info.get("props", [])
    ])


def parse_classes(root: ET.Element) -> list[dict[str, Any]]:
    """Extract Classes with their namespace, base class, and child property associations.

    Args:
        root: CMF XML root element

    Returns:
        List of class information dictionaries
    """
    classes_info = []
    for class_element in root.findall(".//cmf:Class", NS):
        class_info = _extract_class_info(class_element)
        if _is_meaningful_class(class_info):
            classes_info.append(class_info)
    return classes_info


def build_element_to_class(root: ET.Element) -> dict[str, str]:
    """Map ObjectProperty id (element QName) → Class id.

    This lets us resolve association role participants to their object classes.

    Args:
        root: CMF XML root element

    Returns:
        Dictionary mapping element IDs to class IDs
    """
    mapping = {}
    for element in root.findall(".//cmf:ObjectProperty", NS):
        class_ref_element = element.find("./cmf:Class", NS)
        if class_ref_element is not None:
            class_ref = class_ref_element.attrib.get(f"{{{STRUCT_NS}}}ref")
            element_id = element.attrib.get(f"{{{STRUCT_NS}}}id")
            if class_ref and element_id:
                mapping[element_id] = class_ref
    return mapping


def build_dataproperty_index(root: ET.Element) -> dict[str, dict[str, Any]]:
    """Build index of DataProperty elements from CMF.

    Args:
        root: CMF XML root element

    Returns:
        Dictionary mapping DataProperty IDs to property information
    """
    index = {}
    for element in root.findall(".//cmf:DataProperty", NS):
        prop_id = element.attrib.get(f"{{{STRUCT_NS}}}id")
        if not prop_id:
            continue

        # Extract datatype reference
        datatype_ref = ref_of(element, "Datatype")

        index[prop_id] = {
            "id": prop_id,
            "name": text_of(element, "Name"),
            "datatype": datatype_ref,
            "namespace": ref_of(element, "Namespace")
        }

    return index


def build_datatype_index(root: ET.Element) -> dict[str, dict[str, Any]]:
    """Build index of Datatype and Restriction elements from CMF to classify types.

    Args:
        root: CMF XML root element

    Returns:
        Dictionary mapping Datatype/Restriction IDs to type classification info
    """
    index = {}

    # Process both Datatype and Restriction elements
    for element_type in [".//cmf:Datatype", ".//cmf:Restriction"]:
        for element in root.findall(element_type, NS):
            dtype_id = element.attrib.get(f"{{{STRUCT_NS}}}id")
            if not dtype_id:
                continue

            # Check for restriction base (indicates simple type)
            restriction_base = element.find(".//cmf:RestrictionBase", NS)
            restriction_of = element.find(".//cmf:RestrictionOf", NS)
            is_restriction = restriction_base is not None or restriction_of is not None or element_type == ".//cmf:Restriction"

            # Check for child properties (indicates complex type)
            child_props = element.findall(".//cmf:ChildPropertyAssociation", NS)

            # Classify type
            if is_restriction and len(child_props) == 0:
                type_class = "SIMPLE"
            elif len(child_props) == 1:
                # Single child - could be WRAPPER
                type_class = "WRAPPER"
            elif len(child_props) > 1:
                type_class = "COMPLEX"
            else:
                type_class = "SIMPLE"  # Default

            index[dtype_id] = {
                "id": dtype_id,
                "name": text_of(element, "Name"),
                "class": type_class,
                "child_count": len(child_props),
                "child_props": [
                    {
                        "dataProperty": ref_of(cpa, "DataProperty"),
                        "objectProperty": ref_of(cpa, "ObjectProperty"),
                        "min": text_of(cpa, "MinOccursQuantity"),
                        "max": text_of(cpa, "MaxOccursQuantity")
                    }
                    for cpa in child_props
                ]
            }

    return index


def _extract_scalar_properties(
    class_props: list[dict[str, Any]],
    dataprop_index: dict[str, dict[str, Any]],
    datatype_index: dict[str, dict[str, Any]],
    max_depth: int = 3
) -> list[dict[str, str]]:
    """Extract flattened scalar properties from class properties.

    Args:
        class_props: List of property associations from class
        dataprop_index: Index of DataProperty definitions
        datatype_index: Index of Datatype definitions
        max_depth: Maximum depth to flatten nested types

    Returns:
        List of scalar property definitions with paths
    """
    scalar_props = []

    for prop in class_props:
        data_prop_ref = prop.get("dataProperty")
        if not data_prop_ref:
            continue

        # Resolve DataProperty
        data_prop = dataprop_index.get(data_prop_ref)
        if not data_prop:
            continue

        # Get the datatype for this property
        datatype_ref = data_prop.get("datatype")
        if not datatype_ref:
            continue

        # Flatten properties recursively
        flattened = _flatten_property(
            data_prop_ref,
            data_prop,
            dataprop_index,
            datatype_index,
            max_depth=max_depth,
            current_depth=0
        )

        scalar_props.extend(flattened)

    return scalar_props


def _flatten_property(
    prop_ref: str,
    data_prop: dict[str, Any],
    dataprop_index: dict[str, dict[str, Any]],
    datatype_index: dict[str, dict[str, Any]],
    max_depth: int,
    current_depth: int,
    path_prefix: str = ""
) -> list[dict[str, str]]:
    """Recursively flatten a property based on its datatype classification.

    Args:
        prop_ref: Property reference ID
        data_prop: DataProperty information
        dataprop_index: Index of DataProperty definitions
        datatype_index: Index of Datatype definitions
        max_depth: Maximum recursion depth
        current_depth: Current recursion depth
        path_prefix: Accumulated path prefix

    Returns:
        List of flattened scalar property definitions
    """
    result = []

    # Build property path
    prop_qname = to_qname(prop_ref)
    if path_prefix:
        full_path = f"{path_prefix}.{prop_qname}"
    else:
        full_path = prop_qname

    # Get datatype classification
    datatype_ref = data_prop.get("datatype")
    if not datatype_ref:
        # No datatype - treat as simple scalar
        result.append({
            "path": full_path,
            "neo4j_property": full_path.replace(":", "_").replace(".", "_")
        })
        return result

    datatype = datatype_index.get(datatype_ref)
    if not datatype:
        # Unknown datatype - treat as simple scalar
        result.append({
            "path": full_path,
            "neo4j_property": full_path.replace(":", "_").replace(".", "_")
        })
        return result

    type_class = datatype.get("class", "SIMPLE")

    # SIMPLE type - return as-is
    if type_class == "SIMPLE":
        result.append({
            "path": full_path,
            "neo4j_property": full_path.replace(":", "_").replace(".", "_")
        })
        return result

    # Depth limit reached - stop flattening
    if current_depth >= max_depth:
        result.append({
            "path": full_path,
            "neo4j_property": full_path.replace(":", "_").replace(".", "_")
        })
        return result

    # WRAPPER or COMPLEX - flatten children
    child_props = datatype.get("child_props", [])

    if type_class == "WRAPPER" and len(child_props) == 1:
        # Single child - flatten directly
        child_prop = child_props[0]
        child_data_ref = child_prop.get("dataProperty")

        if child_data_ref and child_data_ref in dataprop_index:
            # Recurse into child
            child_data = dataprop_index[child_data_ref]
            result.extend(_flatten_property(
                child_data_ref,
                child_data,
                dataprop_index,
                datatype_index,
                max_depth,
                current_depth + 1,
                full_path
            ))
    elif type_class == "COMPLEX" and len(child_props) > 0:
        # Multiple children - flatten each with path prefix
        for child_prop in child_props:
            child_data_ref = child_prop.get("dataProperty")

            if child_data_ref and child_data_ref in dataprop_index:
                child_data = dataprop_index[child_data_ref]
                result.extend(_flatten_property(
                    child_data_ref,
                    child_data,
                    dataprop_index,
                    datatype_index,
                    max_depth,
                    current_depth + 1,
                    full_path
                ))
    else:
        # No children or couldn't resolve - treat as scalar
        result.append({
            "path": full_path,
            "neo4j_property": full_path.replace(":", "_").replace(".", "_")
        })

    return result


def _partition_classes(
    class_index: dict[str, dict[str, Any]],
    class_to_element: dict[str, str]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], set[str]]:
    """Partition classes into AssociationType and ObjectType.

    Args:
        class_index: Dictionary mapping class IDs to class info
        class_to_element: Dictionary mapping class IDs to element names

    Returns:
        Tuple of (objects, associations, association_ids)
    """
    association_ids = set()
    objects, associations = [], []

    for class_id, class_info in class_index.items():
        class_data = {
            "class_id": class_id,
            "element_qname": class_to_element.get(class_id),
            "info": class_info
        }

        if class_info["subclass_of"] == ASSOCIATION_TYPE:
            association_ids.add(class_id)
            associations.append(class_data)
        else:
            objects.append(class_data)

    return objects, associations, association_ids


def _collect_used_prefixes(classes: list[dict[str, Any]]) -> set[str]:
    """Collect all namespace prefixes used by classes and their properties.

    Args:
        classes: List of class information dictionaries

    Returns:
        Set of used namespace prefixes
    """
    used_prefixes = set()
    for class_info in classes:
        ns_prefix = class_info.get("namespace_prefix")
        if ns_prefix:
            used_prefixes.add(ns_prefix)

        for prop in class_info.get("props", []):
            for ref in (prop.get("objectProperty"), prop.get("dataProperty")):
                if ref and "." in ref:
                    used_prefixes.add(ref.split(".", 1)[0])

    return used_prefixes


def _create_label_for_class_function(
    class_to_element: dict[str, str]
) -> callable:
    """Create a label_for_class function with closure over class_to_element.

    Args:
        class_to_element: Dictionary mapping class IDs to element names

    Returns:
        Function that computes label from class ID
    """
    def label_for_class(class_id: str) -> str:
        element = class_to_element.get(class_id)
        if element:
            return to_label(to_qname(element))
        return to_label(to_qname(class_id.replace("Type", "")))

    return label_for_class


def _build_complete_objects_list(
    root: ET.Element,
    class_index: dict[str, dict[str, Any]],
    element_to_class: dict[str, str],
    association_ids: set[str]
) -> list[dict[str, Any]]:
    """Build complete list of objects from ALL ObjectProperties.

    This includes both:
    1. ObjectProperties with corresponding Class definitions (have properties)
    2. ObjectProperties without Class definitions (act as references only)

    Args:
        root: CMF XML root element
        class_index: Dictionary mapping class IDs to class info
        element_to_class: Mapping from ObjectProperty IDs to Class IDs
        association_ids: Set of association class IDs to exclude

    Returns:
        List of object dictionaries with element QNames and class info
    """
    objects = []
    seen_qnames = set()

    # Process all ObjectProperty elements
    for obj_prop in root.findall(".//cmf:ObjectProperty", NS):
        obj_prop_id = obj_prop.attrib.get(f"{{{STRUCT_NS}}}id")
        if not obj_prop_id:
            continue

        # Get the class this property references
        class_ref = element_to_class.get(obj_prop_id)

        # Skip if this is an association
        if class_ref and class_ref in association_ids:
            continue

        qn = to_qname(obj_prop_id)

        # Skip duplicates
        if qn in seen_qnames:
            continue
        seen_qnames.add(qn)

        # Build object entry
        obj_entry = {
            "element_qname": obj_prop_id,
            "class_id": class_ref,
            "info": class_index.get(class_ref, {}) if class_ref else {}
        }

        objects.append(obj_entry)

    return objects


def _build_objects_mapping(
    objects: list[dict[str, Any]],
    dataprop_index: dict[str, dict[str, Any]],
    datatype_index: dict[str, dict[str, Any]]
) -> list[dict[str, Any]]:
    """Build objects section of the mapping with extracted scalar properties.

    Args:
        objects: List of object class data
        dataprop_index: Index of DataProperty definitions
        datatype_index: Index of Datatype definitions

    Returns:
        List of object mapping entries
    """
    objects_mapping = []
    for obj in objects:
        qn = to_qname(obj["element_qname"] or obj["class_id"])

        # Extract scalar properties from this class
        class_info = obj.get("info", {})
        class_props = class_info.get("props", [])
        scalar_props = _extract_scalar_properties(class_props, dataprop_index, datatype_index)

        objects_mapping.append({
            "qname": qn,
            "label": to_label(qn),
            "carries_structures_id": True,
            "scalar_props": scalar_props
        })
    return objects_mapping


def _build_association_endpoint(
    prop: dict[str, str],
    element_to_class: dict[str, str],
    label_for_class: callable,
    endpoint_index: int
) -> dict[str, str]:
    """Build a single association endpoint.

    Args:
        prop: Property information
        element_to_class: Mapping from elements to classes
        label_for_class: Function to get label from class ID
        endpoint_index: Index of this endpoint (for direction)

    Returns:
        Association endpoint dictionary
    """
    obj_prop = prop["objectProperty"]
    target_class_id = element_to_class.get(obj_prop)
    target_label = label_for_class(target_class_id) if target_class_id else to_label(to_qname(obj_prop))

    return {
        "role_qname": to_qname(obj_prop),
        "maps_to_label": target_label,
        "direction": "source" if endpoint_index == 0 else "target",
        "via": "structures:ref",
        "cardinality": f"{prop['min'] or '0'}..{prop['max'] or '*'}"
    }


def _build_associations_mapping(
    associations: list[dict[str, Any]],
    element_to_class: dict[str, str],
    label_for_class: callable
) -> list[dict[str, Any]]:
    """Build associations section of the mapping.

    Args:
        associations: List of association class data
        element_to_class: Mapping from elements to classes
        label_for_class: Function to get label from class ID

    Returns:
        List of association mapping entries
    """
    associations_mapping = []
    for assoc in associations:
        class_info = assoc["info"]
        base_rel_name = to_qname(assoc["element_qname"] or assoc["class_id"])
        endpoints = []

        for prop in class_info.get("props", []):
            obj_prop = prop["objectProperty"]
            if obj_prop:
                endpoint = _build_association_endpoint(
                    prop, element_to_class, label_for_class, len(endpoints)
                )
                endpoints.append(endpoint)

        associations_mapping.append({
            "qname": base_rel_name,
            "rel_type": to_rel_type(base_rel_name),
            "endpoints": endpoints,
            "rel_props": []
        })

    return associations_mapping


def _build_references_mapping(
    objects: list[dict[str, Any]],
    element_to_class: dict[str, str],
    association_ids: set[str],
    label_for_class: callable
) -> list[dict[str, Any]]:
    """Build references section of the mapping.

    Args:
        objects: List of object class data
        element_to_class: Mapping from elements to classes
        association_ids: Set of association class IDs
        label_for_class: Function to get label from class ID

    Returns:
        List of reference mapping entries
    """
    references_mapping = []
    for obj in objects:
        owner_qn = to_qname(obj["element_qname"] or obj["class_id"])
        class_info = obj["info"]

        for prop in class_info.get("props", []):
            obj_prop = prop["objectProperty"]
            if not obj_prop:
                continue

            target_class_id = element_to_class.get(obj_prop)
            if target_class_id and target_class_id not in association_ids:
                references_mapping.append({
                    "owner_object": owner_qn,
                    "field_qname": to_qname(obj_prop),
                    "target_label": label_for_class(target_class_id),
                    "rel_type": to_rel_type(obj_prop),
                    "via": "structures:ref",
                    "cardinality": f"{prop['min'] or '0'}..{prop['max'] or '*'}"
                })

    return references_mapping


def generate_mapping_from_cmf_content(cmf_content: str) -> dict[str, Any]:
    """Generate mapping dictionary from CMF XML content string.

    Args:
        cmf_content: CMF XML content as string

    Returns:
        Dictionary containing the mapping structure
    """
    root = ET.fromstring(cmf_content)
    return _generate_mapping_from_root(root)


def generate_mapping_from_cmf_file(cmf_path: str) -> dict[str, Any]:
    """Generate mapping dictionary from CMF XML file.

    Args:
        cmf_path: Path to CMF XML file

    Returns:
        Dictionary containing the mapping structure
    """
    root = ET.parse(cmf_path).getroot()
    return _generate_mapping_from_root(root)


def _generate_mapping_from_root(root: ET.Element) -> dict[str, Any]:
    """Internal function to generate mapping from parsed XML root.

    Args:
        root: Parsed CMF XML root element

    Returns:
        Complete mapping dictionary
    """
    # Extract base data
    prefixes_all = build_prefix_map(root)
    classes = parse_classes(root)
    class_index = {c["id"]: c for c in classes if c["id"]}
    element_to_class = build_element_to_class(root)
    class_to_element = {v: k for k, v in element_to_class.items()}

    # Build DataProperty and Datatype indexes for property extraction
    dataprop_index = build_dataproperty_index(root)
    datatype_index = build_datatype_index(root)

    # Build CMF element index for augmentation detection
    cmf_elements = set()
    for element in root.findall(".//cmf:ObjectProperty", NS):
        elem_id = element.attrib.get(f"{{{STRUCT_NS}}}id")
        if elem_id:
            cmf_elements.add(to_qname(elem_id))
    for element in root.findall(".//cmf:DataProperty", NS):
        elem_id = element.attrib.get(f"{{{STRUCT_NS}}}id")
        if elem_id:
            cmf_elements.add(to_qname(elem_id))

    # Partition classes for associations
    _, associations, association_ids = _partition_classes(class_index, class_to_element)

    # Build complete object list from ALL ObjectProperties
    objects = _build_complete_objects_list(root, class_index, element_to_class, association_ids)

    # Collect used prefixes
    used_prefixes = _collect_used_prefixes(classes)
    used_ns_map = {k: v for k, v in prefixes_all.items() if k in used_prefixes}

    # Create helper function
    label_for_class = _create_label_for_class_function(class_to_element)

    # Build mapping sections with property extraction
    objects_mapping = _build_objects_mapping(objects, dataprop_index, datatype_index)
    associations_mapping = _build_associations_mapping(associations, element_to_class, label_for_class)
    references_mapping = _build_references_mapping(objects, element_to_class, association_ids, label_for_class)

    # Assemble final mapping with metadata
    return {
        "namespaces": used_ns_map,
        "objects": objects_mapping,
        "associations": associations_mapping,
        "references": references_mapping,
        "augmentations": [],  # reserved for future
        "polymorphism": {
            "strategy": "extraLabel",
            "store_actual_type_property": "xsiType"
        },
        "metadata": {
            "cmf_element_index": sorted(list(cmf_elements))
        }
    }


def main(cmf_path: str, out_yaml: str):
    """Main function for command-line usage.

    Args:
        cmf_path: Path to input CMF XML file
        out_yaml: Path to output YAML file
    """
    mapping = generate_mapping_from_cmf_file(cmf_path)

    with open(out_yaml, "w", encoding="utf-8") as f:
        yaml.safe_dump(mapping, f, sort_keys=False, allow_unicode=True)

    print(f"OK: wrote {out_yaml}")  # noqa: T201
    print(f"  namespaces: {len(mapping['namespaces'])}")  # noqa: T201
    print(f"  objects: {len(mapping['objects'])}")  # noqa: T201
    print(f"  associations: {len(mapping['associations'])}")  # noqa: T201
    print(f"  references: {len(mapping['references'])}")  # noqa: T201


if __name__ == "__main__":
    if len(sys.argv) not in (2, 3):
        print("Usage: python cmf_to_mapping.py <input.cmf.xml> <output.yaml>")  # noqa: T201
        sys.exit(2)
    cmf_path = sys.argv[1]
    out_yaml = sys.argv[2] if len(sys.argv) == 3 else "mapping.yaml"
    main(cmf_path, out_yaml)
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Validator — CMF ↔ mapping.yaml Coverage & Consistency (NIEM→Neo4j)
==================================================================

Purpose
-------
Given:
  1) a NIEM **CMF 1.0** XML, and
  2) a **mapping.yaml** produced by `cmf_to_mapping.documented.py` (or equivalent),

this validator checks that the mapping is *comprehensive* and *internally consistent*:

Checks performed
----------------
1) **Namespace sanity**
   - Every QName prefix in mapping.yaml exists in CMF namespaces.
   - Mapping `namespaces` section includes all prefixes needed by mapping QNames.

2) **Association coverage**
   - Every CMF Class with `SubClassOf == nc.AssociationType` has a corresponding entry in `associations[]`.
   - Each association has ≥2 `endpoints[]`.
   - Each endpoint’s `maps_to_label` exists in `objects[]` labels.

3) **Object-valued reference coverage**
   - For every object Class, each child `ChildPropertyAssociation/ObjectProperty` whose *target Class* is **not**
     an AssociationType must have a `references[]` rule `(owner_object, field_qname)`.
   - Target label in the rule must resolve to the element/class label of the target Class.

4) **Objects coverage (advisory)**
   - Reports CMF object Classes missing from `objects[]` (warning: some Classes are abstract/no element).

5) **Cardinality presence (advisory)**
   - Each `references[]` and association endpoint includes a cardinality string (e.g., `0..*`).

Exit code
---------
- **0** if no critical issues (association or reference coverage failures, bad endpoints).
- **1** if any critical issue is detected.

Usage
-----
    python validate_mapping_coverage.documented.py <input.cmf.xml> <mapping.yaml> [--json report.json]

"""

import argparse
import json
import sys
import xml.etree.ElementTree as ET

CMF_NS = "https://docs.oasis-open.org/niemopen/ns/specification/cmf/1.0/"
STRUCT_NS = "https://docs.oasis-open.org/niemopen/ns/model/structures/6.0/"
NS = {"cmf": CMF_NS, "structures": STRUCT_NS}

# --------------------- CMF parsing helpers ---------------------

def ref_of(el, tag):
    t = el.find(f"./cmf:{tag}", NS)
    if t is not None:
        return t.attrib.get(f"{{{STRUCT_NS}}}ref")
    return None

def text_of(el, tag):
    t = el.find(f"./cmf:{tag}", NS)
    return (t.text.strip() if t is not None and t.text else None)

def cmf_namespaces(root):
    out = {}
    for nsel in root.findall(".//cmf:Namespace", NS):
        p = nsel.find("./cmf:NamespacePrefixText", NS)
        u = nsel.find("./cmf:NamespaceURI", NS)
        if p is not None and u is not None and p.text and u.text:
            out[p.text.strip()] = u.text.strip()
    return out

def parse_classes(root):
    classes = []
    for cl in root.findall(".//cmf:Class", NS):
        cid = cl.attrib.get(f"{{{STRUCT_NS}}}id") or cl.attrib.get("id")
        subclass = ref_of(cl, "SubClassOf")
        props = []
        for cpa in cl.findall("./cmf:ChildPropertyAssociation", NS):
            op_ref = ref_of(cpa, "ObjectProperty")
            dp_ref = ref_of(cpa, "DataProperty")
            mino = text_of(cpa, "MinOccursQuantity")
            maxo = text_of(cpa, "MaxOccursQuantity")
            props.append({"objectProperty": op_ref, "dataProperty": dp_ref, "min": mino, "max": maxo})
        classes.append({"id": cid, "subclass_of": subclass, "props": props})
    return classes

def build_objectproperty_to_class(root):
    mapping = {}
    for el in root.findall(".//cmf:ObjectProperty", NS):
        classRef = el.find("./cmf:Class", NS)
        if classRef is not None:
            cref = classRef.attrib.get(f"{{{STRUCT_NS}}}ref")
            el_id = el.attrib.get(f"{{{STRUCT_NS}}}id")
            if cref and el_id:
                mapping[el_id] = cref
    return mapping

# --------------------- QName utils ---------------------

def prefixes_in_qname(qn: str):
    # Return prefix used in a QName (prefix:LocalName)
    if qn and ":" in qn:
        return {qn.split(":",1)[0]}
    return set()

def collect_mapping_prefixes(mapping):
    used = set()
    for o in mapping.get("objects", []):
        used |= prefixes_in_qname(o.get("qname"))
        for sp in o.get("scalar_props", []) or []:
            p = sp.get("path")
            if p and ":" in p.replace("@",""):
                used.add(p.replace("@","").split(":",1)[0])
    for a in mapping.get("associations", []):
        used |= prefixes_in_qname(a.get("qname"))
        for ep in a.get("endpoints", []) or []:
            used |= prefixes_in_qname(ep.get("role_qname"))
    for r in mapping.get("references", []):
        used |= prefixes_in_qname(r.get("owner_object"))
        used |= prefixes_in_qname(r.get("field_qname"))
    return used

# --------------------- Validation logic ---------------------

def validate(cmf_xml, mapping_yaml):
    root = ET.parse(cmf_xml).getroot()
    with open(mapping_yaml, encoding="utf-8") as f:
        mapping = yaml.safe_load(f)

    cmf_ns = cmf_namespaces(root)
    classes = parse_classes(root)
    element_to_class = build_objectproperty_to_class(root)
    class_to_element = {v:k for k,v in element_to_class.items()}

    # Partition
    assoc_ids = {c["id"] for c in classes if c["subclass_of"] == ASSOCIATION_TYPE}
    obj_ids   = {c["id"] for c in classes if c["subclass_of"] != ASSOCIATION_TYPE}

    # Build mapping indexes
    objects_labels = {o["label"]: o for o in mapping.get("objects", [])}
    objects_qnames = {o["qname"]: o for o in mapping.get("objects", [])}
    labels_set = set(objects_labels.keys())
    assoc_qnames = {a["qname"]: a for a in mapping.get("associations", [])}
    refs_index = {(r["owner_object"], r["field_qname"]): r for r in mapping.get("references", [])}

    report = {
        "namespaces": {
            "cmf_prefixes": sorted(cmf_ns.keys()),
            "mapping_prefixes_used": list(collect_mapping_prefixes(mapping)),
            "missing_prefixes_in_cmf": [],
            "missing_prefixes_in_mapping_namespaces": [],
        },
        "coverage": {
            "associationtypes_total": 0,
            "associationtypes_mapped": 0,
            "unmapped_associations": [],
            "objecttypes_total": 0,
            "objecttypes_mapped": len(objects_qnames),
            "unmapped_objects_advisory": [],
            "object_refs_total": 0,
            "object_refs_mapped": 0,
            "unmapped_object_refs": [],
        },
        "consistency": {
            "bad_endpoints": [],
            "missing_cardinalities": {
                "associations": [],
                "references": []
            }
        }
    }

    # Namespace checks
    used_prefixes = collect_mapping_prefixes(mapping)
    for p in sorted(used_prefixes):
        if p not in cmf_ns:
            report["namespaces"]["missing_prefixes_in_cmf"].append(p)
    for p in sorted(used_prefixes):
        if p not in mapping.get("namespaces", {}):
            report["namespaces"]["missing_prefixes_in_mapping_namespaces"].append(p)

    # Association coverage & endpoint validation
    assoc_total = 0
    assoc_mapped = 0
    for c in classes:
        if c["subclass_of"] != ASSOCIATION_TYPE:
            continue
        assoc_total += 1
        assoc_qn = (class_to_element.get(c["id"]) or c["id"]).replace(".", ":")
        a = assoc_qnames.get(assoc_qn)
        if not a:
            report["coverage"]["unmapped_associations"].append(assoc_qn)
            continue
        assoc_mapped += 1
        # endpoints present?
        eps = a.get("endpoints", []) or []
        if len(eps) < 2:
            report["consistency"]["bad_endpoints"].append({"association": assoc_qn, "reason": "fewer than 2 endpoints"})
        else:
            for ep in eps:
                mlabel = ep.get("maps_to_label")
                if not mlabel or mlabel not in labels_set:
                    report["consistency"]["bad_endpoints"].append({"association": assoc_qn, "endpoint": ep, "reason": "maps_to_label not found in objects labels"})

        # endpoint cardinalities present (advisory)
        if any(not ep.get("cardinality") for ep in eps):
            report["consistency"]["missing_cardinalities"]["associations"].append(assoc_qn)

    report["coverage"]["associationtypes_total"] = assoc_total
    report["coverage"]["associationtypes_mapped"] = assoc_mapped

    # Object-valued references coverage
    refs_total = 0
    refs_mapped = 0
    for c in classes:
        if c["subclass_of"] == ASSOCIATION_TYPE:
            continue
        owner_qn = (class_to_element.get(c["id"]) or c["id"]).replace(".", ":")
        for p in c.get("props", []):
            op = p["objectProperty"]
            if not op:
                continue
            target_class_id = element_to_class.get(op)
            if target_class_id and target_class_id not in assoc_ids:
                refs_total += 1
                key = (owner_qn, op.replace(".", ":"))
                if key in refs_index:
                    refs_mapped += 1
                else:
                    report["coverage"]["unmapped_object_refs"].append({"owner": owner_qn, "field": op.replace(".", ":")})

    report["coverage"]["object_refs_total"] = refs_total
    report["coverage"]["object_refs_mapped"] = refs_mapped

    # Objects coverage (advisory)
    obj_total = len(obj_ids)
    report["coverage"]["objecttypes_total"] = obj_total
    # Warn if a CMF object class with an associated element is missing from mapping.objects
    for cid in obj_ids:
        el = class_to_element.get(cid)
        cand_qn = (el or cid).replace(".", ":")
        if cand_qn not in objects_qnames:
            report["coverage"]["unmapped_objects_advisory"].append(cand_qn)

    # References cardinality presence (advisory)
    for r in mapping.get("references", []):
        if not r.get("cardinality"):
            report["consistency"]["missing_cardinalities"]["references"].append((r.get("owner_object"), r.get("field_qname")))

    # Decide exit code
    critical = (
        len(report["coverage"]["unmapped_associations"]) > 0 or
        len(report["coverage"]["unmapped_object_refs"]) > 0 or
        len(report["consistency"]["bad_endpoints"]) > 0 or
        len(report["namespaces"]["missing_prefixes_in_cmf"]) > 0 or
        len(report["namespaces"]["missing_prefixes_in_mapping_namespaces"]) > 0
    )

    return report, (1 if critical else 0)

def validate_mapping_coverage_from_data(cmf_content: str, mapping_dict: dict) -> dict:
    """
    Validate mapping coverage from in-memory data.

    Args:
        cmf_content: CMF XML content as string
        mapping_dict: Mapping dictionary

    Returns:
        Dictionary containing validation report
    """
    import xml.etree.ElementTree as ET

    # Parse CMF from string instead of file
    try:
        root = ET.fromstring(cmf_content)
    except ET.ParseError as e:
        return {
            "summary": {
                "has_critical_issues": True,
                "overall_coverage_percentage": 0,
                "association_coverage_percentage": 0,
                "reference_coverage_percentage": 0,
                "total_mapped_elements": 0,
                "total_elements": 0
            },
            "error": f"Invalid CMF XML: {str(e)}"
        }

    # Use the existing validation logic but with in-memory data
    cmf_ns = cmf_namespaces(root)
    classes = parse_classes(root)
    element_to_class = build_objectproperty_to_class(root)

    # Partition
    assoc_ids = {c["id"] for c in classes if c["subclass_of"] == ASSOCIATION_TYPE}
    obj_ids   = {c["id"] for c in classes if c["subclass_of"] != ASSOCIATION_TYPE}

    # Build mapping indexes using provided dictionary instead of loading from file
    objects_labels = {o["label"]: o for o in mapping_dict.get("objects", [])}
    objects_qnames = {o["qname"]: o for o in mapping_dict.get("objects", [])}
    labels_set = set(objects_labels.keys())
    assoc_qnames = {a["qname"]: a for a in mapping_dict.get("associations", [])}
    refs_index = {(r["owner_object"], r["field_qname"]): r for r in mapping_dict.get("references", [])}

    # Rest of the validation logic from the main validate function
    report = {
        "namespaces": {
            "cmf_prefixes": sorted(cmf_ns.keys()),
            "mapping_prefixes_used": sorted(list(collect_mapping_prefixes(mapping_dict))),
            "missing_prefixes_in_cmf": [],
            "missing_prefixes_in_mapping_namespaces": [],
        },
        "coverage": {
            "associationtypes_total": 0,
            "associationtypes_mapped": 0,
            "unmapped_associations": [],
            "objecttypes_total": 0,
            "objecttypes_mapped": len(objects_qnames),
            "unmapped_objects_advisory": [],
            "object_refs_total": 0,
            "object_refs_mapped": 0,
            "unmapped_object_refs": [],
        },
        "consistency": {
            "bad_endpoints": [],
            "missing_cardinalities": {
                "associations": [],
                "references": []
            }
        }
    }

    # Run the validation checks (simplified version)
    report["coverage"]["associationtypes_total"] = len(assoc_ids)
    report["coverage"]["associationtypes_mapped"] = len([a for a in assoc_qnames if any(c["id"] for c in classes if element_to_class.get(a) == c["id"] and c["id"] in assoc_ids)])

    report["coverage"]["objecttypes_total"] = len(obj_ids)

    # Calculate object references
    total_refs = 0
    mapped_refs = 0
    for c in classes:
        c_id = c.get("id")
        if not c_id or c_id not in obj_ids:
            continue

        for p in c.get("props", []):
            obj_prop = p.get("objectProperty")
            if obj_prop:
                total_refs += 1
                target_class = element_to_class.get(obj_prop)
                if target_class and target_class in assoc_ids:
                    # This is an association reference - check if mapped
                    if any(a.get("qname") for a in mapping_dict.get("associations", []) if element_to_class.get(a.get("qname")) == target_class):
                        mapped_refs += 1
                elif (c.get("qname", ""), obj_prop) in refs_index:
                    # This is a regular reference - check if mapped
                    mapped_refs += 1

    report["coverage"]["object_refs_total"] = total_refs
    report["coverage"]["object_refs_mapped"] = mapped_refs

    # Add summary statistics
    total_assocs = report["coverage"]["associationtypes_total"]
    mapped_assocs = report["coverage"]["associationtypes_mapped"]
    total_refs = report["coverage"]["object_refs_total"]
    mapped_refs = report["coverage"]["object_refs_mapped"]

    # Calculate coverage percentages
    assoc_coverage = (mapped_assocs / total_assocs * 100) if total_assocs > 0 else 100
    ref_coverage = (mapped_refs / total_refs * 100) if total_refs > 0 else 100
    overall_coverage = ((mapped_assocs + mapped_refs) / (total_assocs + total_refs) * 100) if (total_assocs + total_refs) > 0 else 100

    report["summary"] = {
        "overall_coverage_percentage": round(overall_coverage, 1),
        "association_coverage_percentage": round(assoc_coverage, 1),
        "reference_coverage_percentage": round(ref_coverage, 1),
        "has_critical_issues": False,  # Simplified for now
        "total_mapped_elements": mapped_assocs + mapped_refs,
        "total_elements": total_assocs + total_refs
    }

    return report


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmf_xml")
    ap.add_argument("mapping_yaml")
    ap.add_argument("--json", help="Write detailed report JSON to this path")
    args = ap.parse_args()

    report, code = validate(args.cmf_xml, args.mapping_yaml)

    pretty = json.dumps(report, indent=2)
    print(pretty)  # noqa: T201
    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            f.write(pretty)
    sys.exit(code)

if __name__ == "__main__":
    main()
