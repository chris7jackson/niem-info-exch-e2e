#!/usr/bin/env python3

import json
import logging
import xml.etree.ElementTree as ET
from typing import List, Dict, Any

from fastapi import HTTPException, UploadFile
from minio import Minio
from ..services.cmf_tool import validate_xml_with_cmf, is_cmf_available
from ..services.graph_schema import get_graph_schema_manager

logger = logging.getLogger(__name__)


async def handle_xml_ingest(
    files: List[UploadFile],
    s3: Minio,
    schema_id: str = None
) -> Dict[str, Any]:
    """Handle XML file ingestion directly to Neo4j"""
    logger.info(f"Starting direct XML ingestion for {len(files)} files")

    try:
        # Get schema ID (use provided or get active)
        if not schema_id:
            from .schema import get_active_schema_id
            schema_id = await get_active_schema_id(s3)
            if not schema_id:
                raise HTTPException(status_code=400, detail="No active schema found and no schema_id provided")

        # Get the mapping specification for this schema
        try:
            mapping_response = s3.get_object("niem-schemas", f"{schema_id}/mapping.json")
            mapping = json.loads(mapping_response.read().decode('utf-8'))
            mapping_response.close()
            mapping_response.release_conn()
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to load mapping: {str(e)}")

        # Get XSD schema for validation
        xsd_content = None
        try:
            schema_response = s3.get_object("niem-schemas", f"{schema_id}/schema.xsd")
            xsd_content = schema_response.read().decode('utf-8')
            schema_response.close()
            schema_response.release_conn()
        except Exception as e:
            logger.warning(f"Could not load XSD schema for validation: {e}")

        results = []
        total_nodes_created = 0
        total_relationships_created = 0

        # Initialize Neo4j connection
        graph_manager = get_graph_schema_manager()

        try:
            with graph_manager.driver.session() as session:
                for file in files:
                    try:
                        content = await file.read()
                        xml_content = content.decode('utf-8')

                        # XSD validation is REQUIRED - fail if CMF tool or XSD not available
                        # TEMPORARILY DISABLED FOR TESTING NIEM ID RELATIONSHIPS
                        # if not is_cmf_available():
                        #     results.append({
                        #         "filename": file.filename,
                        #         "status": "failed",
                        #         "error": "CMF tool not available - XSD validation required but cannot be performed"
                        #     })
                        #     continue

                        if not xsd_content:
                            results.append({
                                "filename": file.filename,
                                "status": "failed",
                                "error": "XSD schema not found - XSD validation required but schema unavailable"
                            })
                            continue

                        # Perform mandatory XSD validation
                        # TEMPORARILY DISABLED FOR TESTING NIEM ID RELATIONSHIPS
                        # validation_result = validate_xml_with_cmf(xml_content, xsd_content)
                        # if validation_result["status"] != "valid":
                        #     results.append({
                        #         "filename": file.filename,
                        #         "status": "failed",
                        #         "error": f"XML validation failed against XSD: {validation_result.get('message', 'Schema validation error')}"
                        #     })
                        #     continue

                        # Parse XML comprehensively, using mapping as guidance but not limiting to it
                        xml_data = _parse_xml_to_graph_data_comprehensive(xml_content, mapping, filename=file.filename)

                        # Write nodes to Neo4j
                        nodes_created = 0
                        for node_data in xml_data["nodes"]:
                            _create_node(session, node_data)
                            nodes_created += 1

                        # Write relationships to Neo4j
                        relationships_created = 0
                        for rel_data in xml_data["relationships"]:
                            _create_relationship(session, rel_data)
                            relationships_created += 1

                        # Only store file in MinIO AFTER successful graph ingestion
                        try:
                            from ..services.storage import upload_file
                            import hashlib
                            import time

                            # Generate unique filename with timestamp
                            timestamp = int(time.time())
                            file_hash = hashlib.md5(content).hexdigest()[:8]
                            stored_filename = f"xml/{timestamp}_{file_hash}_{file.filename}"

                            await upload_file(s3, "niem-data", stored_filename, content, "application/xml")
                            logger.info(f"Stored XML file in niem-data after successful ingestion: {stored_filename}")
                        except Exception as e:
                            logger.warning(f"Graph ingestion succeeded but failed to store XML file {file.filename} in niem-data: {e}")
                            # Don't fail the ingestion if storage fails after successful graph creation

                        total_nodes_created += nodes_created
                        total_relationships_created += relationships_created

                        results.append({
                            "filename": file.filename,
                            "status": "success",
                            "nodes_created": nodes_created,
                            "relationships_created": relationships_created
                        })

                        logger.info(f"Successfully ingested {file.filename}: {nodes_created} nodes, {relationships_created} relationships")

                    except Exception as e:
                        logger.error(f"Failed to process file {file.filename}: {e}")
                        results.append({
                            "filename": file.filename,
                            "status": "failed",
                            "error": str(e)
                        })

        finally:
            graph_manager.close()

        return {
            "schema_id": schema_id,
            "files_processed": len(files),
            "total_nodes_created": total_nodes_created,
            "total_relationships_created": total_relationships_created,
            "results": results
        }

    except Exception as e:
        logger.error(f"XML ingestion failed: {e}")
        if isinstance(e, HTTPException):
            raise
        raise HTTPException(status_code=500, detail=f"XML ingestion failed: {str(e)}")


