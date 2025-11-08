#!/usr/bin/env python3
"""NIEM XML to Cypher converter service.

This module converts NIEM XML documents to Neo4j Cypher statements using
a mapping dictionary. It supports role-based person modeling and NIEM
reference relationships.
"""
import argparse
import hashlib
import re
# Use defusedxml for secure XML parsing (prevents XXE attacks)
import defusedxml.ElementTree as ET
# Import Element type from standard library for type hints
from xml.etree.ElementTree import Element
from pathlib import Path
from typing import Any

import yaml
import logging

# Initialize logger for this module
logger = logging.getLogger(__name__)

# XSI namespace for xsi:nil and other schema instance attributes
XSI_NS = "http://www.w3.org/2001/XMLSchema-instance"

# Cypher property name validation pattern - only alphanumeric and underscore are safe
# Property names with dots, hyphens, or other special chars must be escaped with backticks
CYPHER_SAFE_PROPERTY_NAME = r'^[a-zA-Z_][a-zA-Z0-9_]*$'

# Known NIEM structures namespaces (for dynamic detection)
KNOWN_STRUCT_NAMESPACES = [
    "https://docs.oasis-open.org/niemopen/ns/model/structures/6.0/",  # NIEM Open 6.0
    "http://release.niem.gov/niem/structures/5.0/",                    # NIEM 5.0
    "http://release.niem.gov/niem/structures/4.0/",                    # NIEM 4.0
    "http://release.niem.gov/niem/structures/3.0/",                    # NIEM 3.0
]


def detect_structures_namespace(root: Element) -> str:
    """
    Detect NIEM structures namespace from XML document.

    Checks namespace declarations on root element for known NIEM
    structures namespace URIs. Supports NIEM 3.0, 4.0, 5.0, and 6.0.

    Args:
        root: Root element of XML document

    Returns:
        Structures namespace URI, or NIEM 6.0 default if not found
    """
    # Check declared namespaces
    if hasattr(root, 'nsmap') and root.nsmap:
        for ns_uri in root.nsmap.values():
            if ns_uri and ns_uri in KNOWN_STRUCT_NAMESPACES:
                logger.debug(f"Detected NIEM structures namespace: {ns_uri}")
                return ns_uri

    # Fallback: check attributes for structures namespace
    for attr_key in root.attrib.keys():
        if '{' in attr_key:
            ns_uri = attr_key[1:attr_key.index('}')]
            if ns_uri in KNOWN_STRUCT_NAMESPACES:
                logger.debug(f"Detected structures namespace from attributes: {ns_uri}")
                return ns_uri

    # Default to NIEM 6.0
    logger.debug("No structures namespace detected, defaulting to NIEM 6.0")
    return KNOWN_STRUCT_NAMESPACES[0]


def get_structures_attr(elem: Element, attr_local_name: str, struct_ns: str = None) -> str | None:
    """
    Get structures attribute value by local name, trying known namespaces.

    Supports any NIEM structures namespace (3.0, 4.0, 5.0, 6.0) by checking
    the detected namespace first, then falling back to all known namespaces.

    Args:
        elem: XML element
        attr_local_name: Local attribute name (e.g., "id", "ref", "uri")
        struct_ns: Detected structures namespace URI (optional)

    Returns:
        Attribute value or None if not found
    """
    # Try detected namespace first (fastest path)
    if struct_ns:
        val = elem.attrib.get(f"{{{struct_ns}}}{attr_local_name}")
        if val:
            return val

    # Fallback: try all known structures namespaces
    for ns in KNOWN_STRUCT_NAMESPACES:
        val = elem.attrib.get(f"{{{ns}}}{attr_local_name}")
        if val:
            return val

    return None


def build_standard_reference_registry(struct_ns: str, nc_ns: str) -> dict:
    """
    Build registry of known NIEM reference attributes.

    Args:
        struct_ns: NIEM structures namespace URI
        nc_ns: NIEM core namespace URI

    Returns:
        Dict mapping {attr_qname: {"cardinality": "single"|"multiple", "edge_type": str}}
    """
    return {
        # Structures namespace (version-specific)
        f"{{{struct_ns}}}ref": {"cardinality": "single", "edge_type": "REFERS_TO"},
        f"{{{struct_ns}}}uri": {"cardinality": "single", "edge_type": "REFERS_TO"},

        # NIEM Core metadata (standard)
        f"{{{nc_ns}}}metadataRef": {"cardinality": "multiple", "edge_type": "HAS_METADATA"},
        f"{{{nc_ns}}}metadata": {"cardinality": "multiple", "edge_type": "HAS_METADATA"},
    }


def detect_reference_by_heuristic(attr_qname: str, attr_value: str) -> dict | None:
    """
    Detect if attribute is likely a reference using heuristics.

    Args:
        attr_qname: Qualified attribute name (e.g., "priv:privacyMetadataRef")
        attr_value: Attribute value

    Returns:
        {"cardinality": "single"|"multiple"|"auto", "edge_type": str, "confidence": str}
        or None if not detected as reference
    """
    local_name = attr_qname.split(':')[-1] if ':' in attr_qname else attr_qname

    # Pattern 1: Ends with "Ref" or "Reference"
    if re.match(r'.*[Rr]ef(erence)?$', local_name):
        # Auto-detect cardinality from value (space = multiple)
        cardinality = "auto"
        edge_type = f"HAS_{local_name.upper()}"
        return {"cardinality": cardinality, "edge_type": edge_type, "confidence": "medium"}

    # Pattern 2: Contains "metadata" + "ref" (case insensitive)
    if "metadata" in local_name.lower() and "ref" in local_name.lower():
        return {"cardinality": "multiple", "edge_type": "HAS_METADATA", "confidence": "medium"}

    # Pattern 3: Value looks like ID(s) - alphanumeric with optional spaces
    if attr_value and re.match(r'^[A-Za-z0-9_-]+(\s+[A-Za-z0-9_-]+)*$', attr_value):
        # Very low confidence - only use as last resort
        return {"cardinality": "auto", "edge_type": "REFERS_TO", "confidence": "low"}

    return None


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
    # SHA1 used for synthetic ID generation only, not cryptographic security
    synth = "syn_" + hashlib.sha1(basis.encode("utf-8"), usedforsecurity=False).hexdigest()[:16]
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


