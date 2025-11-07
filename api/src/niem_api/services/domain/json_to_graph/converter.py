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
) -> list[tuple[str, Any]]:
    """Extract properties from JSON-LD object based on mapping rules.

    Args:
        obj: JSON-LD object
        obj_rule: Mapping rule for this object type
        context: JSON-LD @context

    Returns:
        List of (property_name, value) tuples (value can be string or list)
    """
    setters = []
    scalar_props = obj_rule.get("scalar_props", [])

    for prop_def in scalar_props:
        # Use correct field names from mapping structure
        path = prop_def.get("path", "")
        key = prop_def.get("neo4j_property") or prop_def.get("prop", path.replace(":", "_").replace("/", "__"))

        value = None

        if "/" in path:
            # Nested path like "nc:PersonName/nc:PersonGivenName"
            parts = path.split("/")
            current = obj
            for part in parts:
                if isinstance(current, dict):
                    current = current.get(part)
                    if current is None:
                        break
                elif isinstance(current, list):
                    # For arrays, try to extract from all items
                    results = []
                    for item in current:
                        if isinstance(item, dict):
                            val = item.get(part)
                            if val is not None:
                                results.append(val)
                    current = results if results else None
                    break
                else:
                    current = None
                    break

            if current is not None:
                value = current
        else:
            # Direct property
            if path.startswith("@"):
                # JSON-LD keyword
                value = obj.get(path)
            else:
                # Regular property
                value = obj.get(path)

        if value is not None:
            # Store raw value (string or list) - handle arrays natively
            setters.append((key, value))

    return setters


def _recursively_flatten_json_object(
    obj: dict[str, Any],
    obj_rules: dict[str, Any],
    assoc_by_qn: dict[str, Any],
    path_prefix: str = ""
) -> dict[str, Any]:
    """Recursively flatten an unselected JSON object and all its descendants.

    Args:
        obj: JSON object to flatten
        obj_rules: Object rules from mapping
        assoc_by_qn: Association rules index
        path_prefix: Prefix for property paths

    Returns:
        Dictionary of flattened properties with hierarchical names
    """
    flattened = {}

    for key, value in obj.items():
        # Skip JSON-LD keywords
        if key.startswith("@"):
            continue

        # Build property path with double underscore delimiter for hierarchy
        # Single underscore for namespace colons, double underscore for nesting
        key_normalized = key.replace(":", "_")
        prop_path = f"{path_prefix}__{key_normalized}" if path_prefix else key_normalized

        if isinstance(value, (str, int, float, bool)):
            # Simple value - add directly
            flattened[prop_path] = value

        elif isinstance(value, list):
            # Handle arrays
            simple_values = []
            for item in value:
                if isinstance(item, (str, int, float, bool)):
                    simple_values.append(item)
                elif isinstance(item, dict):
                    # Check if this dict should be a node
                    item_type = item.get("@type") or key
                    if item_type not in obj_rules and item_type not in assoc_by_qn:
                        # Recursively flatten nested object
                        nested_props = _recursively_flatten_json_object(
                            item, obj_rules, assoc_by_qn, prop_path
                        )
                        flattened.update(nested_props)
            if simple_values:
                flattened[prop_path] = simple_values

        elif isinstance(value, dict):
            # Check if this is a reference
            if is_reference(value):
                # Store reference ID
                flattened[f"{prop_path}_ref"] = value["@id"]
            else:
                # Check if nested object should be a node
                nested_type = value.get("@type") or key
                if nested_type not in obj_rules and nested_type not in assoc_by_qn:
                    # Recursively flatten nested object
                    nested_props = _recursively_flatten_json_object(
                        value, obj_rules, assoc_by_qn, prop_path
                    )
                    flattened.update(nested_props)

    return flattened


def _is_complex_json_element(obj: dict[str, Any]) -> bool:
    """Determine if JSON object is complex (should become a node in dynamic mode).

    Complex objects have:
    1. @id attribute (explicitly identifiable), OR
    2. Nested object properties (not just simple values), OR
    3. Multiple properties (beyond @type and simple text)

    Simple objects with only text values → flattened as properties

    Args:
        obj: JSON object to check

    Returns:
        True if object should become a node
    """
    if not isinstance(obj, dict):
        return False

    # Has @id? → Complex (explicitly identifiable)
    if "@id" in obj:
        return True

    # Count non-metadata properties
    non_metadata_keys = [k for k in obj.keys() if not k.startswith("@")]

    # No properties beyond metadata → Not complex
    if len(non_metadata_keys) == 0:
        return False

    # Check if has nested objects or arrays
    for key in non_metadata_keys:
        value = obj[key]
        if isinstance(value, dict):
            # Nested object (not just a reference)
            if not is_reference(value):
                return True
        elif isinstance(value, list):
            # Array property
            return True

    # Multiple simple properties → Complex
    if len(non_metadata_keys) > 1:
        return True

    # Single simple property → Not complex (will be flattened)
    return False


