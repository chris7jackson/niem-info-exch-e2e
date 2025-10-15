#!/usr/bin/env python3
"""NIEM JSON to Cypher converter service.

This module converts NIEM JSON (JSON-LD compliant) documents to Neo4j Cypher statements using
a mapping dictionary. NIEM JSON uses JSON-LD features with NIEM-specific conventions:

- @context: Maps namespace prefixes to URIs (e.g., "nc" → NIEM Core namespace)
- @id: Identifies objects and creates references (replaces XML structures:id/structures:ref)
- @type: Specifies object type (optional)
- Property names use namespace prefixes: "nc:PersonFullName", "j:CrashDriver"
- References are objects containing only @id: {"@id": "P1"}
- @graph: Optional container for multiple top-level objects

Example NIEM JSON:
{
  "@context": {"nc": "http://release.niem.gov/niem/niem-core/5.0/"},
  "nc:Person": {
    "@id": "P1",
    "nc:PersonName": {
      "nc:PersonGivenName": "John"
    }
  }
}
"""
import hashlib
import json
import logging
import time
from typing import Any

logger = logging.getLogger(__name__)


def load_mapping_from_dict(mapping_dict: dict[str, Any]) -> tuple[
    dict[str, Any], dict[str, Any], list[dict[str, Any]], list[dict[str, Any]], dict[str, str]
]:
    """Load mapping from dictionary.

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


def resolve_qname(prefixed_name: str, context: dict[str, Any]) -> str:
    """Resolve prefixed name to full URI using @context.

    Args:
        prefixed_name: Prefixed name like "nc:Person"
        context: JSON-LD @context mapping

    Returns:
        Full URI or original name if no prefix
    """
    if ":" in prefixed_name:
        prefix, local = prefixed_name.split(":", 1)
        namespace = context.get(prefix, "")
        if namespace:
            return f"{prefix}:{local}"  # Keep prefix format for mapping
    return prefixed_name


def is_reference(value: Any) -> bool:
    """Check if value is a NIEM JSON reference.

    NIEM JSON references are objects containing only @id, similar to XML structures:ref.
    Example: {"@id": "P1"}

    Args:
        value: Value to check

    Returns:
        True if value is a reference object
    """
    return isinstance(value, dict) and "@id" in value and len(value) == 1


def local_from_qname(qn: str) -> str:
    """Extract local name from qualified name.

    Args:
        qn: Qualified name like "nc:Person"

    Returns:
        Local name like "Person"
    """
    if ":" in qn:
        return qn.split(":", 1)[1]
    return qn


def build_refs_index(references: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """Build index of references by owner QName.

    Args:
        references: List of reference definitions

    Returns:
        Dictionary mapping owner QName to list of reference definitions
    """
    refs_by_owner = {}
    for ref in references:
        owner_qn = ref.get("owner_qname")
        if owner_qn:
            refs_by_owner.setdefault(owner_qn, []).append(ref)
    return refs_by_owner


def build_assoc_index(associations: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Build index of associations by QName.

    Args:
        associations: List of association definitions

    Returns:
        Dictionary mapping association QName to definition
    """
    return {assoc["qname"]: assoc for assoc in associations}


def extract_properties(
    obj: dict[str, Any],
    obj_rule: dict[str, Any],
    context: dict[str, Any]
) -> list[tuple[str, str]]:
    """Extract properties from JSON-LD object based on mapping rules.

    Args:
        obj: JSON-LD object
        obj_rule: Mapping rule for this object type
        context: JSON-LD @context

    Returns:
        List of (property_name, value) tuples
    """
    setters = []
    properties = obj_rule.get("properties", [])

    for prop_def in properties:
        key = prop_def["neo4j_key"]
        json_path = prop_def.get("json_path") or prop_def.get("xml_path", "")

        value = None

        if "/" in json_path:
            # Nested path like "nc:PersonName/nc:PersonGivenName"
            parts = json_path.split("/")
            current = obj
            for part in parts:
                if isinstance(current, dict):
                    current = current.get(part)
                    if current is None:
                        break
                else:
                    current = None
                    break
            if current and isinstance(current, str):
                value = current
        else:
            # Direct property
            if json_path.startswith("@"):
                # JSON-LD keyword
                value = obj.get(json_path)
            else:
                # Regular property
                value = obj.get(json_path)

        if value is not None:
            # Escape single quotes for Cypher
            escaped_value = str(value).replace("'", "\\'")
            setters.append((key, escaped_value))

    return setters