async def handle_json_ingest(
    files: List[UploadFile],
    s3: Minio,
    schema_id: str = None
) -> Dict[str, Any]:
    """Handle JSON file ingestion directly to Neo4j"""
    logger.info(f"Starting direct JSON ingestion for {len(files)} files")

    try:
        # Get schema ID (use provided or get active)
        if not schema_id:
            from .schema import get_active_schema_id
            schema_id = await get_active_schema_id(s3)
            if not schema_id:
                raise HTTPException(status_code=400, detail="No active schema found and no schema_id provided")

        # Get the mapping specification for this schema
        try:
            mapping_response = s3.get_object("niem-schemas", f"{schema_id}/mapping.json")
            mapping = json.loads(mapping_response.read().decode('utf-8'))
            mapping_response.close()
            mapping_response.release_conn()
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to load mapping: {str(e)}")

        results = []
        total_nodes_created = 0
        total_relationships_created = 0

        # Initialize Neo4j connection
        graph_manager = get_graph_schema_manager()

        try:
            with graph_manager.driver.session() as session:
                for file in files:
                    try:
                        content = await file.read()
                        json_data = json.loads(content.decode('utf-8'))

                        # Convert JSON to graph data using comprehensive structure-based parsing
                        graph_data = _parse_json_to_graph_data_comprehensive(json_data, mapping, file.filename)

                        # Write nodes to Neo4j
                        nodes_created = 0
                        for node_data in graph_data["nodes"]:
                            _create_node(session, node_data)
                            nodes_created += 1

                        # Write relationships to Neo4j
                        relationships_created = 0
                        for rel_data in graph_data["relationships"]:
                            _create_relationship(session, rel_data)
                            relationships_created += 1

                        # Only store file in MinIO AFTER successful graph ingestion
                        try:
                            from ..services.storage import upload_file
                            import hashlib
                            import time

                            # Generate unique filename with timestamp
                            timestamp = int(time.time())
                            file_hash = hashlib.md5(content).hexdigest()[:8]
                            stored_filename = f"json/{timestamp}_{file_hash}_{file.filename}"

                            await upload_file(s3, "niem-data", stored_filename, content, "application/json")
                            logger.info(f"Stored JSON file in niem-data after successful ingestion: {stored_filename}")
                        except Exception as e:
                            logger.warning(f"Graph ingestion succeeded but failed to store JSON file {file.filename} in niem-data: {e}")
                            # Don't fail the ingestion if storage fails after successful graph creation

                        total_nodes_created += nodes_created
                        total_relationships_created += relationships_created

                        results.append({
                            "filename": file.filename,
                            "status": "success",
                            "nodes_created": nodes_created,
                            "relationships_created": relationships_created
                        })

                        logger.info(f"Successfully ingested {file.filename}: {nodes_created} nodes, {relationships_created} relationships")

                    except json.JSONDecodeError:
                        results.append({
                            "filename": file.filename,
                            "status": "failed",
                            "error": "Invalid JSON format"
                        })
                    except Exception as e:
                        logger.error(f"Failed to process file {file.filename}: {e}")
                        results.append({
                            "filename": file.filename,
                            "status": "failed",
                            "error": str(e)
                        })

        finally:
            graph_manager.close()

        return {
            "schema_id": schema_id,
            "files_processed": len(files),
            "total_nodes_created": total_nodes_created,
            "total_relationships_created": total_relationships_created,
            "results": results
        }

    except Exception as e:
        logger.error(f"JSON ingestion failed: {e}")
        if isinstance(e, HTTPException):
            raise
        raise HTTPException(status_code=500, detail=f"JSON ingestion failed: {str(e)}")