def generate_for_json_content(
    json_content: str,
    mapping_dict: dict[str, Any],
    filename: str = "memory",
    upload_id: str = None,
    schema_id: str = None,
    cmf_element_index: set = None,
    mode: str = "dynamic"
) -> tuple[str, dict[str, Any], list[tuple], list[tuple]]:
    """Generate Cypher statements from NIEM JSON content and mapping dictionary.

    NIEM JSON uses JSON-LD features (@context, @id, @type) with NIEM conventions.
    This function applies the same mapping rules as the XML converter to maintain
    consistent graph structures between XML and JSON representations.

    Args:
        json_content: NIEM JSON content as string
        mapping_dict: Mapping dictionary (same as used for XML)
        filename: Source filename for provenance
        upload_id: Unique identifier for this upload batch (for graph isolation)
        schema_id: Schema identifier (for graph isolation)
        cmf_element_index: Set of known CMF element QNames
        mode: Converter mode - "mapping" (use selections) or "dynamic" (all complex elements)

    Returns:
        Tuple of (cypher_statements, nodes_dict, contains_list, edges_list)
    """
    # Parse NIEM JSON
    data = json.loads(json_content)

    # Extract context
    context = data.get("@context", {})

    # Load mapping
    _, obj_rules, associations, references, _ = load_mapping_from_dict(mapping_dict)

    # Build association index for quick lookup
    assoc_by_qn = build_assoc_index(associations)

    # Extract CMF element index from mapping metadata if not provided
    if cmf_element_index is None:
        metadata = mapping_dict.get("metadata", {})
        cmf_elements_list = metadata.get("cmf_element_index", [])
        cmf_element_index = set(cmf_elements_list) if cmf_elements_list else set()

    # In dynamic mode, disable augmentation detection (all properties are standard)
    if mode == "dynamic":
        cmf_element_index = set()
        logger.info("Dynamic mode: Augmentation detection disabled")

    # Generate file-specific prefix for node IDs
    # SHA1 used for ID generation only, not cryptographic security
    file_prefix = hashlib.sha1(f"{filename}_{time.time()}".encode(), usedforsecurity=False).hexdigest()[:8]

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

        # Extract @id (if present)
        obj_id = obj.get("@id")
        has_id = obj_id is not None

        # Extract @type to determine object type
        obj_type = obj.get("@type")

        # Determine QName - prefer @type, fall back to property name
        qname = obj_type if obj_type else property_name

        # Check if this is an association (process before checking for object rule)
        assoc_rule = assoc_by_qn.get(qname) if qname else None

        if assoc_rule:
            # Handle Association objects (create intermediate nodes with hypergraph pattern)
            # Generate association node ID - use @id if present, otherwise synthetic
            if not obj_id:
                object_counter += 1
                obj_id = f"{file_prefix}_obj{object_counter}"

            # Skip if already processed
            if obj_id in nodes:
                return obj_id

            # Create label for association node (normalize qname)
            assoc_label = qname.replace(":", "_")

            # Extract properties from association object and flatten them
            assoc_props = {}
            aug_props = {}

            # Get role qnames to skip them during property extraction
            endpoints = assoc_rule.get("endpoints", [])
            role_qnames = {ep["role_qname"] for ep in endpoints}

            # Flatten all non-role children onto association node
            for key, value in obj.items():
                # Skip JSON-LD keywords
                if key.startswith("@"):
                    continue

                # Skip role elements (these become edges, not properties)
                if key in role_qnames:
                    continue

                # Check if value is a selected object or association (becomes a node, not property)
                value_qname = None
                if isinstance(value, dict):
                    value_qname = value.get("@type") or key
                if value_qname and (value_qname in obj_rules or value_qname in assoc_by_qn):
                    # This will be processed recursively
                    continue

                # Flatten property
                if isinstance(value, dict) and not is_reference(value):
                    prefix = key.replace(":", "_")
                    flattened = _recursively_flatten_json_object(value, obj_rules, assoc_by_qn, prefix)
                    aug_props.update(flattened)
                elif isinstance(value, (str, int, float, bool)):
                    prop_key = key.replace(":", "_")
                    aug_props[prop_key] = value
                elif isinstance(value, list):
                    prop_key = key.replace(":", "_")
                    aug_props[prop_key] = value

            # Add metadata
            assoc_props["qname"] = qname
            assoc_props["_isAssociation"] = True
            assoc_props["_source_file"] = filename

            # Capture NIEM structures attributes as metadata
            if obj_id and has_id:
                assoc_props["structures_id"] = obj_id

            # Check for structures:uri in the object (support multiple prefix variants)
            struct_uri = obj.get("structures:uri") or obj.get("s:uri")
            if struct_uri:
                assoc_props["structures_uri"] = struct_uri

            # Check for structures:ref in the object (though in JSON-LD this would be an @id reference)
            # Support multiple prefix variants (structures:, s:)
            struct_ref = obj.get("structures:ref") or obj.get("s:ref")
            if struct_ref:
                assoc_props["structures_ref"] = struct_ref

            # Create association node
            nodes[obj_id] = (assoc_label, qname, assoc_props, aug_props)

            # Create edges from association node to each endpoint
            for ep in endpoints:
                # Find the role property and extract its @id reference
                endpoint_ref = None
                role_value = obj.get(ep["role_qname"])

                if role_value:
                    if is_reference(role_value):
                        # Direct reference: {"@id": "P1"}
                        endpoint_ref = role_value["@id"]
                    elif isinstance(role_value, dict) and role_value.get("@id"):
                        # Nested object with @id
                        endpoint_ref = role_value["@id"]
                    elif isinstance(role_value, list) and len(role_value) > 0:
                        # Array of references - take first
                        first_item = role_value[0]
                        if isinstance(first_item, dict) and first_item.get("@id"):
                            endpoint_ref = first_item["@id"]

                if endpoint_ref:
                    # Create edge from association node to endpoint
                    # Relationship type: HAS_{role_local_name}
                    role_local = ep["role_qname"].split(":")[-1].upper()
                    rel_type = f"HAS_{role_local}"

                    # Edge properties include role metadata
                    edge_props = {
                        "role_qname": ep["role_qname"],
                        "direction": ep.get("direction", "")
                    }

                    # Get endpoint label from mapping
                    endpoint_label = ep["maps_to_label"]

                    edges.append((obj_id, assoc_label, endpoint_ref, endpoint_label, rel_type, edge_props))

            # Create REFERS_TO edges for structures:ref and structures:uri on the association itself
            # Note: struct_ref and struct_uri already checked for both prefixes above
            if struct_ref:
                # structures:ref - direct reference to an ID
                edges.append((obj_id, assoc_label, struct_ref, None, "REFERS_TO", {}))
            elif struct_uri:
                # structures:uri - resolve to target ID
                target_ref = None
                if '#' in struct_uri:
                    target_ref = struct_uri.split('#')[-1]
                else:
                    # Use last path segment as ID
                    uri_parts = struct_uri.rstrip('/').split('/')
                    if uri_parts:
                        target_ref = uri_parts[-1].replace(':', '_')
                if target_ref:
                    edges.append((obj_id, assoc_label, target_ref, None, "REFERS_TO", {}))

            # Recursively process children (for nested objects within association)
            for key, value in obj.items():
                if key.startswith("@") or key in role_qnames:
                    continue
                if isinstance(value, dict) and not is_reference(value):
                    process_jsonld_object(value, obj_id, assoc_label, key)
                elif isinstance(value, list):
                    for item in value:
                        if isinstance(item, dict) and not is_reference(item):
                            process_jsonld_object(item, obj_id, assoc_label, key)

            return obj_id

        # Find matching object rule
        obj_rule = obj_rules.get(qname) if qname else None

        # Determine if object should become a node based on mode
        should_create_node = False

        if mode == "mapping":
            # Mapping mode: Only create nodes for elements explicitly selected in designer
            should_create_node = obj_rule is not None
        elif mode == "dynamic":
            # Dynamic mode: Create nodes for all complex objects
            should_create_node = _is_complex_json_element(obj)

        if not should_create_node:
            # Flatten properties onto parent node (if parent exists)
            if parent_id and parent_id in nodes:
                parent_node = nodes[parent_id]
                parent_props = parent_node[2]  # props_dict is at index 2

                # Recursively flatten all properties from this unselected object
                prefix = property_name.replace(":", "_") if property_name else ""
                flattened = _recursively_flatten_json_object(obj, obj_rules, assoc_by_qn, prefix)
                parent_props.update(flattened)
            else:
                # Process children even if no parent to create nodes for
                for key, value in obj.items():
                    if key.startswith("@"):
                        continue
                    if isinstance(value, dict):
                        process_jsonld_object(value, parent_id, parent_label, key)
                    elif isinstance(value, list):
                        for item in value:
                            if isinstance(item, dict):
                                process_jsonld_object(item, parent_id, parent_label, key)

            # Don't create a node, return None
            return None

        # Generate ID only if should create node but doesn't have one
        if not obj_id:
            object_counter += 1
            obj_id = f"{file_prefix}_obj{object_counter}"

        # Skip if already processed
        if obj_id in nodes:
            # Create reference edge if this is a nested occurrence
            if parent_id and property_name:
                edges.append((parent_id, parent_label, obj_id, qname, property_name, {}))
            return obj_id

        # Generate label and properties
        if obj_rule:
            # Mapping mode: Use label from mapping
            label = obj_rule.get("label", local_from_qname(qname))
            props = extract_properties(obj, obj_rule, context)
            props_dict = dict(props)
        else:
            # Dynamic mode: Generate label from qname
            label = qname.replace(":", "_") if qname else "Unknown"
            props_dict = {}

        # Add source provenance and isolation properties
        props_dict["_source_file"] = filename
        if upload_id:
            props_dict["_upload_id"] = upload_id
        if schema_id:
            props_dict["_schema_id"] = schema_id

        # Capture NIEM structures attributes as metadata
        if obj_id and has_id:
            props_dict["structures_id"] = obj_id

        # Check for structures:uri in the object (support multiple prefix variants)
        struct_uri = obj.get("structures:uri") or obj.get("s:uri")
        if struct_uri:
            props_dict["structures_uri"] = struct_uri

        # Check for structures:ref in the object (support multiple prefix variants)
        struct_ref = obj.get("structures:ref") or obj.get("s:ref")
        if struct_ref:
            props_dict["structures_ref"] = struct_ref

        # Create node
        nodes[obj_id] = (label, qname, props_dict, {})

        # Create containment edge if nested
        if parent_id:
            rel_type = (
                f"HAS_{local_from_qname(property_name)}"
                if property_name else 'HAS_CHILD'
            )
            contains.append((parent_id, parent_label, obj_id, label, rel_type))

        # Create REFERS_TO edges for structures:ref and structures:uri on the object itself
        # Note: struct_ref and struct_uri already checked for both prefixes above
        if struct_ref:
            # structures:ref - direct reference to an ID
            edges.append((obj_id, label, struct_ref, None, "REFERS_TO", {}))
        elif struct_uri:
            # structures:uri - resolve to target ID
            target_ref = None
            if '#' in struct_uri:
                target_ref = struct_uri.split('#')[-1]
            else:
                # Use last path segment as ID
                uri_parts = struct_uri.rstrip('/').split('/')
                if uri_parts:
                    target_ref = uri_parts[-1].replace(':', '_')
            if target_ref:
                edges.append((obj_id, label, target_ref, None, "REFERS_TO", {}))

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

    # Process all top-level objects
    for obj in objects:
        if isinstance(obj, dict):
            process_jsonld_object(obj)

    # Generate Cypher statements
    cypher_statements = generate_cypher_from_structures(nodes, edges, contains, upload_id, filename)

    return cypher_statements, nodes, contains, edges


