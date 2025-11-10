"""
XML-based automatic entity selection.

This module analyzes uploaded XML instances to automatically determine which
schema elements should be selected as entities (nodes) vs properties (flattened).

Uses schema-based entity type detection to identify person, organization, and
other entity types from their position in the NIEM type hierarchy.
"""

import logging
from typing import Set, Dict
import defusedxml.ElementTree as ET
from xml.etree.ElementTree import Element

from .xsd_element_tree import TypeDefinition, ElementDeclaration, is_entity_type, _build_indices

logger = logging.getLogger(__name__)


def extract_namespaces_from_xml(xml_content: bytes) -> dict[str, str]:
    """
    Extract namespace prefix mappings from XML content.

    Args:
        xml_content: Raw XML bytes

    Returns:
        Dict mapping namespace URIs to prefixes
    """
    try:
        # Parse to find all xmlns declarations
        import re

        namespaces = {}

        # Extract all xmlns declarations using regex
        # Matches xmlns:prefix="uri" or xmlns="uri"
        xmlns_pattern = rb'xmlns(?::([a-zA-Z0-9_-]+))?=["\']([^"\']+)["\']'

        for match in re.finditer(xmlns_pattern, xml_content):
            prefix_bytes = match.group(1)
            uri_bytes = match.group(2)

            prefix = prefix_bytes.decode('utf-8') if prefix_bytes else ""
            uri = uri_bytes.decode('utf-8')

            namespaces[uri] = prefix
            logger.debug(f"Found namespace: {prefix}:{uri}" if prefix else f"Found default namespace: {uri}")

        logger.info(f"Extracted {len(namespaces)} namespace mappings from XML")
        return namespaces

    except Exception as e:
        logger.error(f"Failed to extract namespaces from XML: {e}")
        return {}


def discover_elements_in_xml(xml_content: bytes) -> Set[str]:
    """
    Discover all unique element qnames used in an XML instance.

    Recursively traverses the XML tree and extracts qualified names
    of all elements present.

    Args:
        xml_content: Raw XML bytes

    Returns:
        Set of qualified element names (e.g., {"nc:Person", "j:CrashDriver"})
    """
    discovered_qnames: Set[str] = set()

    try:
        root = ET.fromstring(xml_content)

        # Build namespace prefix map (uri -> prefix)
        ns_map = extract_namespaces_from_xml(xml_content)
        logger.info(f"Namespace map extracted: {ns_map}")

        def traverse(elem: Element):
            """Recursively traverse and collect qnames."""
            # Get element's namespace and local name
            tag = elem.tag

            if tag.startswith("{"):
                # Element has a namespace: {http://...}LocalName
                ns_end = tag.index("}")
                namespace_uri = tag[1:ns_end]
                local_name = tag[ns_end + 1:]

                # Find prefix for this namespace
                prefix = ns_map.get(namespace_uri, "")

                if prefix:
                    qname = f"{prefix}:{local_name}"
                else:
                    # No prefix found, use local name only
                    qname = local_name

                discovered_qnames.add(qname)
            else:
                # No namespace
                discovered_qnames.add(tag)

            # Recurse to children
            for child in elem:
                traverse(child)

        traverse(root)

        logger.info(f"Discovered {len(discovered_qnames)} unique elements in XML instance")
        logger.info(f"Discovered elements with prefixes: {sorted(discovered_qnames)}")
        return discovered_qnames

    except Exception as e:
        logger.error(f"Failed to discover elements in XML: {e}")
        return set()


def auto_select_entities_from_xml(
    xml_content: bytes,
    xsd_files: dict[str, bytes]
) -> dict[str, bool]:
    """
    Automatically select entity elements based on XML instance analysis.

    This function:
    1. Discovers all elements present in the XML instance
    2. Parses XSD schemas to build type definitions
    3. Uses schema-based entity detection to determine which elements are entities
    4. Returns a selection dictionary with entity elements set to True

    Args:
        xml_content: Raw XML instance bytes
        xsd_files: Dict mapping XSD filenames to content bytes

    Returns:
        Dict mapping element qnames to selection state (True for entities)
    """
    logger.info("Auto-selecting entities from XML instance")

    # Step 1: Discover elements in XML
    discovered_elements = discover_elements_in_xml(xml_content)
    logger.info(f"Found {len(discovered_elements)} elements in XML: {sorted(discovered_elements)}")

    # Step 2: Parse XSD schemas
    try:
        type_definitions, element_declarations, namespace_prefixes = _build_indices(xsd_files)
        logger.info(f"Parsed {len(type_definitions)} type definitions and {len(element_declarations)} element declarations from schemas")

        # Log sample element declarations to verify prefixes
        elem_decl_sample = list(element_declarations.keys())[:20]
        logger.info(f"Sample element declarations from schema: {elem_decl_sample}")
    except Exception as e:
        logger.error(f"Failed to parse XSD schemas: {e}")
        # Fallback: select all discovered elements
        return {qname: True for qname in discovered_elements}

    # Step 3: Determine which discovered elements are entities
    selections: dict[str, bool] = {}
    entity_count = 0
    property_count = 0

    for qname in discovered_elements:
        # Look up element declaration
        elem_decl = element_declarations.get(qname)

        if not elem_decl:
            # Element not found in schema - might be from a different namespace
            # or a custom element. Default to selecting it.
            logger.debug(f"Element {qname} not found in schema, selecting by default")
            selections[qname] = True
            entity_count += 1
            continue

        # Get type definition
        type_def = type_definitions.get(elem_decl.type_ref) if elem_decl.type_ref else None

        # Use schema-based entity detection
        is_entity = is_entity_type(
            elem_name=qname,
            type_name=elem_decl.type_ref,
            type_def=type_def,
            type_definitions=type_definitions
        )

        if is_entity:
            logger.debug(f"✓ {qname} identified as entity type")
            selections[qname] = True
            entity_count += 1
        else:
            logger.debug(f"✗ {qname} identified as property/wrapper type (will be flattened)")
            selections[qname] = False
            property_count += 1

    logger.info(
        f"Auto-selection complete: {entity_count} entities selected, "
        f"{property_count} properties to be flattened"
    )

    # Log the selected entities for visibility
    selected_entities = [qname for qname, selected in selections.items() if selected]
    logger.info(f"Selected entities: {sorted(selected_entities)}")

    return selections
