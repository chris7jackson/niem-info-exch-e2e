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
from typing import Any, Dict, List, Set, Tuple
import xml.etree.ElementTree as ET

import yaml

# NIEM CMF and structures namespaces
CMF_NS = "https://docs.oasis-open.org/niemopen/ns/specification/cmf/1.0/"
STRUCT_NS = "https://docs.oasis-open.org/niemopen/ns/model/structures/6.0/"
NS = {"cmf": CMF_NS, "structures": STRUCT_NS}


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


def build_prefix_map(root: ET.Element) -> Dict[str, str]:
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


def _parse_property_associations(class_element: ET.Element) -> List[Dict[str, str]]:
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


def _extract_class_info(class_element: ET.Element) -> Dict[str, Any]:
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


def _is_meaningful_class(class_info: Dict[str, Any]) -> bool:
    """Check if a class has meaningful content.

    Args:
        class_info: Class information dictionary

    Returns:
        True if class has meaningful content
    """
    return any([
        class_info["id"],
        class_info["name"],
        class_info["namespace_prefix"],
        class_info["subclass_of"],
        class_info["props"]
    ])


def parse_classes(root: ET.Element) -> List[Dict[str, Any]]:
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


def build_element_to_class(root: ET.Element) -> Dict[str, str]:
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


def _partition_classes(
    class_index: Dict[str, Dict[str, Any]],
    class_to_element: Dict[str, str]
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], Set[str]]:
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

        if class_info["subclass_of"] == "nc.AssociationType":
            association_ids.add(class_id)
            associations.append(class_data)
        else:
            objects.append(class_data)

    return objects, associations, association_ids


def _collect_used_prefixes(classes: List[Dict[str, Any]]) -> Set[str]:
    """Collect all namespace prefixes used by classes and their properties.

    Args:
        classes: List of class information dictionaries

    Returns:
        Set of used namespace prefixes
    """
    used_prefixes = set()
    for class_info in classes:
        if class_info["namespace_prefix"]:
            used_prefixes.add(class_info["namespace_prefix"])

        for prop in class_info["props"]:
            for ref in (prop["objectProperty"], prop["dataProperty"]):
                if ref and "." in ref:
                    used_prefixes.add(ref.split(".", 1)[0])

    return used_prefixes


def _create_label_for_class_function(
    class_to_element: Dict[str, str]
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


def _build_objects_mapping(objects: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Build objects section of the mapping.

    Args:
        objects: List of object class data

    Returns:
        List of object mapping entries
    """
    objects_mapping = []
    for obj in objects:
        qn = to_qname((obj["element_qname"] or obj["class_id"]))
        objects_mapping.append({
            "qname": qn,
            "label": to_label(qn),
            "carries_structures_id": True,
            "scalar_props": []
        })
    return objects_mapping


def _build_association_endpoint(
    prop: Dict[str, str],
    element_to_class: Dict[str, str],
    label_for_class: callable,
    endpoint_index: int
) -> Dict[str, str]:
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
    associations: List[Dict[str, Any]],
    element_to_class: Dict[str, str],
    label_for_class: callable
) -> List[Dict[str, Any]]:
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

        for prop in class_info["props"]:
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
    objects: List[Dict[str, Any]],
    element_to_class: Dict[str, str],
    association_ids: Set[str],
    label_for_class: callable
) -> List[Dict[str, Any]]:
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

        for prop in class_info["props"]:
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


def generate_mapping_from_cmf_content(cmf_content: str) -> Dict[str, Any]:
    """Generate mapping dictionary from CMF XML content string.

    Args:
        cmf_content: CMF XML content as string

    Returns:
        Dictionary containing the mapping structure
    """
    root = ET.fromstring(cmf_content)
    return _generate_mapping_from_root(root)


def generate_mapping_from_cmf_file(cmf_path: str) -> Dict[str, Any]:
    """Generate mapping dictionary from CMF XML file.

    Args:
        cmf_path: Path to CMF XML file

    Returns:
        Dictionary containing the mapping structure
    """
    root = ET.parse(cmf_path).getroot()
    return _generate_mapping_from_root(root)


def _generate_mapping_from_root(root: ET.Element) -> Dict[str, Any]:
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

    # Partition classes and collect used prefixes
    objects, associations, association_ids = _partition_classes(class_index, class_to_element)
    used_prefixes = _collect_used_prefixes(classes)
    used_ns_map = {k: v for k, v in prefixes_all.items() if k in used_prefixes}

    # Create helper function
    label_for_class = _create_label_for_class_function(class_to_element)

    # Build mapping sections
    objects_mapping = _build_objects_mapping(objects)
    associations_mapping = _build_associations_mapping(associations, element_to_class, label_for_class)
    references_mapping = _build_references_mapping(objects, element_to_class, association_ids, label_for_class)

    # Assemble final mapping
    return {
        "namespaces": used_ns_map,
        "objects": objects_mapping,
        "associations": associations_mapping,
        "references": references_mapping,
        "augmentations": [],  # reserved for future
        "polymorphism": {
            "strategy": "extraLabel",
            "store_actual_type_property": "xsiType"
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

    print(f"OK: wrote {out_yaml}")
    print(f"  namespaces: {len(mapping['namespaces'])}")
    print(f"  objects: {len(mapping['objects'])}")
    print(f"  associations: {len(mapping['associations'])}")
    print(f"  references: {len(mapping['references'])}")


if __name__ == "__main__":
    if len(sys.argv) not in (2, 3):
        print("Usage: python cmf_to_mapping.py <input.cmf.xml> <output.yaml>")
        sys.exit(2)
    cmf_path = sys.argv[1]
    out_yaml = sys.argv[2] if len(sys.argv) == 3 else "mapping.yaml"
    main(cmf_path, out_yaml)