def generate_cypher_from_structures(
    nodes: dict[str, tuple],
    edges: list[tuple],
    contains: list[tuple],
    upload_id: str = None,
    filename: str = None
) -> str:
    """Generate Cypher statements from node and edge structures.

    Args:
        nodes: Dictionary of node structures
        edges: List of edge tuples
        contains: List of containment edge tuples
        upload_id: Unique identifier for this upload batch (for graph isolation)
        filename: Source filename (for graph isolation)

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
            # Handle different value types properly
            if isinstance(value, (list, tuple)):
                # Use Neo4j native array syntax
                array_items = []
                for item in value:
                    if isinstance(item, str):
                        escaped_item = item.replace("'", "\\'")
                        array_items.append(f"'{escaped_item}'")
                    elif isinstance(item, (int, float, bool)):
                        array_items.append(str(item).lower() if isinstance(item, bool) else str(item))
                    else:
                        escaped_item = str(item).replace("'", "\\'")
                        array_items.append(f"'{escaped_item}'")
                props_parts.append(f"{key}: [{', '.join(array_items)}]")
            elif isinstance(value, str):
                # Escape single quotes in strings
                escaped_value = value.replace("'", "\\'")
                props_parts.append(f"{key}: '{escaped_value}'")
            elif isinstance(value, (int, float, bool)):
                # Numbers and booleans don't need quotes
                props_parts.append(f"{key}: {str(value).lower() if isinstance(value, bool) else value}")
            elif value is None:
                # Skip null values
                continue
            else:
                # Convert other types to string
                escaped_value = str(value).replace("'", "\\'")
                props_parts.append(f"{key}: '{escaped_value}'")

        props_str = ", ".join(props_parts)
        cypher_lines.append(f"MERGE (n:{label} {{id: '{node_id}', {props_str}}});")

    # Helper function to build match properties for a specific node ID
    def build_node_match_props(node_id: str) -> str:
        """Build match properties for graph isolation."""
        props = f"id: '{node_id}'"
        if upload_id:
            props += f", _upload_id: '{upload_id}'"
        if filename:
            props += f", _source_file: '{filename}'"
        return props

    # Generate MERGE statements for containment relationships
    for parent_id, parent_label, child_id, child_label, rel_type in contains:
        parent_match = build_node_match_props(parent_id)
        child_match = build_node_match_props(child_id)

        cypher_lines.append(
            f"MATCH (parent:{parent_label} {{{parent_match}}}), (child:{child_label} {{{child_match}}}) "
            f"MERGE (parent)-[:{rel_type}]->(child);"
        )

    # Generate MERGE statements for reference/association edges
    for from_id, from_label, to_id, to_label, rel_type, edge_props in edges:
        # Clean relationship type
        clean_rel_type = rel_type.replace(":", "_").upper()

        # Build match properties for graph isolation
        from_match = build_node_match_props(from_id)
        to_match = build_node_match_props(to_id)

        # Build relationship properties if any
        if edge_props:
            # Build property setters for rich edges (e.g., association endpoint metadata)
            prop_setters = []
            for key, value in sorted(edge_props.items()):
                if isinstance(value, str):
                    escaped_value = value.replace("'", "\\'")
                    prop_setters.append(f"r.{key}='{escaped_value}'")
                elif isinstance(value, (int, float, bool)):
                    prop_setters.append(f"r.{key}={str(value).lower() if isinstance(value, bool) else value}")
                elif isinstance(value, list):
                    # Handle array properties on edges
                    array_items = []
                    for item in value:
                        if isinstance(item, str):
                            escaped_item = item.replace("'", "\\'")
                            array_items.append(f"'{escaped_item}'")
                        elif isinstance(item, (int, float, bool)):
                            array_items.append(str(item).lower() if isinstance(item, bool) else str(item))
                        else:
                            escaped_item = str(item).replace("'", "\\'")
                            array_items.append(f"'{escaped_item}'")
                    prop_setters.append(f"r.{key}=[{', '.join(array_items)}]")
                else:
                    escaped_value = str(value).replace("'", "\\'")
                    prop_setters.append(f"r.{key}='{escaped_value}'")

            props_clause = ", ".join(prop_setters)

            if to_label:
                cypher_lines.append(
                    f"MATCH (from:{from_label} {{{from_match}}}), (to:{to_label} {{{to_match}}}) "
                    f"MERGE (from)-[r:{clean_rel_type}]->(to) ON CREATE SET {props_clause};"
                )
            else:
                # Find target by ID only
                cypher_lines.append(
                    f"MATCH (from:{from_label} {{{from_match}}}), (to {{{to_match}}}) "
                    f"MERGE (from)-[r:{clean_rel_type}]->(to) ON CREATE SET {props_clause};"
                )
        else:
            # Simple edge without properties
            if to_label:
                cypher_lines.append(
                    f"MATCH (from:{from_label} {{{from_match}}}), (to:{to_label} {{{to_match}}}) "
                    f"MERGE (from)-[:{clean_rel_type}]->(to);"
                )
            else:
                # Find target by ID only
                cypher_lines.append(
                    f"MATCH (from:{from_label} {{{from_match}}}), (to {{{to_match}}}) "
                    f"MERGE (from)-[:{clean_rel_type}]->(to);"
                )

    return "\n".join(cypher_lines)