def build_augmentation_index_from_mapping(mapping_dict: dict) -> dict[str, dict]:
    """Build index: augmentation_element_qname → definition from mapping.

    Args:
        mapping_dict: The mapping dictionary containing augmentations

    Returns:
        Dictionary mapping augmentation element qname to augmentation definition
    """
    aug_index = {}
    for aug in mapping_dict.get('augmentations', []):
        aug_index[aug['augmentation_element_qname']] = aug
    return aug_index


def process_reference_attributes(
    elem: Element,
    node_id: str,
    node_label: str,
    file_prefix: str,
    ns_map: dict,
    reference_registry: dict,
    struct_ns: str
) -> list:
    """
    Detect and process all reference attributes on element.
    Creates reference edges for each target ID (splitting IDREFS).

    Args:
        elem: XML element to process
        node_id: ID of current node
        node_label: Label of current node
        file_prefix: File-specific prefix for IDs
        ns_map: Namespace mapping
        reference_registry: Registry of known reference attributes
        struct_ns: Structures namespace URI

    Returns:
        List of edge tuples: (from_id, from_label, to_id, to_label, rel_type, props)
    """
    edges = []

    for attr, value in elem.attrib.items():
        # Skip nil and structural attributes
        if not value or attr.startswith(f"{{{XSI_NS}}}"):
            continue

        # Skip if already handled (structures:id, structures:ref handled elsewhere)
        if attr in [f"{{{struct_ns}}}id", f"{{{struct_ns}}}ref", f"{{{struct_ns}}}uri"]:
            continue

        # Get qualified name
        attr_qname = qname_from_tag(attr, ns_map)

        # Check if this is a reference attribute (4-tier strategy)
        ref_info = None

        # Tier 1: Standard registry
        if attr in reference_registry:
            ref_info = reference_registry[attr]

        # Tier 2: XSD-based (future enhancement)
        # elif attr in xsd_reference_attrs:
        #     ref_info = xsd_reference_attrs[attr]

        # Tier 3: Heuristic detection
        else:
            ref_info = detect_reference_by_heuristic(attr_qname, value)

        if not ref_info:
            continue

        # Determine cardinality and split if needed
        if ref_info["cardinality"] == "multiple":
            target_ids = value.split()  # Split on whitespace
        elif ref_info["cardinality"] == "auto":
            target_ids = value.split() if ' ' in value else [value]
        else:
            target_ids = [value]

        # Create edge for each target
        for target_id in target_ids:
            target_id_prefixed = f"{file_prefix}_{target_id}"

            edges.append((
                node_id,
                node_label,
                target_id_prefixed,
                None,  # Target label unknown (resolved later)
                ref_info["edge_type"],
                {
                    "source_attribute": attr_qname,
                    "confidence": ref_info.get("confidence", "high")
                }
            ))

            logger.debug(f"Detected reference: {node_id} --{ref_info['edge_type']}--> {target_id_prefixed} (via {attr_qname})")

    return edges


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
    elem: Element,
    ns_map: dict[str, str],
    cmf_element_index: set,
    struct_ns: str
) -> dict[str, Any]:
    """Extract augmentation properties to be added to edges (associations).

    This function specifically handles augmentation elements/attributes that should
    be added as properties on association edges, not as separate nodes.
    For flattening unselected complex elements into nodes, see _recursively_flatten_element.

    Args:
        elem: XML element to process (typically an association)
        ns_map: Namespace mapping
        cmf_element_index: Set of known CMF element QNames
        struct_ns: NIEM structures namespace URI

    Returns:
        Dictionary of augmentation properties with 'aug_' prefix
    """
    unmapped = {}

    # Extract unmapped attributes
    for attr, value in elem.attrib.items():
        # Skip structural attributes - try detected namespace first, then fallback
        is_struct_attr = False
        if struct_ns and attr.startswith(f"{{{struct_ns}}}"):
            is_struct_attr = True
        else:
            for ns in KNOWN_STRUCT_NAMESPACES:
                if attr.startswith(f"{{{ns}}}"):
                    is_struct_attr = True
                    break

        if is_struct_attr or attr.startswith(f"{{{XSI_NS}}}"):
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


# Note: Removed unused handle_complex_augmentation and _extract_all_properties_recursive functions
# These were replaced by the new _recursively_flatten_element function which handles
# recursive flattening of unselected elements during ingestion


def _recursively_flatten_element(
    elem: Element,
    ns_map: dict[str, str],
    obj_rules: dict[str, Any],
    assoc_by_qn: dict[str, Any],
    cmf_element_index: set,
    path_prefix: str = "",
    struct_ns: str = None
) -> dict[str, Any]:
    """Recursively flatten an unselected element and all its descendants.

    This function extracts ALL data from an unselected element tree,
    building hierarchical property names like PersonName.PersonGivenName.

    Args:
        elem: XML element to flatten
        ns_map: Namespace mapping
        obj_rules: Dictionary of elements that should become nodes
        assoc_by_qn: Dictionary of association elements
        cmf_element_index: Set of known CMF elements for augmentation detection
        path_prefix: Accumulated property path prefix
        struct_ns: NIEM structures namespace URI

    Returns:
        Dictionary of flattened properties with dot-notation paths
    """
    properties = {}
    elem_qn = qname_from_tag(elem.tag, ns_map)

    # Build property prefix for this level with double underscore delimiter
    # Single underscore for namespace colons, double underscore for hierarchy
    elem_normalized = elem_qn.replace(':', '_')
    current_prefix = f"{path_prefix}__{elem_normalized}" if path_prefix else elem_normalized

    # Extract attributes (skip structural ones)
    for attr, value in elem.attrib.items():
        # Skip NIEM structural attributes - check detected namespace and fallback
        is_struct_attr = False
        if struct_ns and f"{{{struct_ns}}}" in attr:
            is_struct_attr = True
        else:
            for ns in KNOWN_STRUCT_NAMESPACES:
                if f"{{{ns}}}" in attr:
                    is_struct_attr = True
                    break

        if is_struct_attr or f"{{{XSI_NS}}}" in attr or attr.startswith("xmlns"):
            continue
        # Convert attribute to qname
        if "{" in attr:
            attr_qn = qname_from_tag(attr, ns_map)
        else:
            attr_qn = attr
        prop_name = f"{current_prefix}__@{attr_qn.replace(':', '_')}"
        properties[prop_name] = value

    # If element has simple text content and no children, capture it
    if elem.text and elem.text.strip() and len(list(elem)) == 0:
        # Store the text value directly at current_prefix
        properties[current_prefix] = elem.text.strip()
        return properties

    # Process children
    for child in elem:
        child_qn = qname_from_tag(child.tag, ns_map)

        # Skip if child should be a node (selected in designer)
        if child_qn in obj_rules:
            continue

        # Skip if child is an association (creates relationships, not properties)
        if child_qn in assoc_by_qn:
            continue

        # Check if child has structures:id or uri (makes it a node)
        child_sid = get_structures_attr(child, "id", struct_ns)
        child_uri = get_structures_attr(child, "uri", struct_ns)
        if child_sid or child_uri:
            continue

        # If child has simple text and no nested elements, store it
        if child.text and child.text.strip() and len(list(child)) == 0:
            prop_name = f"{current_prefix}__{child_qn.replace(':', '_')}"
            properties[prop_name] = child.text.strip()

        # If child has nested elements, recurse
        elif len(list(child)) > 0:
            nested_props = _recursively_flatten_element(
                child, ns_map, obj_rules, assoc_by_qn, cmf_element_index, current_prefix, struct_ns
            )
            properties.update(nested_props)

    return properties