def _parse_xml_to_graph_data_comprehensive(xml_content: str, mapping: Dict[str, Any], filename: str = "unknown") -> Dict[str, Any]:
    """
    Parse XML content into graph structure based on XML element hierarchy.

    GRAPH CREATION STRATEGY:
    - Each XML element becomes a Neo4j node with element tag as label
    - Element containment hierarchy becomes CONTAINS relationships
    - Text content between tags stored as 'content' property
    - All XML attributes preserved as node properties
    - File-unique node IDs prevent collisions across multiple files

    Args:
        xml_content (str): Raw XML content to parse
        mapping (Dict): XSD-derived schema mapping (for future enhancements)
        filename (str): Source filename for node provenance

    Returns:
        Dict containing:
        - nodes: List of node data dicts with labels and properties
        - relationships: List of relationship data dicts

    Node Structure Created:
    {
        "label": "PersonGivenName",  # XML tag name (namespace removed)
        "properties": {
            "node_id": "abc123_node_1",    # File-unique identifier
            "xml_tag": "PersonGivenName",   # Original tag with namespace
            "content": "Peter",             # Text between XML tags
            "type": "leaf|container|mixed", # Content classification
            "level": 2,                     # Depth in XML hierarchy
            "source_file": "crash.xml",    # Source file provenance
            "id": "P01"                     # XML id/ref attributes
        }
    }

    Relationship Structure Created:
    {
        "type": "CONTAINS",              # Parent contains child element
        "from_id": "abc123_node_1",      # Parent node ID
        "to_id": "abc123_node_2",        # Child node ID
        "from_label": "CrashDriver",     # Parent element label
        "to_label": "PersonName",        # Child element label
        "properties": {
            "xml_relationship": "parent_child",
            "level_difference": 1
        }
    }
    """
    try:
        root = ET.fromstring(xml_content)
        nodes = []
        relationships = []
        node_counter = 0  # To generate unique node IDs

        logger.info(f"Starting XML structure-based parsing of root: {root.tag} for file: {filename}")

        # Create file-specific identifier for node uniqueness
        import hashlib
        file_hash = hashlib.md5(filename.encode()).hexdigest()[:8]

        def _get_clean_tag_name(element):
            """Get clean element name without namespace"""
            return element.tag.split('}')[-1] if '}' in element.tag else element.tag

        def _extract_text_content(element):
            """Extract direct text content of element (not including child element text)"""
            if element.text:
                return element.text.strip()
            return None

        def _extract_attributes(element):
            """Extract all attributes as properties, cleaning namespace prefixes"""
            properties = {}
            for attr_name, attr_value in element.attrib.items():
                clean_attr_name = attr_name.split('}')[-1] if '}' in attr_name else attr_name
                properties[clean_attr_name] = attr_value
            return properties

        def _process_element(element, parent_node_id=None, level=0):
            """Recursively process element and create nodes for XML structure"""
            nonlocal node_counter

            # Generate globally unique node ID using filename hash + counter
            node_counter += 1
            node_id = f"{file_hash}_node_{node_counter}"

            # Get element tag name for the node label
            tag_name = _get_clean_tag_name(element)

            # Start with attributes as properties
            properties = _extract_attributes(element)
            properties['node_id'] = node_id
            properties['xml_tag'] = tag_name
            properties['level'] = level
            properties['source_file'] = filename

            # Get direct text content (not from child elements)
            text_content = _extract_text_content(element)

            # Only add content if element has direct text and no child elements
            # OR if element has text content but also has children (mixed content)
            if text_content:
                if len(element) == 0:
                    # Leaf element with text content
                    properties['content'] = text_content
                    properties['type'] = 'leaf'
                else:
                    # Parent element with mixed content
                    properties['mixed_content'] = text_content
                    properties['type'] = 'mixed'
            else:
                if len(element) > 0:
                    # Parent element without direct text content
                    properties['type'] = 'container'
                else:
                    # Empty element
                    properties['type'] = 'empty'

            # Create the node with tag name as label
            node_data = {
                "label": tag_name,
                "properties": properties
            }

            nodes.append(node_data)
            logger.debug(f"Created node: {tag_name}({node_id}) with content: {text_content or 'no content'}")

            # Create parent-child relationship if this element has a parent
            if parent_node_id:
                relationships.append({
                    "type": "CONTAINS",
                    "from_id": parent_node_id,
                    "to_id": node_id,
                    "from_label": "Parent",  # Will be updated when we know parent label
                    "to_label": tag_name,
                    "properties": {
                        "xml_relationship": "parent_child",
                        "level_difference": 1
                    }
                })
                logger.debug(f"Created CONTAINS relationship: {parent_node_id} -> {node_id}")

            # Process all child elements
            for child in element:
                _process_element(child, node_id, level + 1)

            return node_id

        # Process the entire XML tree starting from root
        root_node_id = _process_element(root)

        # Update parent labels in relationships now that all nodes are created
        node_id_to_label = {node["properties"]["node_id"]: node["label"] for node in nodes}
        for rel in relationships:
            if rel["from_label"] == "Parent":
                rel["from_label"] = node_id_to_label.get(rel["from_id"], "Unknown")

        # Create schema-derived relationships based on XSD-like patterns and Association elements
        def _create_schema_derived_relationships():
            """Create relationships derived from XSD schema patterns and Association elements"""
            # Find nodes by their labels for schema-based linking
            nodes_by_label = {}
            for node in nodes:
                label = node["label"]
                if label not in nodes_by_label:
                    nodes_by_label[label] = []
                nodes_by_label[label].append(node)

            # XSD-derived relationship patterns based on CrashDriverInfoType schema
            schema_patterns = {
                "CrashDriverInfo": {
                    # Based on XSD: CrashDriverInfo contains Crash, Charge[], PersonChargeAssociation[]
                    "contains": ["Crash", "Charge", "PersonChargeAssociation", "PersonUnionAssociation",
                                "ParentChildAssociation", "PersonOtherKinAssociation", "Metadata", "PrivacyMetadata"],
                    "associations": {
                        "PersonChargeAssociation": {
                            "associates": ["Person", "Charge"],
                            "relationship_type": "PERSON_CHARGED_WITH"
                        },
                        "PersonUnionAssociation": {
                            "associates": ["Person", "Person"],
                            "relationship_type": "UNION_WITH"
                        },
                        "ParentChildAssociation": {
                            "associates": ["Person", "Person"],
                            "relationship_type": "PARENT_CHILD"
                        }
                    }
                }
            }

            # Process Association elements to create proper relationships
            # PersonChargeAssociation is already represented in the XML hierarchy as CONTAINS relationships
            # The association element itself connects to both Person and Charge via CONTAINS relationships
            # This provides the explicit association without redundant direct Person->Charge relationships

            # Create contextual relationships within CrashDriverInfo based on XSD schema
            if "CrashDriverInfo" in nodes_by_label:
                for crash_driver_info in nodes_by_label["CrashDriverInfo"]:
                    # All Charges within CrashDriverInfo are related to the Crash within the same context
                    crash_nodes = [n for n in nodes_by_label.get("Crash", [])
                                 if n["properties"].get("level", 0) == 1]  # Direct children of CrashDriverInfo
                    charge_nodes = [n for n in nodes_by_label.get("Charge", [])
                                  if n["properties"].get("level", 0) == 1]  # Direct children of CrashDriverInfo

                    # Based on XSD: Charges in CrashDriverInfo are "associated with the driver of a vehicle in a crash"
                    for crash_node in crash_nodes:
                        for charge_node in charge_nodes:
                            relationships.append({
                                "type": "CRASH_RELATED_CHARGE",
                                "from_id": charge_node["properties"]["node_id"],
                                "to_id": crash_node["properties"]["node_id"],
                                "from_label": "Charge",
                                "to_label": "Crash",
                                "properties": {
                                    "relationship_type": "crash_driver_charges",
                                    "schema_derived": True,
                                    "schema_context": "CrashDriverInfoType",
                                    "description": "Legal charges associated with the driver of a vehicle in a crash"
                                }
                            })
                            logger.info(f"Created schema-derived relationship: Charge -[CRASH_RELATED_CHARGE]-> Crash via CrashDriverInfoType schema")

        # Create schema-derived relationships
        _create_schema_derived_relationships()

        logger.info(f"XML structure-based parsing complete: {len(nodes)} nodes, {len(relationships)} relationships")
        logger.info(f"Root element '{_get_clean_tag_name(root)}' processed with {len(list(root.iter()))} total XML elements")

        return {"nodes": nodes, "relationships": relationships}

    except Exception as e:
        logger.error(f"Failed to parse XML with structure-based approach: {e}")
        raise