def generate_for_json_content(
    json_content: str,
    mapping_dict: dict[str, Any],
    filename: str = "memory",
    cmf_element_index: set = None
) -> tuple[str, dict[str, Any], list[tuple], list[tuple]]:
    """Generate Cypher statements from NIEM JSON content and mapping dictionary.

    NIEM JSON uses JSON-LD features (@context, @id, @type) with NIEM conventions.
    This function applies the same mapping rules as the XML converter to maintain
    consistent graph structures between XML and JSON representations.

    Args:
        json_content: NIEM JSON content as string
        mapping_dict: Mapping dictionary (same as used for XML)
        filename: Source filename for provenance
        cmf_element_index: Set of known CMF element QNames

    Returns:
        Tuple of (cypher_statements, nodes_dict, contains_list, edges_list)
    """
    # Parse NIEM JSON
    data = json.loads(json_content)

    # Extract context
    context = data.get("@context", {})

    # Load mapping
    _, obj_rules, _, _, _ = load_mapping_from_dict(mapping_dict)

    # Extract CMF element index from mapping metadata if not provided
    if cmf_element_index is None:
        metadata = mapping_dict.get("metadata", {})
        cmf_elements_list = metadata.get("cmf_element_index", [])
        cmf_element_index = set(cmf_elements_list) if cmf_elements_list else set()

    # Generate file-specific prefix for node IDs
    file_prefix = hashlib.sha1(f"{filename}_{time.time()}".encode()).hexdigest()[:8]

    nodes = {}  # id -> (label, qname, props_dict, aug_props_dict)
    edges = []  # (from_id, from_label, to_id, to_label, rel_type, rel_props)
    contains = []  # (parent_id, parent_label, child_id, child_label, HAS_REL)

    # Get objects from @graph or treat data as single object
    has_content = "@type" in data or any(k for k in data.keys() if not k.startswith("@"))
    objects = data.get("@graph", [data] if has_content else [])

    # Process each object
    object_counter = 0

    def process_jsonld_object(
        obj: dict[str, Any], parent_id: str = None, parent_label: str = None, property_name: str = None
    ):
        """Process a JSON-LD object and generate nodes/relationships."""
        nonlocal object_counter

        # Skip if not a dict
        if not isinstance(obj, dict):
            return None

        # Extract @id or generate one
        obj_id = obj.get("@id")
        if not obj_id:
            object_counter += 1
            obj_id = f"{file_prefix}_obj{object_counter}"

        # Extract @type to determine object type
        obj_type = obj.get("@type")

        # Determine QName - prefer @type, fall back to property name
        qname = obj_type if obj_type else property_name

        # Skip if already processed
        if obj_id in nodes:
            # Create reference edge if this is a nested occurrence
            if parent_id and property_name:
                edges.append((parent_id, parent_label, obj_id, qname, property_name, {}))
            return obj_id

        # Find matching object rule
        obj_rule = obj_rules.get(qname) if qname else None

        if obj_rule:
            # Extract label and properties
            label = obj_rule.get("label", local_from_qname(qname))
            props = extract_properties(obj, obj_rule, context)
            props_dict = dict(props)

            # Add source provenance
            props_dict["_source_file"] = filename

            # Create node
            nodes[obj_id] = (label, qname, props_dict, {})

            # Create containment edge if nested
            if parent_id:
                rel_type = (
                    f"HAS_{local_from_qname(property_name)}"
                    if property_name else 'HAS_CHILD'
                )
                contains.append((parent_id, parent_label, obj_id, label, rel_type))

            # Process nested properties
            for key, value in obj.items():
                if key.startswith("@"):
                    continue  # Skip JSON-LD keywords

                if is_reference(value):
                    # Reference edge
                    target_id = value["@id"]
                    edges.append((obj_id, label, target_id, None, key, {}))

                elif isinstance(value, dict):
                    # Nested object (containment edge created automatically)
                    process_jsonld_object(value, obj_id, label, key)

                elif isinstance(value, list):
                    # Array of objects or references
                    for item in value:
                        if isinstance(item, dict):
                            if is_reference(item):
                                target_id = item["@id"]
                                edges.append((obj_id, label, target_id, None, key, {}))
                            else:
                                process_jsonld_object(item, obj_id, label, key)

            return obj_id
        else:
            # No mapping rule - create generic node
            label = local_from_qname(qname) if qname else "Object"
            props_dict = {"_source_file": filename}

            # Extract simple string properties
            for key, value in obj.items():
                if key.startswith("@"):
                    continue
                if isinstance(value, (str, int, float, bool)):
                    safe_key = key.replace(":", "_")
                    props_dict[safe_key] = str(value).replace("'", "\\'")

            nodes[obj_id] = (label, qname or "Object", props_dict, {})

            if parent_id:
                rel_type = (
                    f"HAS_{local_from_qname(property_name)}"
                    if property_name else 'HAS_CHILD'
                )
                contains.append((parent_id, parent_label, obj_id, label, rel_type))

            # Process nested
            for key, value in obj.items():
                if key.startswith("@"):
                    continue
                if is_reference(value):
                    edges.append((obj_id, label, value["@id"], None, key, {}))
                elif isinstance(value, dict):
                    process_jsonld_object(value, obj_id, label, key)
                elif isinstance(value, list):
                    for item in value:
                        if isinstance(item, dict):
                            if is_reference(item):
                                edges.append((obj_id, label, item["@id"], None, key, {}))
                            else:
                                process_jsonld_object(item, obj_id, label, key)

            return obj_id

    # Process all top-level objects
    for obj in objects:
        if isinstance(obj, dict):
            process_jsonld_object(obj)

    # Generate Cypher statements
    cypher_statements = generate_cypher_from_structures(nodes, edges, contains)

    return cypher_statements, nodes, contains, edges