def collect_scalar_setters(
    obj_rule: dict[str, Any], elem: Element, ns_map: dict[str, str]
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
                    for ch in cur:
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
            # Escape backslashes first, then single quotes for Cypher
            escaped_value = value.replace("\\", "\\\\").replace("'", "\\'")
            setters.append((key, escaped_value))
    return setters


def _is_complex_element(elem: Element, ns_map: dict[str, str], struct_ns: str) -> bool:
    """Determine if element is complex (should become a node in dynamic mode).

    Complex elements have:
    1. Child elements (not just text), OR
    2. Attributes (beyond structural ones), OR
    3. structures:id/uri (explicitly identifiable)

    Simple text elements become properties, not nodes.

    Args:
        elem: XML element
        ns_map: Namespace mapping
        struct_ns: Structures namespace URI

    Returns:
        True if element should become a node
    """
    # Check for structures:id or structures:uri (always makes it a node)
    if get_structures_attr(elem, "id", struct_ns) or get_structures_attr(elem, "uri", struct_ns):
        return True

    # Check for child elements (not just text)
    has_child_elements = len(list(elem)) > 0
    if has_child_elements:
        return True

    # Check for non-structural attributes
    for attr in elem.attrib.keys():
        # Skip structural attributes
        if attr.startswith(f"{{{struct_ns}}}") or attr.startswith(f"{{{XSI_NS}}}"):
            continue
        # Found a non-structural attribute
        return True

    # Element is simple (just text) - becomes a property
    return False


def detect_associations_from_xml_data(root: Element, xml_ns_map: dict[str, str]) -> dict[str, dict[str, Any]]:
    """Auto-detect association patterns in XML data for dynamic mode.

    NIEM associations follow naming convention: elements ending with "Association"
    that have 2+ child elements representing endpoint roles.

    Args:
        root: XML root element
        xml_ns_map: Namespace prefix mapping

    Returns:
        Dictionary mapping association QName to association rule
    """
    from .converter import qname_from_tag

    auto_assocs = {}

    def scan_element_for_associations(elem: Element):
        """Recursively scan element for association patterns."""
        elem_qn = qname_from_tag(elem.tag, xml_ns_map)

        # Check if this looks like an association (ends with "Association")
        if elem_qn.endswith("Association"):
            # Extract potential endpoints (child elements)
            endpoints = []

            for child in elem:
                child_qn = qname_from_tag(child.tag, xml_ns_map)

                # Check if child has a reference (structures:ref, structures:uri, or structures:id)
                # This indicates it's an endpoint role, not just a property
                has_ref = False
                for attr in child.attrib.keys():
                    if 'ref' in attr.lower() or 'uri' in attr.lower() or 'id' in attr.lower():
                        if any(ns in attr for ns in ['structures', 's:']):
                            has_ref = True
                            break

                if has_ref:
                    endpoints.append({
                        "role_qname": child_qn,
                        "maps_to_label": child_qn.replace(":", "_"),
                        "direction": "source" if len(endpoints) == 0 else "target",
                        "via": "structures:ref",
                        "cardinality": "0..*"
                    })

            # Valid association must have 2+ endpoints
            if len(endpoints) >= 2:
                auto_assocs[elem_qn] = {
                    "qname": elem_qn,
                    "rel_type": elem_qn.replace(":", "_").upper(),
                    "endpoints": endpoints,
                    "rel_props": []
                }
                logger.info(f"Auto-detected association: {elem_qn} with {len(endpoints)} endpoints: {[ep['role_qname'] for ep in endpoints]}")

        # Recurse into children
        for child in elem:
            scan_element_for_associations(child)

    # Scan entire XML tree
    scan_element_for_associations(root)

    return auto_assocs


def generate_for_xml_content(
    xml_content: str, mapping_dict: dict[str, Any], filename: str = "memory", upload_id: str = None, schema_id: str = None, cmf_element_index: set = None, mode: str = "dynamic"
) -> tuple[str, dict[str, Any], list[tuple], list[tuple]]:
    """Generate Cypher statements from XML content and mapping dictionary.

    Args:
        xml_content: XML content as string
        mapping_dict: Mapping dictionary
        filename: Source filename for provenance
        upload_id: Unique identifier for this upload batch (for graph isolation)
        schema_id: Schema identifier (for graph isolation)
        cmf_element_index: Set of known CMF element QNames for augmentation detection
        mode: Converter mode - "mapping" (use selections) or "dynamic" (all complex elements)

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

    # In dynamic mode, disable augmentation detection (all properties are standard)
    if mode == "dynamic":
        cmf_element_index = set()
        logger.info("Dynamic mode: Augmentation detection disabled")

    # Prepare reference and association indices
    refs_by_owner = build_refs_index(references)
    assoc_by_qn = build_assoc_index(associations)

    # Build augmentation index from mapping
    augmentation_index = build_augmentation_index_from_mapping(mapping_dict)

    root = ET.fromstring(xml_content)
    xml_ns_map = parse_ns(xml_content)

    # In dynamic mode, auto-detect associations from XML structure
    if mode == "dynamic":
        auto_detected_assocs = detect_associations_from_xml_data(root, xml_ns_map)
        assoc_by_qn.update(auto_detected_assocs)
        logger.info(f"Dynamic mode: Total associations (mapping + auto-detected): {len(assoc_by_qn)}")

    # Detect NIEM structures namespace dynamically
    struct_ns = detect_structures_namespace(root)

    # Detect NIEM core namespace (attempt to find from namespaces)
    nc_ns = ns_map.get("nc", "https://docs.oasis-open.org/niemopen/ns/model/niem-core/6.0/")

    # Build reference attribute registry
    reference_registry = build_standard_reference_registry(struct_ns, nc_ns)

    # Generate file-specific prefix for node IDs to ensure uniqueness across files
    # Use timestamp + filename hash for uniqueness
    import json
    import time
    from datetime import datetime, timezone

    # SHA1 used for file prefix generation only, not cryptographic security
    file_prefix = hashlib.sha1(f"{filename}_{time.time()}".encode(), usedforsecurity=False).hexdigest()[:8]
    ingest_timestamp = datetime.now(timezone.utc).isoformat()

    nodes = {}  # id -> (label, qname, props_dict, aug_props_dict)
    edges = []  # (from_id, from_label, to_id, to_label, rel_type, rel_props)
    contains = []  # (parent_id, parent_label, child_id, child_label, HAS_REL)

    # ID registry for two-pass traversal
    # Collect all IDs in first pass to enable forward reference resolution
    id_registry = {}  # id -> element info for deferred processing
    uri_entity_registry = {}  # Track URI-based entities for co-referencing
    pending_refs = []  # List of (source_id, target_id, context) for validation
    id_collisions = []  # List of ID collisions detected during Pass 1

    def collect_ids_pass1(elem: Element):
        """Pass 1: Collect all elements with structures:id or structures:uri for forward reference resolution.

        Args:
            elem: XML element to process
        """
        sid = get_structures_attr(elem, "id", struct_ns)
        uri_ref = get_structures_attr(elem, "uri", struct_ns)

        # Process structures:id
        if sid:
            prefixed_id = f"{file_prefix}_{sid}"
            elem_qn = qname_from_tag(elem.tag, xml_ns_map)

            # Check for ID collisions
            if prefixed_id in id_registry:
                # ID collision detected - same structures:id used multiple times
                existing_qn = id_registry[prefixed_id]['qname']
                id_collisions.append({
                    'id': sid,
                    'first_qname': existing_qn,
                    'second_qname': elem_qn,
                    'prefixed_id': prefixed_id
                })
                # Keep the first occurrence in the registry
                # Later we can decide whether to error or warn
            else:
                # Register new ID
                id_registry[prefixed_id] = {
                    'element': elem,
                    'qname': elem_qn,
                    'raw_id': sid
                }

        # Process structures:uri - these also define identifiable resources
        # URI fragments (#P01) or full URIs can be used as identifiers
        if uri_ref and not sid:  # Only if no structures:id (structures:id takes precedence)
            # Extract fragment or basename from URI
            uri_id = None
            if '#' in uri_ref:
                uri_id = uri_ref.split('#')[-1]
            else:
                # Use last path segment as ID
                uri_parts = uri_ref.rstrip('/').split('/')
                if uri_parts:
                    uri_id = uri_parts[-1].replace(':', '_')

            if uri_id:
                prefixed_id = f"{file_prefix}_{uri_id}"
                elem_qn = qname_from_tag(elem.tag, xml_ns_map)

                # Check for ID collisions
                if prefixed_id in id_registry:
                    # Multiple elements with same URI - this is valid in NIEM (co-referencing)
                    # Don't add to collisions, just skip registering duplicate
                    pass
                else:
                    # Register new URI-based ID
                    id_registry[prefixed_id] = {
                        'element': elem,
                        'qname': elem_qn,
                        'raw_id': uri_id,
                        'source': 'uri'
                    }

        # Recurse to all children
        for child in elem:
            collect_ids_pass1(child)

    def traverse(elem, parent_info=None, path_stack=None):
        """Traverse XML tree and generate nodes and relationships.

        CRITICAL: Augmentations are processed FIRST to ensure they never create nodes.

        Processing order:
        1. Augmentations (transparent - flatten children into parent)
        2. Associations (create intermediate hypergraph nodes)
        3. Objects (create entity nodes)

        This order ensures augmentations are completely invisible in the graph.
        """
        if path_stack is None:
            path_stack = []

        elem_qn = qname_from_tag(elem.tag, xml_ns_map)

        # ============================================================================
        # AUGMENTATION HANDLING (MUST BE FIRST!)
        # ============================================================================
        # Check for augmentation FIRST (before associations or objects)
        # Augmentations are NIEM schema constructs that should NEVER become nodes.
        # They exist only to extend types from other namespaces without modification.
        #
        # Detection: Elements with qname ending in "Augmentation"
        # Examples: j:MetadataAugmentation, exch:ChargeAugmentation
        #
        # Processing:
        # - Simple properties → flattened into parent node properties
        # - Complex children → direct containment to parent (skip augmentation layer)
        # - Never create a node for the augmentation itself
        if elem_qn.endswith('Augmentation'):
            if parent_info:
                parent_id, parent_label = parent_info

                # Process each child of the augmentation directly under parent
                for aug_child in elem:
                    aug_child_qn = qname_from_tag(aug_child.tag, xml_ns_map)

                    # Check if this child is a complex element that should become a node
                    if _is_complex_element(aug_child, xml_ns_map, struct_ns):
                        # Process as direct child of PARENT (not augmentation)
                        traverse(aug_child, parent_info=parent_info, path_stack=path_stack + [elem])
                    # If simple property, flatten into parent properties
                    elif aug_child.text and aug_child.text.strip() and len(list(aug_child)) == 0:
                        prop_name = aug_child_qn.replace(':', '_')
                        if parent_id in nodes:
                            nodes[parent_id][2][prop_name] = aug_child.text.strip()
                            nodes[parent_id][2][f"{prop_name}_isAugmentation"] = True
                    # If has nested structure, recursively flatten
                    elif len(list(aug_child)) > 0:
                        flattened = _recursively_flatten_element(
                            aug_child, xml_ns_map, obj_rules, assoc_by_qn, cmf_element_index, "", struct_ns
                        )
                        if parent_id in nodes and flattened:
                            for key, value in flattened.items():
                                nodes[parent_id][2][key] = value
                                if not key.endswith('_isAugmentation'):
                                    nodes[parent_id][2][f"{key}_isAugmentation"] = True

            # Never create node for augmentation - return early
            return

        # Handle Association elements (create intermediate nodes with hypergraph pattern)
        assoc_rule = assoc_by_qn.get(elem_qn)
        if assoc_rule:
            # Generate association node ID - use structures:id if present, otherwise synthetic
            sid = get_structures_attr(elem, "id", struct_ns)
            if sid:
                assoc_node_id = f"{file_prefix}_{sid}"
            else:
                # Generate synthetic ID based on element position
                parent_id = parent_info[0] if parent_info else "root"
                chain = [qname_from_tag(e.tag, xml_ns_map) for e in path_stack] + [elem_qn]
                ordinal_path = "/".join(chain)
                assoc_node_id = synth_id(parent_id, elem_qn, ordinal_path, file_prefix)

            # Create label for association node (normalize qname)
            assoc_label = elem_qn.replace(":", "_")

            # Extract properties from association element and flatten them
            assoc_props = {}
            aug_props = {}

            # Get role qnames to skip them during property extraction
            endpoints = assoc_rule.get("endpoints", [])
            role_qnames = {ep["role_qname"] for ep in endpoints}

            # Flatten all non-role children onto association node
            for child in elem:
                child_qn = qname_from_tag(child.tag, xml_ns_map)

                # Skip role elements (these become edges, not properties)
                if child_qn in role_qnames:
                    continue

                # Check if child is a selected object or association (becomes a node, not property)
                if child_qn in obj_rules or child_qn in assoc_by_qn:
                    # This will be processed recursively
                    continue

                # Flatten property
                flattened = _recursively_flatten_element(
                    child, xml_ns_map, obj_rules, assoc_by_qn, cmf_element_index, "", struct_ns
                )
                aug_props.update(flattened)

            # Add metadata
            assoc_props["qname"] = elem_qn
            assoc_props["_isAssociation"] = True
            assoc_props["_source_file"] = filename

            # Capture NIEM structures attributes as metadata
            if sid:
                assoc_props["structures_id"] = sid
            struct_uri = get_structures_attr(elem, "uri", struct_ns)
            if struct_uri:
                assoc_props["structures_uri"] = struct_uri
            struct_ref = get_structures_attr(elem, "ref", struct_ns)
            if struct_ref:
                assoc_props["structures_ref"] = struct_ref

            # Register association node in id_registry for reference resolution
            id_registry[assoc_node_id] = {
                "qname": elem_qn,
                "label": assoc_label,
                "element": elem
            }

            # Create association node (nodes is a dict, not a list)
            nodes[assoc_node_id] = [assoc_label, elem_qn, assoc_props, aug_props]

            # Create edges from association node to each endpoint
            for ep in endpoints:
                # Find ALL role elements with matching qname and extract their references
                # This handles cases like PersonUnionAssociation with multiple <nc:Person> elements
                endpoint_refs = []

                for ch in elem:
                    if qname_from_tag(ch.tag, xml_ns_map) == ep["role_qname"]:
                        endpoint_id = None
                        endpoint_elem = ch

                        # Check for reference (structures:ref)
                        endpoint_ref = get_structures_attr(ch, "ref", struct_ns)
                        if endpoint_ref:
                            endpoint_id = f"{file_prefix}_{endpoint_ref}"
                        else:
                            # Check for URI reference (structures:uri)
                            endpoint_uri = get_structures_attr(ch, "uri", struct_ns)
                            if endpoint_uri:
                                # Extract ID from URI - always use the fragment if present
                                # This ensures different URI formats pointing to same ID resolve to same node
                                if '#' in endpoint_uri:
                                    # Fragment reference: "#P1" or "http://example.com#P1" -> "P1"
                                    endpoint_id = f"{file_prefix}_{endpoint_uri.split('#')[-1]}"
                                else:
                                    # Full URI without fragment - use basename or full sanitized URI
                                    # Try to extract a meaningful ID from the URI path
                                    uri_parts = endpoint_uri.rstrip('/').split('/')
                                    if uri_parts:
                                        # Use last path segment as ID
                                        endpoint_id = f"{file_prefix}_{uri_parts[-1].replace(':', '_')}"
                                    else:
                                        # Fallback: sanitize full URI
                                        endpoint_id = f"{file_prefix}_{endpoint_uri.replace('/', '_').replace(':', '_')}"
                            else:
                                # Check for inline definition with structures:id
                                endpoint_sid = get_structures_attr(ch, "id", struct_ns)
                                if endpoint_sid:
                                    endpoint_id = f"{file_prefix}_{endpoint_sid}"

                        if endpoint_id:
                            endpoint_refs.append((endpoint_id, endpoint_elem))

                # Create edges for ALL matching role elements (handles multiple Person refs, etc.)
                for endpoint_id, endpoint_elem in endpoint_refs:
                    # Validate reference exists in ID registry (or will be created)
                    if endpoint_id not in id_registry:
                        # Check if this is an inline element with structures:id
                        if endpoint_elem is not None:
                            sid = get_structures_attr(endpoint_elem, "id", struct_ns)
                            if sid:
                                # Inline element with ID - register it now
                                id_registry[endpoint_id] = {
                                    "qname": qname_from_tag(endpoint_elem.tag, xml_ns_map),
                                    "label": ep["maps_to_label"],
                                    "element": endpoint_elem
                                }
                            else:
                                # Inline element without ID - will be processed recursively
                                # But track as pending in case it's not in the mapping
                                pending_refs.append((elem_qn, endpoint_id, f"Association {elem_qn} endpoint {ep['role_qname']}"))
                        else:
                            # Pure reference (ref/uri) that doesn't exist yet - track it
                            pending_refs.append((elem_qn, endpoint_id, f"Association {elem_qn} endpoint {ep['role_qname']}"))

                    # Create edge from association node to endpoint
                    # Relationship type: ASSOCIATED_WITH
                    rel_type = "ASSOCIATED_WITH"

                    # Edge properties include role metadata
                    edge_props = {
                        "role_qname": ep["role_qname"],
                        "direction": ep.get("direction", "")
                    }

                    # Get endpoint label - use None to let resolution logic find actual node label
                    # This handles NIEM substitution where role type (nc:Person) differs from actual type (j:CrashDriver)
                    endpoint_label = None

                    edges.append((assoc_node_id, assoc_label, endpoint_id, endpoint_label, rel_type, edge_props))

            # Recursively process children (for nested objects within association)
            for ch in elem:
                traverse(ch, (assoc_node_id, assoc_label), path_stack + [elem])
            return

        # Handle Object elements (nodes)
        obj_rule = obj_rules.get(elem_qn)
        node_id = None
        node_label = None
        props = {}

        # Check if element has structures:id (makes it a node regardless of mapping)
        sid = get_structures_attr(elem, "id", struct_ns)
        uri_ref = get_structures_attr(elem, "uri", struct_ns)
        ref = get_structures_attr(elem, "ref", struct_ns)
        is_nil = elem.attrib.get(f"{{{XSI_NS}}}nil") == "true"

        # Skip pure reference elements (ref or uri with nil) - they don't create nodes
        if (ref or uri_ref) and is_nil:
            # Just traverse children without creating any nodes
            for ch in elem:
                traverse(ch, parent_info, path_stack)
            return

        # Check if this is an augmentation element (never create nodes for augmentations)
        is_augmentation = elem_qn.endswith('Augmentation')

        # Determine if element should become a node based on mode
        should_create_node = False

        if mode == "mapping":
            # Mapping mode: Only create nodes for elements explicitly selected in designer
            # Skip augmentations even if they're in the mapping
            should_create_node = obj_rule is not None and not is_augmentation
        elif mode == "dynamic":
            # Dynamic mode: Create nodes for all complex elements EXCEPT augmentations
            should_create_node = _is_complex_element(elem, xml_ns_map, struct_ns) and not is_augmentation

        if should_create_node:
            # Generate label
            if obj_rule:
                # Use label from mapping
                node_label = obj_rule["label"]
            else:
                # Dynamic mode: generate label from qname
                node_label = elem_qn.replace(':', '_')

            # Generate node ID - use structures:id if present, otherwise structures:uri, otherwise synthetic
            if sid:
                node_id = f"{file_prefix}_{sid}"
            elif uri_ref:
                # Extract fragment for co-referencing: "#P01" -> "P01"
                entity_id = uri_ref.lstrip('#')
                node_id = f"{file_prefix}_{entity_id}"

                # Track URI entity for co-referencing
                if entity_id in uri_entity_registry:
                    # This entity already exists - create SAME_ENTITY edge
                    first_node_id = uri_entity_registry[entity_id]
                    edges.append((
                        node_id,
                        node_label,
                        first_node_id,
                        nodes[first_node_id][0],  # First node's label
                        "SAME_ENTITY",
                        {"uri": uri_ref, "source": "uri_co_reference"}
                    ))
                    logger.debug(f"URI co-reference: {node_id} --SAME_ENTITY--> {first_node_id} (via {uri_ref})")
                else:
                    # First occurrence of this URI
                    uri_entity_registry[entity_id] = node_id
            else:
                # Generate synthetic ID based on element position
                parent_id = parent_info[0] if parent_info else "root"
                chain = [qname_from_tag(e.tag, xml_ns_map) for e in path_stack] + [elem_qn]
                ordinal_path = "/".join(chain)
                node_id = synth_id(parent_id, elem_qn, ordinal_path, file_prefix)

            # Capture NIEM structures attributes as metadata
            if sid:
                props["structures_id"] = sid
            if uri_ref:
                props["structures_uri"] = uri_ref
            if ref:
                props["structures_ref"] = ref

            # Extract explicitly mapped scalar properties
            if obj_rule:
                setters = collect_scalar_setters(obj_rule, elem, xml_ns_map)
                for key, value in setters:
                    props[key] = value

            # Recursively flatten unselected children
            # Note: This may create some duplicate properties with different names
            # (e.g., "firstName" from scalar_props AND "nc_PersonName__nc_PersonGivenName" from flattening)
            # but ensures complete data capture. Last write wins for same property name.
            aug_props = {}
            for child in elem:
                child_qn = qname_from_tag(child.tag, xml_ns_map)

                # Check if this child is an augmentation element that should be flattened
                if child_qn in augmentation_index:
                    # This is an augmentation element - flatten all its properties into parent
                    aug_def = augmentation_index[child_qn]
                    for prop_def in aug_def['properties']:
                        prop_qname = prop_def['qname']
                        # Find child element matching this property
                        for aug_child in child:
                            aug_child_qn = qname_from_tag(aug_child.tag, xml_ns_map)
                            if aug_child_qn == prop_qname:
                                # Extract value (simple text)
                                if aug_child.text and aug_child.text.strip():
                                    # Flat naming: j:PersonAdultIndicator -> j_PersonAdultIndicator
                                    prop_name = prop_qname.replace(':', '_')
                                    props[prop_name] = aug_child.text.strip()
                                    props[f"{prop_name}_isAugmentation"] = True
                                break
                    # Don't create a node for augmentation element itself
                    continue

                # Check if child should become its own node
                if mode == "mapping":
                    child_is_node = (
                        child_qn in obj_rules or  # Explicitly selected in designer
                        child_qn in assoc_by_qn    # Associations (handled separately)
                    )
                elif mode == "dynamic":
                    child_is_node = (
                        _is_complex_element(child, xml_ns_map, struct_ns) or
                        child_qn in assoc_by_qn    # Associations (handled separately)
                    )
                else:
                    child_is_node = False

                if child_is_node:
                    # This child will be processed as a separate node in recursion
                    # Skip flattening - it will create a containment relationship instead
                    continue

                # Child is NOT a node - flatten it and all its descendants
                if child.text and child.text.strip() and len(list(child)) == 0:
                    # Simple text child - flatten directly
                    prop_name = child_qn.replace(':', '_')
                    is_aug = cmf_element_index and is_augmentation(child_qn, cmf_element_index)

                    if is_aug:
                        aug_props[prop_name] = child.text.strip()
                        aug_props[f"{prop_name}_isAugmentation"] = True
                    else:
                        props[prop_name] = child.text.strip()

                elif len(list(child)) > 0:
                    # Complex child with nested elements - recursively flatten
                    flattened = _recursively_flatten_element(
                        child, xml_ns_map, obj_rules, assoc_by_qn, cmf_element_index, path_prefix="", struct_ns=struct_ns
                    )

                    # Determine if this is augmentation data
                    is_aug = cmf_element_index and is_augmentation(child_qn, cmf_element_index)

                    for prop_path, prop_value in flattened.items():
                        if is_aug:
                            aug_props[prop_path] = prop_value
                            aug_props[f"{prop_path}_isAugmentation"] = True
                        else:
                            props[prop_path] = prop_value

            # Register node
            if node_id in nodes:
                # Keep existing label, but extend props (don't overwrite)
                nodes[node_id][2].update({k: v for k, v in props.items() if k not in nodes[node_id][2]})
                # Merge augmentation properties
                if aug_props:
                    nodes[node_id][3].update({k: v for k, v in aug_props.items() if k not in nodes[node_id][3]})
            else:
                nodes[node_id] = [node_label, elem_qn, props, aug_props]

            # Process dynamic reference attributes (nc:metadataRef, priv:privacyMetadataRef, etc.)
            # This handles IDREFS splitting and creates edges for custom reference attributes
            reference_edges = process_reference_attributes(
                elem=elem,
                node_id=node_id,
                node_label=node_label,
                file_prefix=file_prefix,
                ns_map=xml_ns_map,
                reference_registry=reference_registry,
                struct_ns=struct_ns
            )
            edges.extend(reference_edges)

            # Create containment edge
            if parent_info:
                p_id, p_label = parent_info
                # Look up actual parent label from nodes dict (handles co-referenced nodes)
                if p_id in nodes:
                    p_label = nodes[p_id][0]  # Use actual label from node
                rel = "HAS_" + re.sub(r'[^A-Za-z0-9]', '_', local_from_qname(elem_qn)).upper()
                contains.append((p_id, p_label, node_id, node_label, rel))

            # Create REFERS_TO edges for structures:ref and structures:uri
            target_id = None
            if ref:
                # structures:ref - direct reference to an ID
                target_id = f"{file_prefix}_{ref}"
                pending_refs.append((node_id, target_id, f"Object {elem_qn} structures:ref"))
                # Create REFERS_TO edge (target label will be resolved later)
                edges.append((node_id, node_label, target_id, None, "REFERS_TO", {}))
            elif uri_ref:
                # structures:uri - URI reference, extract fragment or basename
                if '#' in uri_ref:
                    target_id = f"{file_prefix}_{uri_ref.split('#')[-1]}"
                else:
                    # Use last path segment as ID
                    uri_parts = uri_ref.rstrip('/').split('/')
                    if uri_parts:
                        target_id = f"{file_prefix}_{uri_parts[-1].replace(':', '_')}"
                if target_id:
                    pending_refs.append((node_id, target_id, f"Object {elem_qn} structures:uri"))
                    # Create REFERS_TO edge (target label will be resolved later)
                    edges.append((node_id, node_label, target_id, None, "REFERS_TO", {}))

            parent_ctx = (node_id, node_label)
        else:
            # Element is NOT selected as a node - flatten it into parent if there is one
            parent_ctx = parent_info

            # Special handling for augmentations - process children directly under parent
            if is_augmentation and parent_info:
                parent_id, parent_label = parent_info

                # Process each child of the augmentation
                for aug_child in elem:
                    aug_child_qn = qname_from_tag(aug_child.tag, xml_ns_map)

                    # Check if this child is a complex element that should become a node
                    if _is_complex_element(aug_child, xml_ns_map, struct_ns):
                        # Process as direct child of PARENT (not augmentation)
                        traverse(aug_child, parent_info=parent_info, path_stack=path_stack + [elem])
                    # If simple property, flatten into parent properties
                    elif aug_child.text and aug_child.text.strip() and len(list(aug_child)) == 0:
                        prop_name = aug_child_qn.replace(':', '_')
                        if parent_id in nodes:
                            nodes[parent_id][2][prop_name] = aug_child.text.strip()
                            nodes[parent_id][2][f"{prop_name}_isAugmentation"] = True
                    # If has nested structure, recursively flatten
                    elif len(list(aug_child)) > 0:
                        flattened = _recursively_flatten_element(
                            aug_child, xml_ns_map, obj_rules, assoc_by_qn, cmf_element_index, "", struct_ns
                        )
                        if parent_id in nodes and flattened:
                            for key, value in flattened.items():
                                nodes[parent_id][2][key] = value
                                if not key.endswith('_isAugmentation'):
                                    nodes[parent_id][2][f"{key}_isAugmentation"] = True

            # If we have a parent node, flatten this element's data into it
            elif parent_info:
                parent_id, parent_label = parent_info

                # Recursively extract all properties from this unselected element
                flattened = _recursively_flatten_element(
                    elem, xml_ns_map, obj_rules, assoc_by_qn, cmf_element_index,
                    path_prefix=elem_qn,  # Use element qname as prefix
                    struct_ns=struct_ns
                )

                # Add flattened properties to parent node
                if parent_id in nodes and flattened:
                    # Determine if this is augmentation data
                    is_aug_data = cmf_element_index and is_augmentation(elem_qn, cmf_element_index)

                    if is_aug_data:
                        # Add to parent's augmentation properties
                        for prop_path, prop_value in flattened.items():
                            nodes[parent_id][3][prop_path] = prop_value
                            nodes[parent_id][3][f"{prop_path}_isAugmentation"] = True
                    else:
                        # Add to parent's regular properties
                        nodes[parent_id][2].update(flattened)

        # Handle reference edges from mapping.references
        if elem_qn in refs_by_owner:
            for rule in refs_by_owner[elem_qn]:
                # Search children with matching field_qname and @structures:ref OR @structures:id
                for ch in elem:
                    if qname_from_tag(ch.tag, xml_ns_map) == rule["field_qname"]:
                        # Check for structures:ref first (traditional NIEM pattern)
                        to_id = get_structures_attr(ch, "ref", struct_ns)
                        if not to_id:
                            # If no structures:ref, check for structures:id (direct child pattern)
                            to_id = get_structures_attr(ch, "id", struct_ns)

                        if to_id and node_id:
                            # Prefix referenced ID with file_prefix
                            to_id_prefixed = f"{file_prefix}_{to_id}"

                            # Validate reference exists in ID registry
                            if to_id_prefixed not in id_registry:
                                pending_refs.append((elem_qn, to_id_prefixed, f"Reference from {elem_qn} via {rule['field_qname']}"))

                            # Use the node_id that was assigned to this element
                            edges.append((
                                node_id, rule["owner_object"].replace(":", "_"),
                                to_id_prefixed, rule["target_label"],
                                rule["rel_type"], {}
                            ))

        # Recurse to children
        path_stack.append(elem)
        for ch in elem:
            traverse(ch, parent_ctx, path_stack)
        path_stack.pop()

    # TWO-PASS TRAVERSAL for forward reference resolution
    # Pass 1: Collect all IDs to enable forward/backward reference resolution
    collect_ids_pass1(root)

    # Report ID collisions if any were detected
    if id_collisions:
        logger.warning(f"Found {len(id_collisions)} ID collisions in {filename}")
        for collision in id_collisions:
            logger.warning(
                f"  - Duplicate ID '{collision['id']}': "
                f"first in {collision['first_qname']}, "
                f"again in {collision['second_qname']}"
            )

    # Pass 2: Process root element and create graph structure (always)
    traverse(root, None, [])

    # HANDLE UNRESOLVED REFERENCES
    # After traversal, check for any references that weren't found in the ID registry
    # These indicate potential data quality issues or forward/external references
    unresolved_refs = []
    for source_qn, target_id, context in pending_refs:
        if target_id not in nodes:
            # Target ID doesn't exist - could be forward ref or missing element
            # Extract the element qname and label from context (format: "Association X endpoint Y")
            # Parse context to get the role qname
            role_qname = None
            label = None

            # Context format: "Association j:PersonChargeAssociation endpoint nc:Person"
            if "endpoint" in context:
                parts = context.split("endpoint")
                if len(parts) > 1:
                    role_qname = parts[1].strip()
                    label = role_qname.replace(":", "_")

            # Fallback if parsing failed
            if not label:
                label = "UnresolvedReference"
                role_qname = "unresolved:Reference"

            unresolved_refs.append({
                'target_id': target_id,
                'context': context,
                'source': source_qn,
                'expected_type': role_qname
            })

            # Create placeholder node with the correct type label
            # This allows the graph to be created while flagging data quality issues
            nodes[target_id] = [
                label,
                role_qname,
                {
                    '_unresolved': True,
                    '_error': f'Referenced ID not found in document',
                    '_context': context,
                    '_raw_id': target_id
                },
                {}
            ]

    # Log unresolved references for reporting (can be added to return value later)
    # For now, add as comment in Cypher output
    if unresolved_refs:
        logger.warning(f"Found {len(unresolved_refs)} unresolved references in {filename}")
        for ref in unresolved_refs:
            logger.warning(f"  - {ref['context']}: {ref['target_id']}")

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
        setbits = [f"n.qname='{qn}'", f"n.sourceDoc='{filename}'", f"n.ingestDate='{ingest_timestamp}'"]
        # Add isolation properties for graph separation
        if upload_id:
            setbits.append(f"n._upload_id='{upload_id}'")
        if schema_id:
            setbits.append(f"n._schema_id='{schema_id}'")

        # Add core mapped properties
        for key, value in sorted(props.items()):
            # Escape property names with special characters (dots, hyphens, etc.) using backticks
            # Only alphanumeric and underscore are safe without backticks in Cypher
            prop_key = f"`{key}`" if not re.match(CYPHER_SAFE_PROPERTY_NAME, key) else key

            if isinstance(value, bool):
                # Write boolean flags directly (for _isAssociation and other boolean properties)
                setbits.append(f"n.{prop_key}={str(value).lower()}")
            else:
                # Escape backslashes first, then single quotes
                escaped_value = str(value).replace("\\", "\\\\").replace("'", "\\'")
                setbits.append(f"n.{prop_key}='{escaped_value}'")

        # Add augmentation properties
        for key, value in sorted(aug_props.items()):
            # Escape property names with special characters (dots, hyphens, etc.) using backticks
            # Only alphanumeric and underscore are safe without backticks in Cypher
            prop_key = f"`{key}`" if not re.match(CYPHER_SAFE_PROPERTY_NAME, key) else key
            if isinstance(value, bool):
                # Write boolean flags directly (for _isAugmentation metadata)
                setbits.append(f"n.{prop_key}={str(value).lower()}")
            elif isinstance(value, list):
                # Use Neo4j native array syntax
                array_items = []
                for item in value:
                    if isinstance(item, str):
                        escaped_item = item.replace("\\", "\\\\").replace("'", "\\'")
                        array_items.append(f"'{escaped_item}'")
                    elif isinstance(item, (int, float, bool)):
                        array_items.append(str(item).lower() if isinstance(item, bool) else str(item))
                    else:
                        escaped_item = str(item).replace("\\", "\\\\").replace("'", "\\'")
                        array_items.append(f"'{escaped_item}'")
                setbits.append(f"n.{prop_key}=[{', '.join(array_items)}]")
            else:
                # Escape backslashes first, then single quotes
                escaped_value = str(value).replace("\\", "\\\\").replace("'", "\\'")
                setbits.append(f"n.{prop_key}='{escaped_value}'")

        lines.append("  ON CREATE SET " + ", ".join(setbits) + ";")

    # Build match properties for graph isolation
    def build_match_props(node_id):
        props = f"id:'{node_id}'"
        if upload_id:
            props += f", _upload_id:'{upload_id}'"
        if filename:
            props += f", sourceDoc:'{filename}'"
        return props

    # MERGE containment edges
    for pid, plabel, cid, clabel, rel in contains:
        parent_match = build_match_props(pid)
        child_match = build_match_props(cid)
        lines.append(f"MATCH (p:`{plabel}` {{{parent_match}}}), (c:`{clabel}` {{{child_match}}}) MERGE (p)-[:`{rel}`]->(c);")

    # MERGE reference/association edges
    for fid, flabel, tid, tlabel, rel, rprops in edges:
        from_match = build_match_props(fid)
        to_match = build_match_props(tid)

        # Build relationship properties if any
        if rprops:
            # Build property setters for rich edges
            prop_setters = []
            for key, value in sorted(rprops.items()):
                # Escape property names with special characters (dots, hyphens, etc.) using backticks
                # Only alphanumeric and underscore are safe without backticks in Cypher
                prop_key = f"`{key}`" if not re.match(CYPHER_SAFE_PROPERTY_NAME, key) else key
                if isinstance(value, list):
                    # Use Neo4j native array syntax
                    array_items = []
                    for item in value:
                        if isinstance(item, str):
                            escaped_item = item.replace("\\", "\\\\").replace("'", "\\'")
                            array_items.append(f"'{escaped_item}'")
                        elif isinstance(item, (int, float, bool)):
                            array_items.append(str(item).lower() if isinstance(item, bool) else str(item))
                        else:
                            escaped_item = str(item).replace("\\", "\\\\").replace("'", "\\'")
                            array_items.append(f"'{escaped_item}'")
                    prop_setters.append(f"r.{prop_key}=[{', '.join(array_items)}]")
                else:
                    # Escape backslashes first, then single quotes
                    escaped_value = str(value).replace("\\", "\\\\").replace("'", "\\'")
                    prop_setters.append(f"r.{prop_key}='{escaped_value}'")

            # MERGE with properties on relationship (rich edge pattern)
            props_clause = ", ".join(prop_setters)
            lines.append(
                f"MATCH (a:`{flabel}` {{{from_match}}}), (b:`{tlabel}` {{{to_match}}}) "
                f"MERGE (a)-[r:`{rel}`]->(b) ON CREATE SET {props_clause};"
            )
        else:
            # Simple edge without properties
            lines.append(f"MATCH (a:`{flabel}` {{{from_match}}}), (b:`{tlabel}` {{{to_match}}}) MERGE (a)-[:`{rel}`]->(b);")

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