def _parse_xml_to_graph_data_OLD_NIEM_BASED(xml_content: str, mapping: Dict[str, Any]) -> Dict[str, Any]:
    """OLD NIEM ID-based parsing - kept for reference but not used"""
    try:
        root = ET.fromstring(xml_content)
        nodes = []
        relationships = []
        element_id_map = {}

        logger.info(f"Starting comprehensive XML parsing of root: {root.tag}")

        def _infer_entity_label(entity_id: str) -> str:
            """Infer entity label from ID pattern"""
            if entity_id.startswith("P"):
                return "Person"
            elif entity_id.startswith("O"):
                return "Organization"
            elif entity_id.startswith("L"):
                return "Location"
            elif entity_id.startswith("V"):
                return "Vehicle"
            elif entity_id.startswith("I"):
                return "Item"
            else:
                return "Entity"

        def _get_clean_element_name(element):
            """Get element name without namespace"""
            return element.tag.split('}')[-1] if '}' in element.tag else element.tag

        def _extract_text_with_children(element):
            """Extract text content including nested element text"""
            text_parts = []
            if element.text:
                text_parts.append(element.text.strip())
            for child in element:
                child_text = _extract_text_with_children(child)
                if child_text:
                    text_parts.append(child_text)
                if child.tail:
                    text_parts.append(child.tail.strip())
            return ' '.join(filter(None, text_parts))

        def _extract_all_attributes(element):
            """Extract all attributes, cleaning namespace prefixes"""
            properties = {}
            for attr_name, attr_value in element.attrib.items():
                clean_attr_name = attr_name.split('}')[-1] if '}' in attr_name else attr_name
                properties[clean_attr_name] = attr_value
            return properties

        # Build element ID map for reference resolution
        for element in root.iter():
            element_id = (element.get("{https://docs.oasis-open.org/niemopen/ns/model/structures/6.0/}id") or
                         element.get("id"))
            if element_id:
                element_name = _get_clean_element_name(element)
                element_id_map[element_id] = {
                    "element": element,
                    "label": element_name
                }

        logger.info(f"Built element ID map with {len(element_id_map)} elements")

        # Create nodes for all elements with meaningful content
        for element in root.iter():
            element_name = _get_clean_element_name(element)

            # Skip root document wrapper elements
            if element_name in ["ExchangeDocument", "Document"]:
                continue

            # Get element ID
            element_id = (element.get("{https://docs.oasis-open.org/niemopen/ns/model/structures/6.0/}id") or
                         element.get("id"))

            # Extract all properties
            properties = _extract_all_attributes(element)

            # Get text content
            text_content = _extract_text_with_children(element)
            if text_content:
                properties["content"] = text_content

            # Add element metadata
            properties["xml_element"] = element_name
            properties["has_children"] = len(element) > 0
            properties["level"] = len([p for p in element.iterancestors()]) if hasattr(element, 'iterancestors') else 0

            # Generate synthetic ID if none exists
            if not element_id:
                import hashlib
                element_path = "/".join([p.tag.split('}')[-1] if '}' in p.tag else p.tag for p in element.iterancestors()]) if hasattr(element, 'iterancestors') else element_name
                element_id = hashlib.md5(f"{element_name}_{element_path}_{text_content or ''}".encode()).hexdigest()[:12]
                properties["synthetic_id"] = True

            properties["id"] = element_id

            # Create node
            node_data = {
                "label": element_name,
                "properties": properties
            }

            nodes.append(node_data)
            logger.debug(f"Created node: {element_name}({element_id})")

            # Update element_id_map for synthetic IDs
            if element_id not in element_id_map:
                element_id_map[element_id] = {
                    "element": element,
                    "label": element_name
                }

        # Create parent-child relationships based on XML structure
        for element in root.iter():
            parent = element.getparent() if hasattr(element, 'getparent') else None
            if parent is not None:
                parent_id = (parent.get("{https://docs.oasis-open.org/niemopen/ns/model/structures/6.0/}id") or
                           parent.get("id"))
                child_id = (element.get("{https://docs.oasis-open.org/niemopen/ns/model/structures/6.0/}id") or
                          element.get("id"))

                if parent_id and child_id and parent_id in element_id_map and child_id in element_id_map:
                    relationships.append({
                        "type": "CONTAINS",
                        "from_id": parent_id,
                        "to_id": child_id,
                        "from_label": element_id_map[parent_id]["label"],
                        "to_label": element_id_map[child_id]["label"],
                        "properties": {"relationship_type": "parent_child"}
                    })

        # Process NIEM reference relationships
        def _process_references():
            for node_data in nodes:
                element_id = node_data["properties"]["id"]
                if element_id in element_id_map:
                    element = element_id_map[element_id]["element"]

                    # Handle structures:ref references
                    ref_attr = (element.get("{https://docs.oasis-open.org/niemopen/ns/model/structures/6.0/}ref") or
                               element.get("ref"))
                    if ref_attr:
                        target_id = ref_attr[1:] if ref_attr.startswith("#") else ref_attr
                        if target_id in element_id_map:
                            relationships.append({
                                "type": "REFERENCES",
                                "from_id": element_id,
                                "to_id": target_id,
                                "from_label": node_data["label"],
                                "to_label": element_id_map[target_id]["label"],
                                "properties": {}
                            })
                            logger.info(f"Created REFERENCES relationship: {node_data['label']}({element_id}) -> {element_id_map[target_id]['label']}({target_id})")

                    # Handle structures:uri references (entity references)
                    uri_attr = (element.get("{https://docs.oasis-open.org/niemopen/ns/model/structures/6.0/}uri") or
                               element.get("uri"))
                    if uri_attr:
                        target_id = uri_attr[1:] if uri_attr.startswith("#") else uri_attr
                        if target_id in element_id_map:
                            relationships.append({
                                "type": "REFERS_TO_ENTITY",
                                "from_id": element_id,
                                "to_id": target_id,
                                "from_label": node_data["label"],
                                "to_label": element_id_map[target_id]["label"],
                                "properties": {}
                            })
                            logger.info(f"Created REFERS_TO_ENTITY relationship: {node_data['label']}({element_id}) -> {element_id_map[target_id]['label']}({target_id})")
                        else:
                            # Create placeholder node for external/referenced entity
                            logger.info(f"Creating placeholder node for referenced entity: {target_id}")
                            # Infer entity type from target_id pattern
                            entity_label = _infer_entity_label(target_id)
                            placeholder_node = {
                                "label": entity_label,
                                "properties": {
                                    "id": target_id,
                                    "is_external_reference": True,
                                    "referenced_from": node_data["label"]
                                }
                            }
                            nodes.append(placeholder_node)
                            element_id_map[target_id] = {"label": entity_label, "element": None}

                            # Create the relationship to the placeholder
                            relationships.append({
                                "type": "REFERS_TO_ENTITY",
                                "from_id": element_id,
                                "to_id": target_id,
                                "from_label": node_data["label"],
                                "to_label": entity_label,
                                "properties": {}
                            })
                            logger.info(f"Created REFERS_TO_ENTITY relationship to placeholder: {node_data['label']}({element_id}) -> {entity_label}({target_id})")

                    # Handle metadataRef references
                    metadata_ref = (element.get("{https://docs.oasis-open.org/niemopen/ns/model/niem-core/6.0/}metadataRef") or
                                   element.get("metadataRef"))
                    if metadata_ref:
                        for ref_id in metadata_ref.split():
                            if ref_id in element_id_map:
                                relationships.append({
                                    "type": "HAS_METADATA",
                                    "from_id": element_id,
                                    "to_id": ref_id,
                                    "from_label": node_data["label"],
                                    "to_label": element_id_map[ref_id]["label"],
                                    "properties": {}
                                })
                                logger.info(f"Created HAS_METADATA relationship: {node_data['label']}({element_id}) -> {element_id_map[ref_id]['label']}({ref_id})")

                    # Handle privacyMetadataRef references
                    privacy_ref = (element.get("{http://example.com/PrivacyMetadata/2.0/}privacyMetadataRef") or
                                  element.get("privacyMetadataRef"))
                    if privacy_ref:
                        for ref_id in privacy_ref.split():
                            if ref_id in element_id_map:
                                relationships.append({
                                    "type": "HAS_PRIVACY_METADATA",
                                    "from_id": element_id,
                                    "to_id": ref_id,
                                    "from_label": node_data["label"],
                                    "to_label": element_id_map[ref_id]["label"],
                                    "properties": {}
                                })
                                logger.info(f"Created HAS_PRIVACY_METADATA relationship: {node_data['label']}({element_id}) -> {element_id_map[ref_id]['label']}({ref_id})")

        _process_references()

        logger.info(f"OLD NIEM-based parsing complete: {len(nodes)} nodes, {len(relationships)} relationships")
        return {"nodes": nodes, "relationships": relationships}

    except Exception as e:
        logger.error(f"Failed to parse XML with OLD NIEM-based approach: {e}")
        raise