def generate_cypher_from_structures(
    nodes: dict[str, tuple],
    edges: list[tuple],
    contains: list[tuple]
) -> str:
    """Generate Cypher statements from node and edge structures.

    Args:
        nodes: Dictionary of node structures
        edges: List of edge tuples
        contains: List of containment edge tuples

    Returns:
        Cypher statements as string
    """
    cypher_lines = []

    # Generate MERGE statements for nodes
    for node_id, (label, qname, props, aug_props) in nodes.items():
        # Build properties string - include qname for display consistency with XML
        props_parts = []
        all_props = {**props, **aug_props, "qname": qname}  # Add qname to properties
        for key, value in all_props.items():
            props_parts.append(f"{key}: '{value}'")

        props_str = ", ".join(props_parts)
        cypher_lines.append(f"MERGE (n:{label} {{id: '{node_id}', {props_str}}});")

    # Generate MERGE statements for containment relationships
    for parent_id, parent_label, child_id, child_label, rel_type in contains:
        cypher_lines.append(
            f"MATCH (parent:{parent_label} {{id: '{parent_id}'}}), (child:{child_label} {{id: '{child_id}'}}) "
            f"MERGE (parent)-[:{rel_type}]->(child);"
        )

    # Generate MERGE statements for reference/association edges
    for from_id, from_label, to_id, to_label, rel_type, _ in edges:
        # Clean relationship type
        clean_rel_type = rel_type.replace(":", "_").upper()

        if to_label:
            cypher_lines.append(
                f"MATCH (from:{from_label} {{id: '{from_id}'}}), (to:{to_label} {{id: '{to_id}'}}) "
                f"MERGE (from)-[:{clean_rel_type}]->(to);"
            )
        else:
            # Find target by ID only
            cypher_lines.append(
                f"MATCH (from:{from_label} {{id: '{from_id}'}}), (to {{id: '{to_id}'}}) "
                f"MERGE (from)-[:{clean_rel_type}]->(to);"
            )

    return "\n".join(cypher_lines)
