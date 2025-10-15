#!/usr/bin/env python3
"""NIEM XML to Cypher converter service.

This module converts NIEM XML documents to Neo4j Cypher statements using
a mapping dictionary. It supports role-based person modeling and NIEM
reference relationships.
"""
import argparse
import hashlib
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

import yaml

# NIEM structures namespace
STRUCT_NS = "https://docs.oasis-open.org/niemopen/ns/model/structures/6.0/"
XSI_NS = "http://www.w3.org/2001/XMLSchema-instance"


def load_mapping_from_dict(mapping_dict: dict[str, Any]) -> tuple[
    dict[str, Any], dict[str, Any], list[dict[str, Any]], list[dict[str, Any]], dict[str, str]
]:
    """Load mapping from dictionary instead of file.

    Args:
        mapping_dict: Dictionary containing mapping configuration

    Returns:
        Tuple containing (mapping_dict, obj_qnames, associations, references, namespaces)
    """
    obj_qnames = {o["qname"]: o for o in mapping_dict.get("objects", [])}
    associations = mapping_dict.get("associations", [])
    references = mapping_dict.get("references", [])
    namespaces = mapping_dict.get("namespaces", {})
    return mapping_dict, obj_qnames, associations, references, namespaces


def load_mapping(mapping_path: Path) -> tuple[
    dict[str, Any], dict[str, Any], list[dict[str, Any]], list[dict[str, Any]], dict[str, str]
]:
    """Load mapping from YAML file.

    Args:
        mapping_path: Path to the mapping YAML file

    Returns:
        Tuple containing (mapping, obj_qnames, associations, references, namespaces)
    """
    mapping = yaml.safe_load(mapping_path.read_text(encoding="utf-8"))
    obj_qnames = {o["qname"]: o for o in mapping.get("objects", [])}
    associations = mapping.get("associations", [])
    references = mapping.get("references", [])
    namespaces = mapping.get("namespaces", {})
    return mapping, obj_qnames, associations, references, namespaces


def parse_ns(xml_text: str) -> dict[str, str]:
    """Parse namespace declarations from XML text.

    Args:
        xml_text: XML document content

    Returns:
        Dictionary mapping namespace prefixes to URIs
    """
    ns_map = dict(re.findall(r'xmlns:([A-Za-z0-9_-]+)\s*=\s*"([^"]+)"', xml_text))
    match = re.search(r'xmlns\s*=\s*"([^"]+)"', xml_text)
    if match:
        ns_map[""] = match.group(1)
    return ns_map


def qname_from_tag(tag: str, ns_map: dict[str, str]) -> str:
    """Convert XML tag to qualified name using namespace map.

    Args:
        tag: XML element tag (may include namespace URI)
        ns_map: Namespace prefix to URI mapping

    Returns:
        Qualified name in prefix:localname format
    """
    if tag.startswith("{"):
        uri, local = tag[1:].split("}", 1)
        for prefix, namespace_uri in ns_map.items():
            if namespace_uri == uri and prefix != "":
                return f"{prefix}:{local}"
        return f"ns:{local}"
    return tag


def local_from_qname(qn: str) -> str:
    """Extract local name from qualified name.

    Args:
        qn: Qualified name in prefix:localname format

    Returns:
        Local name part
    """
    return qn.split(":")[-1]


def synth_id(parent_id: str, elem_qn: str, ordinal_path: str, file_prefix: str = "") -> str:
    """Generate synthetic ID for elements without explicit IDs.

    Args:
        parent_id: Parent element ID
        elem_qn: Element qualified name
        ordinal_path: Path indicating element position
        file_prefix: File-specific prefix for uniqueness across files

    Returns:
        Synthetic ID with file_prefix and 'syn_' prefix
    """
    basis = f"{parent_id}|{elem_qn}|{ordinal_path}"
    synth = "syn_" + hashlib.sha1(basis.encode("utf-8")).hexdigest()[:16]
    return f"{file_prefix}_{synth}" if file_prefix else synth