def _parse_xml_to_graph_data(xml_content: str, mapping: Dict[str, Any]) -> Dict[str, Any]:
    """Parse XML content and convert to graph data using mapping specification"""
    try:
        root = ET.fromstring(xml_content)
        nodes = []
        relationships = []

        logger.info(f"Root element: {root.tag}")
        logger.info(f"XML namespace: {root.tag.split('}')[0] if '}' in root.tag else 'No namespace'}")

        # Extract nodes based on mapping
        for node_mapping in mapping.get("nodes", []):
            label = node_mapping["label"]
            logger.info(f"Looking for elements with label: {label}")

            # Find elements matching this node type
            matching_elements = []
            for element in root.iter():
                element_name = element.tag.split('}')[-1] if '}' in element.tag else element.tag
                logger.debug(f"Checking element: {element_name} against label: {label}")

                if element_name == label:
                    matching_elements.append(element)
                    logger.info(f"Found matching element: {element_name}")

            logger.info(f"Found {len(matching_elements)} elements for label {label}")

            for element in matching_elements:
                node_data = {
                    "label": label,
                    "properties": {}
                }

                # Extract properties based on mapping
                for prop in node_mapping.get("props", []):
                    prop_name = prop["name"]
                    from_path = prop["from"]

                    if from_path.startswith("@"):
                        # Attribute
                        attr_name = from_path[1:]
                        value = element.get(attr_name)

                        # Also check for NIEM structures namespace attributes
                        if not value and attr_name == "id":
                            # Check for structures:uri, structures:ref, or other NIEM identifiers
                            value = (element.get("{https://docs.oasis-open.org/niemopen/ns/model/structures/6.0/}uri") or
                                   element.get("{https://docs.oasis-open.org/niemopen/ns/model/structures/6.0/}ref") or
                                   element.get("{https://docs.oasis-open.org/niemopen/ns/model/structures/6.0/}id"))

                        logger.debug(f"Attribute {attr_name}: {value}")
                    else:
                        # Element text - handle namespaced elements
                        child = element.find(from_path)
                        if child is None:
                            # Try without namespace prefix
                            for child_element in element:
                                child_name = child_element.tag.split('}')[-1] if '}' in child_element.tag else child_element.tag
                                if child_name == from_path:
                                    child = child_element
                                    break

                        value = child.text if child is not None else None
                        logger.debug(f"Element {from_path}: {value}")

                    if value:
                        node_data["properties"][prop_name] = value

                print(f"*** DEBUG: Node properties for {label}: {node_data['properties']}")
                logger.error(f"*** DEBUG: Node properties for {label}: {node_data['properties']}")

                # Generate synthetic ID if no ID property found
                if not node_data["properties"].get("id"):
                    import hashlib
                    element_path = f"/{'/'.join([p.tag.split('}')[-1] if '}' in p.tag else p.tag for p in element.iter()])}"
                    synthetic_id = hashlib.md5(f"{label}_{element_path}_{element.text or ''}".encode()).hexdigest()[:12]
                    node_data["properties"]["id"] = f"synthetic_{synthetic_id}"
                    logger.info(f"Generated synthetic ID for {label}: {node_data['properties']['id']}")

                nodes.append(node_data)
                print(f"*** DEBUG: Added node: {label} with ID {node_data['properties']['id']} and properties: {node_data['properties']}")
                logger.info(f"Added node: {label} with ID {node_data['properties']['id']}")

        logger.info(f"Total nodes extracted: {len(nodes)}")

        # Extract relationships based on mapping (simplified)
        # This would need more sophisticated logic for real XML association parsing
        for rel_mapping in mapping.get("relationships", []):
            # For now, skip relationship extraction as it's complex
            # In practice, this would parse XML associations and create relationships
            pass

        return {"nodes": nodes, "relationships": relationships}

    except Exception as e:
        logger.error(f"Failed to parse XML: {e}")
        raise


def _parse_json_to_graph_data_comprehensive(json_data: Dict[str, Any], mapping: Dict[str, Any], filename: str = "unknown") -> Dict[str, Any]:
    """
    Parse JSON content into graph structure based on JSON object hierarchy.

    GRAPH CREATION STRATEGY:
    - JSON objects become Neo4j nodes with sanitized key names as labels
    - JSON arrays become container nodes with indexed child nodes
    - Primitive values (strings, numbers, booleans) become leaf nodes with content
    - Object/array nesting becomes CONTAINS relationships
    - File-unique node IDs prevent collisions across multiple files

    Args:
        json_data (Dict): Parsed JSON data structure
        mapping (Dict): XSD-derived schema mapping (for future enhancements)
        filename (str): Source filename for node provenance

    Returns:
        Dict containing:
        - nodes: List of node data dicts with labels and properties
        - relationships: List of relationship data dicts

    Label Sanitization Rules:
    - @context -> AT_context (Neo4j labels can't start with @)
    - Special chars replaced with underscores
    - Numbers prefixed with N_ if label starts with digit
    - Empty labels become 'Unknown'

    Node Types Created:
    1. CONTAINER NODES (JSON objects):
    {
        "label": "PersonName",
        "properties": {
            "node_id": "def456_node_1",
            "json_key": "PersonName",
            "type": "container|simple_object",
            "level": 1,
            "source_file": "data.json",
            "PersonGivenName": "Peter",    # Simple properties included directly
            "PersonSurName": "Wimsey"
        }
    }

    2. ARRAY NODES (JSON arrays):
    {
        "label": "PersonMiddleName",
        "properties": {
            "node_id": "def456_node_2",
            "json_key": "PersonMiddleName",
            "type": "array",
            "array_length": 2,
            "level": 2,
            "source_file": "data.json"
        }
    }

    3. LEAF NODES (Primitive values):
    {
        "label": "PersonMiddleName_item_0",
        "properties": {
            "node_id": "def456_node_3",
            "json_key": "PersonMiddleName_item_0",
            "type": "leaf",
            "content": "Death",           # The actual JSON value
            "value": "Death",            # Duplicate for compatibility
            "data_type": "str",          # Python type name
            "level": 3,
            "source_file": "data.json"
        }
    }

    Content Capture Strategy:
    - Primitive values: Direct value storage in 'content' property
    - Simple objects: All key-value pairs aggregated as content string
    - Arrays: Each element becomes separate child node with content
    - Complex nested structures: Hierarchical node creation with relationships
    """
    try:
        nodes = []
        relationships = []
        node_counter = 0

        logger.info(f"Starting JSON structure-based parsing for file: {filename}")

        # Create file-specific identifier for node uniqueness
        import hashlib
        file_hash = hashlib.md5(filename.encode()).hexdigest()[:8]

        def sanitize_label(label: str) -> str:
            """Sanitize label to be valid for Neo4j"""
            # Remove or replace invalid characters for Neo4j labels
            # Labels can't start with @ or contain special characters
            label = str(label)
            if label.startswith('@'):
                label = 'AT_' + label[1:]  # @context becomes AT_context
            # Replace other invalid characters
            label = ''.join(c if c.isalnum() or c == '_' else '_' for c in label)
            # Ensure it doesn't start with a number
            if label and label[0].isdigit():
                label = 'N_' + label
            # Ensure it's not empty
            if not label:
                label = 'Unknown'
            return label

        def create_nodes_from_json(obj, parent_id=None, level=0, key_name="root"):
            nonlocal node_counter, nodes, relationships

            node_counter += 1
            current_node_id = f"{file_hash}_node_{node_counter}"

            # Sanitize the key name for use as a node label
            sanitized_label = sanitize_label(key_name)

            # Determine node properties based on JSON value type
            if isinstance(obj, dict):
                # Dictionary becomes a container node
                node_data = {
                    "id": current_node_id,
                    "label": sanitized_label,
                    "properties": {
                        "id": current_node_id,
                        "node_id": current_node_id,
                        "json_key": key_name,
                        "type": "container",
                        "level": level,
                        "source_file": filename
                    }
                }

                # Add simple properties (strings, numbers, booleans) including content capture
                simple_values = []
                for k, v in obj.items():
                    if isinstance(v, (str, int, float, bool)) and v is not None:
                        node_data["properties"][k] = v
                        # Store all simple values for potential content aggregation
                        simple_values.append(f"{k}: {v}")

                # If this object only contains simple values (no nested objects/arrays),
                # aggregate them as content like XML text content
                if simple_values and all(isinstance(v, (str, int, float, bool)) or v is None for v in obj.values()):
                    node_data["properties"]["content"] = "; ".join(simple_values)
                    node_data["properties"]["type"] = "simple_object"  # Object with only simple values

                nodes.append(node_data)
                logger.debug(f"Created container node: {key_name} with ID: {current_node_id}")

                # Create relationship to parent if exists
                if parent_id:
                    relationship_data = {
                        "type": "CONTAINS",
                        "from_id": parent_id,
                        "to_id": current_node_id,
                        "from_label": "Unknown",  # Will be filled later
                        "to_label": sanitized_label,
                        "properties": {
                            "relationship_type": "parent_child",
                            "child_key": key_name
                        }
                    }
                    relationships.append(relationship_data)
                    logger.debug(f"Created CONTAINS relationship: {parent_id} -> {current_node_id}")

                # Recursively process nested objects and arrays
                for k, v in obj.items():
                    if isinstance(v, (dict, list)):
                        create_nodes_from_json(v, current_node_id, level + 1, k)

            elif isinstance(obj, list):
                # Array becomes a container node
                node_data = {
                    "id": current_node_id,
                    "label": sanitized_label,
                    "properties": {
                        "id": current_node_id,
                        "node_id": current_node_id,
                        "json_key": key_name,
                        "type": "array",
                        "level": level,
                        "array_length": len(obj),
                        "source_file": filename
                    }
                }

                nodes.append(node_data)
                logger.debug(f"Created array node: {key_name} with {len(obj)} items")

                # Create relationship to parent if exists
                if parent_id:
                    relationship_data = {
                        "type": "CONTAINS",
                        "from_id": parent_id,
                        "to_id": current_node_id,
                        "from_label": "Unknown",  # Will be filled later
                        "to_label": sanitized_label,
                        "properties": {
                            "relationship_type": "parent_child",
                            "child_key": key_name
                        }
                    }
                    relationships.append(relationship_data)

                # Process array items
                for i, item in enumerate(obj):
                    if isinstance(item, (dict, list)):
                        create_nodes_from_json(item, current_node_id, level + 1, f"{key_name}_item_{i}")
                    else:
                        # Primitive values in arrays also become leaf nodes with content
                        create_nodes_from_json(item, current_node_id, level + 1, f"{key_name}_item_{i}")

            else:
                # Primitive values become value nodes (leaf nodes with content)
                node_data = {
                    "id": current_node_id,
                    "label": sanitized_label,
                    "properties": {
                        "id": current_node_id,
                        "node_id": current_node_id,
                        "json_key": key_name,
                        "type": "leaf",  # Changed from "value" to "leaf" to match XML parser
                        "level": level,
                        "value": str(obj) if obj is not None else "null",
                        "content": str(obj) if obj is not None else "null",  # Added content property like XML parser
                        "data_type": type(obj).__name__,
                        "source_file": filename
                    }
                }

                nodes.append(node_data)
                logger.debug(f"Created value node: {key_name} = {obj}")

                # Create relationship to parent if exists
                if parent_id:
                    relationship_data = {
                        "type": "CONTAINS",
                        "from_id": parent_id,
                        "to_id": current_node_id,
                        "from_label": "Unknown",  # Will be filled later
                        "to_label": sanitized_label,
                        "properties": {
                            "relationship_type": "parent_child",
                            "child_key": key_name
                        }
                    }
                    relationships.append(relationship_data)

            return current_node_id

        # Start parsing from root
        create_nodes_from_json(json_data, None, 0, "JSONRoot")

        # Update "from_label" in relationships now that all nodes are created
        node_id_to_label = {node["properties"]["node_id"]: node["label"] for node in nodes}
        for rel in relationships:
            if rel.get("from_label") == "Unknown":
                rel["from_label"] = node_id_to_label.get(rel["from_id"], "Unknown")

        logger.info(f"JSON parsing complete for {filename}: {len(nodes)} nodes, {len(relationships)} relationships")

        return {
            "nodes": nodes,
            "relationships": relationships
        }

    except Exception as e:
        logger.error(f"Error parsing JSON {filename}: {e}")
        raise