def build_refs_index(references: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """Build index of reference rules by owner object.

    Args:
        references: List of reference rule dictionaries

    Returns:
        Dictionary mapping owner object names to their reference rules
    """
    by_owner = {}
    for ref in references:
        by_owner.setdefault(ref["owner_object"], []).append(ref)
    return by_owner


def build_assoc_index(associations: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Build index of association rules by qualified name.

    Args:
        associations: List of association rule dictionaries

    Returns:
        Dictionary mapping association qualified names to their rules
    """
    by_qn = {}
    for assoc in associations:
        by_qn[assoc["qname"]] = assoc
    return by_qn


def is_augmentation(element_qname: str, cmf_element_index: set) -> bool:
    """Check if an element QName is an augmentation (not in CMF index).

    Args:
        element_qname: Qualified name of element (e.g., "nc:Person")
        cmf_element_index: Set of known CMF element QNames

    Returns:
        True if element is an augmentation/unmapped element
    """
    return element_qname not in cmf_element_index


def extract_unmapped_properties(
    elem: ET.Element,
    ns_map: dict[str, str],
    cmf_element_index: set
) -> dict[str, Any]:
    """Extract properties from unmapped/augmentation elements and attributes.

    Args:
        elem: XML element to process
        ns_map: Namespace mapping
        cmf_element_index: Set of known CMF element QNames

    Returns:
        Dictionary of augmentation properties with 'aug_' prefix
    """
    unmapped = {}

    # Extract unmapped attributes
    for attr, value in elem.attrib.items():
        # Skip structural attributes
        if attr.startswith(f"{{{STRUCT_NS}}}") or attr.startswith(f"{{{XSI_NS}}}"):
            continue

        attr_qn = qname_from_tag(attr, ns_map)
        if is_augmentation(attr_qn, cmf_element_index):
            prop_name = f"aug_{attr_qn.replace(':', '_').replace('.', '_')}"
            unmapped[prop_name] = value

    # Extract unmapped child elements with simple text content
    for child in elem:
        child_qn = qname_from_tag(child.tag, ns_map)

        # Skip if element is in CMF (handled by mapping)
        if not is_augmentation(child_qn, cmf_element_index):
            continue

        # Only extract if element has simple text content (no nested elements)
        if child.text and child.text.strip() and len(list(child)) == 0:
            prop_name = f"aug_{child_qn.replace(':', '_').replace('.', '_')}"
            text_value = child.text.strip()

            # Handle multiple occurrences (repeating elements)
            if prop_name in unmapped:
                # Convert to list on second occurrence
                if not isinstance(unmapped[prop_name], list):
                    unmapped[prop_name] = [unmapped[prop_name]]
                unmapped[prop_name].append(text_value)
            else:
                unmapped[prop_name] = text_value

    return unmapped


def handle_complex_augmentation(
    elem: ET.Element,
    ns_map: dict[str, str],
    parent_node_id: str,
    file_prefix: str,
    nodes: dict[str, list],
    contains: list[tuple]
) -> str:
    """Create separate augmentation node for complex nested structures.

    Args:
        elem: XML element (augmentation)
        ns_map: Namespace mapping
        parent_node_id: ID of parent node
        file_prefix: File-specific prefix for ID generation
        nodes: Nodes dictionary to update
        contains: Containment edges list to update

    Returns:
        Augmentation node ID
    """
    elem_qn = qname_from_tag(elem.tag, ns_map)

    # Generate synthetic ID for augmentation node
    aug_node_id = synth_id(parent_node_id, elem_qn, f"aug_{elem_qn}", file_prefix)

    # Recursively extract all properties
    properties = _extract_all_properties_recursive(elem, ns_map)

    # Create node with special 'Augmentation' label
    nodes[aug_node_id] = ["Augmentation", elem_qn, properties]

    # Link back to parent with special relationship
    parent_label = nodes[parent_node_id][0] if parent_node_id in nodes else "Unknown"
    contains.append((parent_node_id, parent_label, aug_node_id, "Augmentation", "AugmentedBy"))

    return aug_node_id


def _extract_all_properties_recursive(elem: ET.Element, ns_map: dict[str, str]) -> dict[str, Any]:
    """Recursively extract all properties from complex augmentation element.

    Args:
        elem: XML element
        ns_map: Namespace mapping

    Returns:
        Dictionary of flattened properties with dot notation
    """
    properties = {}

    # Extract attributes
    for attr, value in elem.attrib.items():
        # Skip structural attributes
        if attr.startswith(f"{{{STRUCT_NS}}}") or attr.startswith(f"{{{XSI_NS}}}"):
            continue

        qn = qname_from_tag(attr, ns_map)
        prop_name = qn.replace(':', '_').replace('.', '_')
        properties[prop_name] = value

    # Extract child elements
    for child in elem:
        child_qn = qname_from_tag(child.tag, ns_map)
        prop_name = child_qn.replace(':', '_').replace('.', '_')

        # If child has text content and no nested elements, store it
        if child.text and child.text.strip() and len(list(child)) == 0:
            properties[prop_name] = child.text.strip()
        elif len(list(child)) > 0:
            # If child has nested elements, recurse with dot notation
            nested_props = _extract_all_properties_recursive(child, ns_map)
            for nested_key, nested_value in nested_props.items():
                properties[f"{prop_name}.{nested_key}"] = nested_value

    return properties


def collect_scalar_setters(
    obj_rule: dict[str, Any], elem: ET.Element, ns_map: dict[str, str]
) -> list[tuple[str, str]]:
    """Collect scalar property setters for an object element.

    Args:
        obj_rule: Object rule from mapping
        elem: XML element
        ns_map: Namespace mapping

    Returns:
        List of (property_name, value) tuples
    """
    setters = []
    for prop in obj_rule.get("scalar_props", []) or []:
        path = prop["path"]  # e.g., "nc:PersonName/nc:PersonGivenName" or "@priv:foo"
        key = prop.get("neo4j_property") or prop.get("prop", path.replace(":", "_").replace("/", "_").replace("@", ""))
        value = None

        # Handle attribute paths
        if path.startswith("@"):
            attr_qn = path[1:]
            if ":" in attr_qn:
                pref, local = attr_qn.split(":", 1)
                # Find attribute by URI
                uri = None
                for prefix, namespace_uri in ns_map.items():
                    if prefix == pref:
                        uri = namespace_uri
                        break
                if uri:
                    value = elem.attrib.get(f"{{{uri}}}{local}")
                else:
                    value = elem.attrib.get(local)
            else:
                value = elem.attrib.get(attr_qn)
        else:
            # Handle nested element paths relative to current element
            cur = elem
            ok = True
            for seg in path.split("/"):
                if cur is not None:
                    # Find first child with matching qname
                    found = None
                    for ch in list(cur):
                        if qname_from_tag(ch.tag, ns_map) == seg:
                            found = ch
                            break
                    cur = found
                else:
                    ok = False
                    break
            if ok and cur is not None and (cur.text and cur.text.strip()):
                value = cur.text.strip()

        if value is not None:
            # Escape single quotes for Cypher
            escaped_value = value.replace("'", "\\'")
            setters.append((key, escaped_value))
    return setters


def generate_for_xml_content(
    xml_content: str, mapping_dict: dict[str, Any], filename: str = "memory", cmf_element_index: set = None
) -> tuple[str, dict[str, Any], list[tuple], list[tuple]]:
    """Generate Cypher statements from XML content and mapping dictionary.

    Args:
        xml_content: XML content as string
        mapping_dict: Mapping dictionary
        filename: Source filename for provenance
        cmf_element_index: Set of known CMF element QNames for augmentation detection

    Returns:
        Tuple of (cypher_statements, nodes_dict, contains_list, edges_list)
    """
    # Load mapping from dictionary
    mapping, obj_rules, associations, references, ns_map = load_mapping_from_dict(mapping_dict)

    # Extract CMF element index from mapping metadata if not provided
    if cmf_element_index is None:
        metadata = mapping_dict.get("metadata", {})
        cmf_elements_list = metadata.get("cmf_element_index", [])
        cmf_element_index = set(cmf_elements_list) if cmf_elements_list else set()

    # Prepare reference and association indices
    refs_by_owner = build_refs_index(references)
    assoc_by_qn = build_assoc_index(associations)

    root = ET.fromstring(xml_content)
    xml_ns_map = parse_ns(xml_content)

    # Generate file-specific prefix for node IDs to ensure uniqueness across files
    # Use timestamp + filename hash for uniqueness
    import json
    import time
    file_prefix = hashlib.sha1(f"{filename}_{time.time()}".encode()).hexdigest()[:8]

    nodes = {}  # id -> (label, qname, props_dict, aug_props_dict)
    edges = []  # (from_id, from_label, to_id, to_label, rel_type, rel_props)
    contains = []  # (parent_id, parent_label, child_id, child_label, HAS_REL)

    def get_metadata_refs(elem: ET.Element, xml_ns_map: dict[str, str]) -> list[str]:
        """Extract metadata reference IDs from nc:metadataRef or priv:privacyMetadataRef attributes.

        Args:
            elem: XML element
            xml_ns_map: Namespace mapping

        Returns:
            List of metadata reference IDs
        """
        metadata_refs = []

        # Check for nc:metadataRef
        for prefix, uri in xml_ns_map.items():
            if 'niem-core' in uri:
                nc_metadata_ref = elem.attrib.get(f"{{{uri}}}metadataRef")
                if nc_metadata_ref:
                    # Can be space-separated list of IDs
                    metadata_refs.extend(nc_metadata_ref.strip().split())
            elif 'PrivacyMetadata' in uri or '/priv' in uri:
                priv_metadata_ref = elem.attrib.get(f"{{{uri}}}privacyMetadataRef")
                if priv_metadata_ref:
                    # Can be space-separated list of IDs
                    metadata_refs.extend(priv_metadata_ref.strip().split())

        return metadata_refs

    def traverse(elem, parent_info=None, path_stack=None):
        """Traverse XML tree and generate nodes and relationships."""
        if path_stack is None:
            path_stack = []

        elem_qn = qname_from_tag(elem.tag, xml_ns_map)

        # Handle Association elements
        assoc_rule = assoc_by_qn.get(elem_qn)
        if assoc_rule:
            # Create the association edge between role endpoints
            role_refs = []
            endpoints = assoc_rule.get("endpoints", [])
            for ep in endpoints:
                to_id = None
                for ch in list(elem):
                    if qname_from_tag(ch.tag, xml_ns_map) == ep["role_qname"]:
                        to_id = ch.attrib.get(f"{{{STRUCT_NS}}}ref")
                        break
                role_refs.append((ep, to_id))

            # If both ends found, produce edge
            if len(role_refs) >= 2 and all(rid for (_, rid) in role_refs[:2]):
                ep_a, id_a = role_refs[0]
                ep_b, id_b = role_refs[1]
                label_a = ep_a["maps_to_label"]
                label_b = ep_b["maps_to_label"]
                rel = assoc_rule.get("rel_type")
                # Prefix referenced IDs with file_prefix
                id_a_prefixed = f"{file_prefix}_{id_a}"
                id_b_prefixed = f"{file_prefix}_{id_b}"
                edges.append((id_a_prefixed, label_a, id_b_prefixed, label_b, rel, {}))

            # Check if association should also be created as a node
            # (if it has metadata refs, structures:id, or explicit mapping that creates nodes)
            sid = elem.attrib.get(f"{{{STRUCT_NS}}}id")
            metadata_ref_list = get_metadata_refs(elem, xml_ns_map)
            has_metadata_refs = bool(metadata_ref_list)

            # If association has metadata or structures:id, continue processing as a node
            # Otherwise, traverse children and return
            if not (sid or has_metadata_refs):
                for ch in list(elem):
                    traverse(ch, parent_info, path_stack)
                return

            # Fall through to process association as a node (for metadata, etc.)

        # Handle Object elements (nodes)
        obj_rule = obj_rules.get(elem_qn)
        node_id = None
        node_label = None
        props = {}

        # Check if element has structures:id (makes it a node regardless of mapping)
        sid = elem.attrib.get(f"{{{STRUCT_NS}}}id")
        uri_ref = elem.attrib.get(f"{{{STRUCT_NS}}}uri")
        ref = elem.attrib.get(f"{{{STRUCT_NS}}}ref")
        is_nil = elem.attrib.get(f"{{{XSI_NS}}}nil") == "true"

        # Check if element is just a reference (ref or uri with nil)
        # These create the entity node (from element QName) and containment relationships
        if (ref or uri_ref) and is_nil:
            # Extract the target ID
            target_id = None
            if ref:
                target_id = f"{file_prefix}_{ref}"
            elif uri_ref:
                target_id = f"{file_prefix}_{uri_ref[1:]}" if uri_ref.startswith("#") else f"{file_prefix}_{uri_ref}"

            # Create or register entity node if not already exists
            # Use element QName to determine entity type (e.g., <nc:Person> creates nc:Person entity)
            if target_id and target_id not in nodes:
                entity_label = elem_qn.replace(":", "_")
                nodes[target_id] = [entity_label, elem_qn, {}, {}]

            # Create containment relationship from parent to referenced node
            if parent_info and target_id:
                parent_id, parent_label = parent_info
                rel = "HAS_" + re.sub(r'[^A-Za-z0-9]', '_', local_from_qname(elem_qn)).upper()
                entity_label = nodes[target_id][0] if target_id in nodes else elem_qn.replace(":", "_")
                contains.append((parent_id, parent_label, target_id, entity_label, rel))

            # Traverse children (though ref/nil elements typically have none)
            for ch in list(elem):
                traverse(ch, parent_info, path_stack)
            return

        # Check if element has metadata references (also makes it a node)
        metadata_ref_list = get_metadata_refs(elem, xml_ns_map)
        has_metadata_refs = bool(metadata_ref_list)

        if obj_rule or sid or has_metadata_refs:
            # Generate label from mapping or from element name
            if obj_rule:
                node_label = obj_rule["label"]
            else:
                # No mapping rule, but has structures:id - create node with qname-based label
                node_label = elem_qn.replace(":", "_")

            if sid:
                # Prefix structures:id with file_prefix to ensure uniqueness across files
                node_id = f"{file_prefix}_{sid}"
            elif uri_ref:
                # Handle structures:uri="#P01" -> create role node + entity reference
                # Entity type is determined by actual entity element in document
                if uri_ref.startswith("#"):
                    entity_id = f"{file_prefix}_{uri_ref[1:]}"  # Remove the "#" prefix and add file_prefix
                else:
                    entity_id = f"{file_prefix}_{uri_ref}"

                # Create the role node with synthetic ID
                parent_id = parent_info[0] if parent_info else "root"
                chain = [qname_from_tag(e.tag, xml_ns_map) for e in path_stack] + [elem_qn]
                ordinal_path = "/".join(chain)
                node_id = synth_id(parent_id, elem_qn, ordinal_path, file_prefix)

                # DON'T create entity node here - defer to actual entity element in document
                # This allows the pattern to work with any entity type (Person, Organization, etc.)

                # Create role-to-entity relationship with deferred label resolution
                # Label will be resolved when entity node is encountered/created
                edges.append((node_id, node_label, entity_id, None, "REPRESENTS", {}))
            else:
                parent_id = parent_info[0] if parent_info else "root"
                chain = [qname_from_tag(e.tag, xml_ns_map) for e in path_stack] + [elem_qn]
                ordinal_path = "/".join(chain)
                node_id = synth_id(parent_id, elem_qn, ordinal_path, file_prefix)

            # Collect scalar properties if configured
            if obj_rule:
                setters = collect_scalar_setters(obj_rule, elem, xml_ns_map)
                if setters:
                    for key, value in setters:
                        props[key] = value

            # Extract augmentation properties (unmapped data)
            aug_props = {}
            if cmf_element_index:
                aug_props = extract_unmapped_properties(elem, xml_ns_map, cmf_element_index)

                # Check for complex augmentation children (nested structures)
                for child in elem:
                    child_qn = qname_from_tag(child.tag, xml_ns_map)
                    if is_augmentation(child_qn, cmf_element_index) and len(list(child)) > 0:
                        # Child is an unmapped element with nested structure
                        # Create separate Augmentation node
                        handle_complex_augmentation(child, xml_ns_map, node_id, file_prefix, nodes, contains)

            # Register node
            if node_id in nodes:
                # Keep existing label, but extend props (don't overwrite)
                nodes[node_id][2].update({k: v for k, v in props.items() if k not in nodes[node_id][2]})
                # Merge augmentation properties
                if aug_props:
                    nodes[node_id][3].update({k: v for k, v in aug_props.items() if k not in nodes[node_id][3]})
            else:
                nodes[node_id] = [node_label, elem_qn, props, aug_props]

            # Create containment edge
            if parent_info:
                p_id, p_label = parent_info
                rel = "HAS_" + re.sub(r'[^A-Za-z0-9]', '_', local_from_qname(elem_qn)).upper()
                contains.append((p_id, p_label, node_id, node_label, rel))

            # Handle metadata references for CROSS-REFERENCES only
            # Metadata references (nc:metadataRef, priv:privacyMetadataRef) create semantic links
            # BUT we don't need them if the metadata is a direct structural child (already has containment edge)
            # For now, skip metadata reference edges entirely - containment edges are sufficient
            # The HAS_METADATA, HAS_PRIVACYMETADATA containment edges already capture the relationships
            metadata_refs = get_metadata_refs(elem, xml_ns_map)
            # Note: We're intentionally not creating metadata reference edges here
            # The structural containment edges (HAS_METADATA, HAS_PRIVACYMETADATA, etc.)
            # already capture the relationships between elements and their metadata

            parent_ctx = (node_id, node_label)
        else:
            parent_ctx = parent_info

        # Handle reference edges from mapping.references
        if elem_qn in refs_by_owner:
            for rule in refs_by_owner[elem_qn]:
                # Search children with matching field_qname and @structures:ref OR @structures:id
                for ch in list(elem):
                    if qname_from_tag(ch.tag, xml_ns_map) == rule["field_qname"]:
                        # Check for structures:ref first (traditional NIEM pattern)
                        to_id = ch.attrib.get(f"{{{STRUCT_NS}}}ref")
                        if not to_id:
                            # If no structures:ref, check for structures:id (direct child pattern)
                            to_id = ch.attrib.get(f"{{{STRUCT_NS}}}id")

                        if to_id and node_id:
                            # Prefix referenced ID with file_prefix
                            to_id_prefixed = f"{file_prefix}_{to_id}"
                            # Use the node_id that was assigned to this element
                            edges.append((
                                node_id, rule["owner_object"].replace(":", "_"),
                                to_id_prefixed, rule["target_label"],
                                rule["rel_type"], {}
                            ))

        # Recurse to children
        path_stack.append(elem)
        for ch in list(elem):
            traverse(ch, parent_ctx, path_stack)
        path_stack.pop()

    # Start traversal - skip root if it's not explicitly mapped and has no structures:id
    # This avoids creating redundant wrapper nodes
    root_qn = qname_from_tag(root.tag, xml_ns_map)
    root_has_id = root.attrib.get(f"{{{STRUCT_NS}}}id") is not None

    if root_qn not in obj_rules and not root_has_id:
        # Skip root element and process its children directly
        for child in list(root):
            traverse(child, None, [])
    else:
        # Root element is mapped or has structures:id, process normally
        traverse(root, None, [])

    # Resolve placeholder labels in edges (for metadata references)
    resolved_edges = []
    for fid, flabel, tid, tlabel, rel, rprops in edges:
        if tlabel is None and tid in nodes:
            # Resolve target label from nodes dictionary
            tlabel = nodes[tid][0]
        resolved_edges.append((fid, flabel, tid, tlabel, rel, rprops))
    edges = resolved_edges

    # Resolve placeholder labels in containment edges (for references)
    resolved_contains = []
    for pid, plabel, cid, clabel, rel in contains:
        if clabel is None and cid in nodes:
            # Resolve child label from nodes dictionary
            clabel = nodes[cid][0]
        resolved_contains.append((pid, plabel, cid, clabel, rel))
    contains = resolved_contains

    # Build Cypher lines
    lines = [f"// Generated for {filename} using mapping"]

    # MERGE nodes
    for nid, node_data in nodes.items():
        label = node_data[0]
        qn = node_data[1]
        props = node_data[2]
        aug_props = node_data[3] if len(node_data) > 3 else {}

        lines.append(f"MERGE (n:`{label}` {{id:'{nid}'}})")
        setbits = [f"n.qname='{qn}'", f"n.sourceDoc='{filename}'"]

        # Add core mapped properties
        for key, value in sorted(props.items()):
            # Escape property names with dots using backticks
            prop_key = f"`{key}`" if '.' in key else key
            setbits.append(f"n.{prop_key}='{value}'")

        # Add augmentation properties
        for key, value in sorted(aug_props.items()):
            # Escape property names with dots using backticks
            prop_key = f"`{key}`" if '.' in key else key
            if isinstance(value, list):
                # Store as JSON array for multiple values
                json_value = json.dumps(value).replace("'", "\\'")
                setbits.append(f"n.{prop_key}='{json_value}'")
            else:
                escaped_value = str(value).replace("'", "\\'")
                setbits.append(f"n.{prop_key}='{escaped_value}'")

        lines.append("  ON CREATE SET " + ", ".join(setbits) + ";")

    # MERGE containment edges
    for pid, plabel, cid, clabel, rel in contains:
        lines.append(f"MATCH (p:`{plabel}` {{id:'{pid}'}}), (c:`{clabel}` {{id:'{cid}'}}) MERGE (p)-[:`{rel}`]->(c);")

    # MERGE reference/association edges
    for fid, flabel, tid, tlabel, rel, rprops in edges:
        lines.append(f"MATCH (a:`{flabel}` {{id:'{fid}'}}), (b:`{tlabel}` {{id:'{tid}'}}) MERGE (a)-[:`{rel}`]->(b);")

    return "\n".join(lines), nodes, contains, edges


def main():
    """Command-line interface for the XML to Cypher converter."""
    parser = argparse.ArgumentParser(
        description="Universal NIEM→Neo4j importer (XML→Cypher) driven by CMF-derived mapping.yaml"
    )
    parser.add_argument("--mapping", required=True, help="Path to mapping.yaml")
    parser.add_argument("--xml", nargs="+", required=True, help="One or more XML files to import")
    parser.add_argument("--out", required=True, help="Output Cypher file")
    args = parser.parse_args()

    mapping, obj_rules, associations, references, namespaces = load_mapping(Path(args.mapping))

    all_lines = []
    for xml_file in args.xml:
        xml_path = Path(xml_file)
        xml_content = xml_path.read_text(encoding="utf-8")
        cypher, nodes, contains, edges = generate_for_xml_content(xml_content, mapping, xml_path.name)
        all_lines.append(cypher)

    Path(args.out).write_text("\n\n".join(all_lines), encoding="utf-8")
    print(f"OK: wrote Cypher to {args.out}")  # noqa: T201


if __name__ == "__main__":
    main()