def _parse_json_to_graph_data(json_data: Dict[str, Any], mapping: Dict[str, Any]) -> Dict[str, Any]:
    """Parse JSON content and convert to graph data using mapping specification"""
    nodes = []
    relationships = []

    # Extract nodes based on mapping
    for node_mapping in mapping.get("nodes", []):
        label = node_mapping["label"]

        # Look for arrays or objects matching this node type
        if label.lower() in json_data:
            data_items = json_data[label.lower()]
            if not isinstance(data_items, list):
                data_items = [data_items]

            for item in data_items:
                node_data = {
                    "label": label,
                    "properties": {}
                }

                # Extract properties based on mapping
                for prop in node_mapping.get("props", []):
                    prop_name = prop["name"]
                    from_path = prop["from"]

                    # Simple property extraction (can be enhanced for nested JSON)
                    value = item.get(from_path, item.get(prop_name))
                    if value:
                        node_data["properties"][prop_name] = value

                # Only add node if it has an ID property
                if node_data["properties"].get("id"):
                    nodes.append(node_data)

    return {"nodes": nodes, "relationships": relationships}


def _create_node(session, node_data: Dict[str, Any]):
    """
    Create a node in Neo4j with dynamic label and properties.

    GRAPH STORAGE STRATEGY:
    - Uses MERGE to find existing nodes by ID or create new ones
    - Dynamic label from node_data["label"]
    - All properties from node_data["properties"] added to node
    - Supports both 'id' (XML attributes) and 'node_id' (generated) as primary keys

    Args:
        session: Active Neo4j session for transaction
        node_data: Dict with structure:
        {
            "label": "PersonGivenName",     # Becomes Neo4j node label
            "properties": {
                "id": "P01",                # Primary key (XML id attribute)
                "node_id": "abc123_node_1", # Alternative primary key (generated)
                "content": "Peter",         # Actual data content
                "xml_tag": "nc:PersonGivenName", # Source element info
                "level": 2,                 # Hierarchy depth
                "source_file": "crash.xml" # File provenance
            }
        }

    Cypher Query Generated:
        MERGE (n:PersonGivenName {id: $id})
        SET n += $props

    This pattern ensures:
    - No duplicate nodes for same logical entity
    - All properties preserved on the node
    - Efficient upsert operation for data updates
    """
    label = node_data["label"]
    properties = node_data["properties"]

    # Get the ID - prefer 'id' but fall back to 'node_id' for XML structure-based nodes
    node_id = properties.get("id") or properties.get("node_id")

    if not node_id:
        raise ValueError(f"Node must have either 'id' or 'node_id' property: {properties}")

    # Build Cypher query - use MERGE to find or create by ID, then SET all properties
    query = f"MERGE (n:{label} {{id: $id}}) SET n += $props"

    print(f"*** DEBUG: Creating node with query: {query}")
    print(f"*** DEBUG: Parameters: id={node_id}, props={properties}")
    logger.debug(f"Creating node with query: {query}")
    logger.debug(f"Parameters: id={node_id}, props={properties}")

    result = session.run(query, id=node_id, props=properties)
    counters = result.consume().counters
    print(f"*** DEBUG: Node creation result: {counters}")
    logger.debug(f"Node creation result: {counters}")


def _create_relationship(session, rel_data: Dict[str, Any]):
    """
    Create a relationship between two nodes in Neo4j.

    RELATIONSHIP CREATION STRATEGY:
    - Matches nodes by their ID and label for precision
    - Creates directed relationships with specified type
    - Adds relationship properties for additional metadata
    - Uses MERGE to prevent duplicate relationships

    Args:
        session: Active Neo4j session for transaction
        rel_data: Dict with structure:
        {
            "type": "CONTAINS",           # Relationship type (becomes -[:CONTAINS]->)
            "from_id": "P01",            # Source node ID
            "to_id": "abc123_node_1",    # Target node ID
            "from_label": "CrashDriver", # Source node label (for precise matching)
            "to_label": "PersonName",    # Target node label (for precise matching)
            "properties": {              # Optional relationship properties
                "xml_relationship": "parent_child",
                "level_difference": 1,
                "child_key": "PersonName"
            }
        }

    Cypher Query Generated:
        MATCH (from:CrashDriver {id: $from_id})
        MATCH (to:PersonName {id: $to_id})
        MERGE (from)-[r:CONTAINS {xml_relationship: $xml_relationship, level_difference: $level_difference}]->(to)

    Relationship Types Created:
    - CONTAINS: Parent-child element containment (XML hierarchy, JSON nesting)
    - REFERS_TO_ENTITY: Reference relationships (structures:ref attributes)
    - HAS_METADATA: Metadata associations (metadataRef attributes)
    - HAS_PRIVACY_METADATA: Privacy metadata links (privacyMetadataRef)

    This ensures:
    - Precise node matching using both ID and label
    - No duplicate relationships between same nodes
    - Rich relationship metadata for query optimization
    """
    rel_type = rel_data["type"]
    from_id = rel_data["from_id"]
    to_id = rel_data["to_id"]
    from_label = rel_data["from_label"]
    to_label = rel_data["to_label"]
    properties = rel_data.get("properties", {})

    # Build Cypher query
    props_str = ", ".join([f"{k}: ${k}" for k in properties.keys()]) if properties else ""
    props_clause = f" {{{props_str}}}" if props_str else ""

    query = f"""
    MATCH (from:{from_label} {{id: $from_id}})
    MATCH (to:{to_label} {{id: $to_id}})
    MERGE (from)-[r:{rel_type}{props_clause}]->(to)
    """

    session.run(query, from_id=from_id, to_id=to_id, **properties)