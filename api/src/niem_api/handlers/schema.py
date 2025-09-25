#!/usr/bin/env python3

import hashlib
import json
import logging
import os
import time
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Dict, List, Any, Optional

import httpx
from fastapi import HTTPException, UploadFile
from minio import Minio
from minio.error import S3Error

from ..models.models import SchemaResponse, NiemNdrReport, NiemNdrViolation
from ..services.storage import upload_file
from ..services.ndr_validator import NiemNdrValidator
from ..services.cmf_tool import convert_xsd_to_jsonschema_with_cmf, is_cmf_available
from ..services.graph_schema import get_graph_schema_manager

logger = logging.getLogger(__name__)


async def handle_schema_upload(
    file: UploadFile,
    s3: Minio
) -> SchemaResponse:
    """Handle XSD schema upload and validation"""
    try:
        # Read file content
        content = await file.read()

        # Validate file size (configurable limit, defaults to 20MB)
        max_file_size_mb = int(os.getenv("MAX_SCHEMA_FILE_SIZE_MB", "20"))
        max_file_size_bytes = max_file_size_mb * 1024 * 1024
        if len(content) > max_file_size_bytes:
            raise HTTPException(status_code=400, detail=f"File size exceeds {max_file_size_mb}MB limit")

        # Generate schema ID with timestamp for uniqueness
        timestamp = datetime.utcnow().isoformat()
        schema_id = hashlib.sha256(content + file.filename.encode() + timestamp.encode()).hexdigest()

        # Run NIEM NDR validation
        logger.error(f"*** DEBUG: About to run NDR validation")
        ndr_validator = NiemNdrValidator()
        ndr_result = await ndr_validator.validate_xsd_conformance(content.decode())
        logger.error(f"*** DEBUG: NDR validation result: {ndr_result}")

        # Convert NDR result to model
        ndr_violations = [
            NiemNdrViolation(**violation) for violation in ndr_result.get("violations", [])
        ]
        niem_ndr_report = NiemNdrReport(
            status=ndr_result["status"],
            message=ndr_result["message"],
            conformance_target=ndr_result["conformance_target"],
            violations=ndr_violations,
            summary=ndr_result.get("summary", {})
        )

        # Check if NIEM validation failed - reject upload if validation fails
        if ndr_result["status"] == "fail":
            error_messages = [v["message"] for v in ndr_result.get("violations", []) if v["type"] == "error"]
            violation_summary = f"Found {ndr_result['summary']['error_count']} NIEM NDR violations"
            if error_messages:
                violation_summary += f": {'; '.join(error_messages)}"

            raise HTTPException(
                status_code=400,
                detail=f"Schema upload rejected due to NIEM NDR validation failures. {violation_summary}"
            )

        # Check if validation encountered an error
        if ndr_result["status"] == "error":
            raise HTTPException(
                status_code=500,
                detail=f"NIEM NDR validation error: {ndr_result['message']}"
            )

        # Convert XSD to JSON Schema using integrated CMF tool
        if is_cmf_available():
            try:
                conversion_result = await convert_xsd_to_jsonschema_with_cmf(content.decode())
                if conversion_result.get("status") != "success":
                    logger.warning(f"XSD to JSON Schema conversion failed: {conversion_result.get('error', 'Unknown error')}")
                    conversion_result = {
                        "status": "error",
                        "jsonschema": {}
                    }
            except Exception as e:
                logger.warning(f"XSD to JSON Schema conversion failed: {e}")
                conversion_result = {
                    "status": "error",
                    "jsonschema": {}
                }
        else:
            logger.warning("CMF tool not available, proceeding without JSON schema conversion")
            conversion_result = {
                "status": "unavailable",
                "jsonschema": {}
            }

        # Store files in MinIO
        await upload_file(s3, "niem-schemas", f"{schema_id}/schema.xsd", content, "application/xml")

        # Store JSON Schema if conversion succeeded
        if conversion_result["jsonschema"]:
            json_schema_content = json.dumps(conversion_result["jsonschema"]).encode()
            await upload_file(s3, "niem-schemas", f"{schema_id}/jsonschema.json", json_schema_content, "application/json")

        # Store NIEM NDR report
        ndr_report_content = json.dumps(ndr_result).encode()
        await upload_file(s3, "niem-schemas", f"{schema_id}/niem_ndr_report.json", ndr_report_content, "application/json")

        # Generate and store mapping spec from XSD content
        mapping_spec = generate_mapping_spec_from_xsd(content.decode())
        mapping_content = json.dumps(mapping_spec, indent=2).encode()
        await upload_file(s3, "niem-schemas", f"{schema_id}/mapping.json", mapping_content, "application/json")

        # Configure graph database schema from mapping
        graph_schema_result = None
        try:
            graph_manager = get_graph_schema_manager()
            graph_schema_result = graph_manager.configure_schema_from_mapping(mapping_spec)
            graph_manager.close()
            logger.info(f"Graph schema configured: {len(graph_schema_result.get('indexes_created', []))} indexes, {len(graph_schema_result.get('constraints_created', []))} constraints")
        except Exception as e:
            logger.warning(f"Failed to configure graph schema: {e}")
            graph_schema_result = {"error": str(e)}

        # Store graph schema configuration result
        if graph_schema_result:
            graph_schema_content = json.dumps(graph_schema_result, indent=2).encode()
            await upload_file(s3, "niem-schemas", f"{schema_id}/graph_schema_result.json", graph_schema_content, "application/json")

        # Store schema metadata in MinIO instead of database
        schema_metadata = {
            "schema_id": schema_id,
            "filename": file.filename,
            "uploaded_at": timestamp,
            "known_gaps": "",
            "is_active": True  # Latest uploaded schema is automatically active
        }
        metadata_content = json.dumps(schema_metadata, indent=2).encode()
        await upload_file(s3, "niem-schemas", f"{schema_id}/metadata.json", metadata_content, "application/json")

        # Mark this as the active schema by storing its ID
        active_schema_marker = {"active_schema_id": schema_id, "updated_at": timestamp}
        active_content = json.dumps(active_schema_marker, indent=2).encode()
        await upload_file(s3, "niem-schemas", "active_schema.json", active_content, "application/json")

        return SchemaResponse(
            schema_id=schema_id,
            niem_ndr_report=niem_ndr_report,
            is_active=True  # Latest uploaded schema is automatically active
        )

    except Exception as e:
        logger.error(f"Schema upload failed: {e}")
        if isinstance(e, HTTPException):
            raise
        raise HTTPException(status_code=500, detail=f"Schema upload failed: {str(e)}")


async def handle_schema_activation(schema_id: str, s3: Minio):
    """Activate a schema by updating the active marker"""
    try:
        # Check if schema exists by looking for its metadata
        try:
            s3.get_object("niem-schemas", f"{schema_id}/metadata.json")
        except S3Error:
            raise HTTPException(status_code=404, detail="Schema not found")

        # Update active schema marker
        timestamp = datetime.utcnow().isoformat()
        active_schema_marker = {"active_schema_id": schema_id, "updated_at": timestamp}
        active_content = json.dumps(active_schema_marker, indent=2).encode()
        await upload_file(s3, "niem-schemas", "active_schema.json", active_content, "application/json")

        return {"active_schema_id": schema_id}

    except Exception as e:
        logger.error(f"Schema activation failed: {e}")
        if isinstance(e, HTTPException):
            raise
        raise HTTPException(status_code=500, detail=f"Schema activation failed: {str(e)}")


async def get_all_schemas(s3: Minio):
    """Get all schemas from MinIO storage"""
    try:
        schemas = []

        # Get active schema ID
        active_schema_id = await get_active_schema_id(s3)

        # List all schema directories - handle case where bucket doesn't exist
        try:
            objects = s3.list_objects("niem-schemas", recursive=False)
        except S3Error as e:
            # If bucket doesn't exist, return empty list
            if e.code == "NoSuchBucket":
                logger.info("Schema bucket does not exist, returning empty schema list")
                return []
            else:
                raise

        for obj in objects:
            if obj.object_name.endswith('/') and obj.object_name != "active_schema.json":
                schema_dir = obj.object_name.rstrip('/')

                # Load metadata for this schema
                try:
                    metadata_obj = s3.get_object("niem-schemas", f"{schema_dir}/metadata.json")
                    metadata = json.loads(metadata_obj.read().decode())

                    # Mark as active if it matches the active schema
                    metadata["active"] = (metadata["schema_id"] == active_schema_id)
                    schemas.append(metadata)

                except S3Error:
                    # Skip schemas without metadata
                    continue

        # Sort by upload time, newest first
        schemas.sort(key=lambda x: x.get("uploaded_at", ""), reverse=True)
        return schemas

    except Exception as e:
        logger.error(f"Failed to get schemas: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get schemas: {str(e)}")


async def get_active_schema_id(s3: Minio) -> Optional[str]:
    """Get the currently active schema ID"""
    try:
        active_obj = s3.get_object("niem-schemas", "active_schema.json")
        active_data = json.loads(active_obj.read().decode())
        return active_data.get("active_schema_id")
    except S3Error:
        return None


async def get_schema_metadata(s3: Minio, schema_id: str) -> Optional[Dict]:
    """Get metadata for a specific schema"""
    try:
        metadata_obj = s3.get_object("niem-schemas", f"{schema_id}/metadata.json")
        return json.loads(metadata_obj.read().decode())
    except S3Error:
        return None


def generate_mapping_spec_from_xsd(xsd_content: str) -> Dict[str, Any]:
    """Generate comprehensive mapping specification by parsing XSD content"""
    logger.info("Parsing XSD content to generate comprehensive mapping specification")

    try:
        # Parse the XSD
        root = ET.fromstring(xsd_content)

        # Get namespace map
        namespaces = _extract_namespaces(root)
        target_namespace = root.get('targetNamespace', '')

        # Parse all elements, types, and their attributes comprehensively
        all_elements = _parse_all_elements(root, namespaces)
        complex_types = _parse_complex_types_comprehensive(root, namespaces)
        simple_types = _parse_simple_types(root, namespaces)
        global_attributes = _parse_global_attributes(root, namespaces)

        # Parse associations/relationships
        associations = _parse_associations_comprehensive(root, namespaces, complex_types, all_elements)

        # Generate nodes from all possible element types
        nodes = []
        indexes = []

        # Process global elements that can be root nodes
        for element_name, element_info in all_elements.items():
            if element_info.get('is_global', False):
                label = _element_name_to_label(element_name)

                node = {
                    "label": label,
                    "match_on": ["@id"],
                    "props": []
                }

                # Add properties from element's type
                type_name = element_info.get('type')
                if type_name and type_name in complex_types:
                    type_info = complex_types[type_name]

                    # Add properties from nested elements
                    for nested_element in type_info.get('elements', []):
                        prop_name = _element_name_to_property(nested_element['name'])
                        node["props"].append({
                            "name": prop_name,
                            "from": nested_element['name'],
                            "type": nested_element.get('type', 'string'),
                            "min_occurs": nested_element.get('min_occurs', '1'),
                            "max_occurs": nested_element.get('max_occurs', '1')
                        })

                    # Add all attributes from the type
                    for attribute in type_info.get('attributes', []):
                        node["props"].append({
                            "name": attribute['name'],
                            "from": f"@{attribute['name']}",
                            "type": attribute.get('type', 'string'),
                            "use": attribute.get('use', 'optional')
                        })

                # Add global attributes that might apply
                for attr_name, attr_info in global_attributes.items():
                    node["props"].append({
                        "name": attr_name,
                        "from": f"@{attr_name}",
                        "type": attr_info.get('type', 'string'),
                        "use": "optional",
                        "global": True
                    })

                # Ensure we have an ID property for matching
                has_id = any(prop['name'] == 'id' for prop in node["props"])
                if not has_id:
                    node["props"].append({
                        "name": "id",
                        "from": "@id",
                        "type": "string",
                        "use": "optional"
                    })

                nodes.append(node)

                # Create index for ID attribute
                indexes.append({
                    "label": label,
                    "properties": ["id"]
                })

        # Process referenced elements to create additional nodes
        referenced_elements = set()
        for type_name, type_info in complex_types.items():
            for element in type_info.get('elements', []):
                if element.get('type') == 'reference' and element.get('ref'):
                    ref_name = element['ref'].split(':')[-1] if ':' in element['ref'] else element['ref']
                    referenced_elements.add(ref_name)

        for ref_name in referenced_elements:
            label = _element_name_to_label(ref_name)

            # Skip if we already have a node with this label
            if any(node['label'] == label for node in nodes):
                continue

            node = {
                "label": label,
                "match_on": ["@id"],
                "props": [{
                    "name": "id",
                    "from": "@id",
                    "type": "string",
                    "use": "optional"
                }]
            }

            nodes.append(node)

            # Create index for ID attribute
            indexes.append({
                "label": label,
                "properties": ["id"]
            })

        # Also process complex types that might represent entities
        for type_name, type_info in complex_types.items():
            if not _is_association_type(type_name, associations):
                label = _type_name_to_label(type_name)

                # Skip if we already have a node with this label from global elements
                if any(node['label'] == label for node in nodes):
                    continue

                node = {
                    "label": label,
                    "match_on": ["@id"],
                    "props": []
                }

                # Add properties from elements
                for element in type_info.get('elements', []):
                    prop_name = _element_name_to_property(element['name'])
                    node["props"].append({
                        "name": prop_name,
                        "from": element['name'],
                        "type": element.get('type', 'string'),
                        "min_occurs": element.get('min_occurs', '1'),
                        "max_occurs": element.get('max_occurs', '1')
                    })

                # Add all attributes
                for attribute in type_info.get('attributes', []):
                    node["props"].append({
                        "name": attribute['name'],
                        "from": f"@{attribute['name']}",
                        "type": attribute.get('type', 'string'),
                        "use": attribute.get('use', 'optional')
                    })

                # Ensure we have an ID property for matching
                has_id = any(prop['name'] == 'id' for prop in node["props"])
                if not has_id:
                    node["props"].append({
                        "name": "id",
                        "from": "@id",
                        "type": "string",
                        "use": "optional"
                    })

                nodes.append(node)

                # Create index for ID attribute
                indexes.append({
                    "label": label,
                    "properties": ["id"]
                })

        # Generate relationships from associations
        relationships = []
        for assoc_name, assoc_info in associations.items():
            rel_type = _association_to_relationship_type(assoc_name)

            # Parse the association structure to identify source and target
            refs = assoc_info.get('references', [])
            if len(refs) >= 2:
                from_ref = refs[0]
                to_ref = refs[1]

                relationships.append({
                    "type": rel_type,
                    "from_label": _element_name_to_label(from_ref['target_type']),
                    "to_label": _element_name_to_label(to_ref['target_type']),
                    "via_association": assoc_name,
                    "match": {
                        "from": f"{from_ref['name']}/@ref",
                        "to": f"{to_ref['name']}/@ref"
                    }
                })

        mapping_spec = {
            "version": 2,
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "source_schema": {
                "target_namespace": target_namespace,
                "namespaces": namespaces
            },
            "indexes": indexes,
            "nodes": nodes,
            "relationships": relationships,
            "metadata": {
                "total_global_elements": len([e for e in all_elements.values() if e.get('is_global')]),
                "total_complex_types": len(complex_types),
                "total_simple_types": len(simple_types),
                "total_global_attributes": len(global_attributes),
                "total_associations": len(associations)
            }
        }

        logger.info(f"Generated comprehensive mapping spec with {len(nodes)} nodes and {len(relationships)} relationships")
        return mapping_spec

    except Exception as e:
        logger.error(f"Failed to parse XSD for mapping generation: {e}")
        # Return a basic fallback mapping
        return {
            "version": 2,
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "error": f"XSD parsing failed: {str(e)}",
            "indexes": [],
            "nodes": [],
            "relationships": []
        }


def _extract_namespaces(root: ET.Element) -> Dict[str, str]:
    """Extract namespace mappings from XSD root element"""
    namespaces = {}
    for key, value in root.attrib.items():
        if key.startswith('{http://www.w3.org/2000/xmlns/}'):
            prefix = key.split('}')[1] if '}' in key else ''
            namespaces[prefix] = value
        elif key == 'xmlns':
            namespaces[''] = value
    return namespaces


def _parse_all_elements(root: ET.Element, _namespaces: Dict[str, str]) -> Dict[str, Dict[str, Any]]:
    """Parse all global and local elements from XSD"""
    elements = {}

    # Parse global elements (direct children of schema)
    for element in root.findall('.//{http://www.w3.org/2001/XMLSchema}element[@name]'):
        element_name = element.get('name')
        if element_name:
            # Check if it's a global element by looking for direct schema parent
            parent = None
            for schema_child in root:
                if schema_child == element:
                    parent = root
                    break

            # If it's a direct child of schema, it's global
            if parent is root:
                elements[element_name] = {
                    'name': element_name,
                    'type': element.get('type'),
                    'min_occurs': element.get('minOccurs', '1'),
                    'max_occurs': element.get('maxOccurs', '1'),
                    'is_global': True,
                    'abstract': element.get('abstract', 'false') == 'true',
                    'substitution_group': element.get('substitutionGroup')
                }

    return elements


def _parse_simple_types(root: ET.Element, _namespaces: Dict[str, str]) -> Dict[str, Dict[str, Any]]:
    """Parse simple types from XSD"""
    simple_types = {}

    for simple_type in root.findall('.//{http://www.w3.org/2001/XMLSchema}simpleType'):
        type_name = simple_type.get('name')
        if type_name:
            restriction = simple_type.find('.//{http://www.w3.org/2001/XMLSchema}restriction')
            type_info = {
                'name': type_name,
                'base_type': restriction.get('base') if restriction is not None else 'string',
                'restrictions': []
            }

            if restriction is not None:
                # Parse restrictions (enumerations, patterns, etc.)
                for facet in restriction:
                    facet_name = facet.tag.split('}')[-1] if '}' in facet.tag else facet.tag
                    type_info['restrictions'].append({
                        'type': facet_name,
                        'value': facet.get('value')
                    })

            simple_types[type_name] = type_info

    return simple_types


def _parse_global_attributes(root: ET.Element, _namespaces: Dict[str, str]) -> Dict[str, Dict[str, Any]]:
    """Parse global attributes from XSD"""
    attributes = {}

    for attribute in root.findall('.//{http://www.w3.org/2001/XMLSchema}attribute[@name]'):
        attr_name = attribute.get('name')
        if attr_name:
            # Check if it's a global attribute by looking for direct schema parent
            parent = None
            for schema_child in root:
                if schema_child == attribute:
                    parent = root
                    break

            # If it's a direct child of schema, it's global
            if parent is root:
                attributes[attr_name] = {
                    'name': attr_name,
                    'type': attribute.get('type', 'string'),
                    'use': attribute.get('use', 'optional'),
                    'default': attribute.get('default'),
                    'fixed': attribute.get('fixed')
                }

    return attributes


def _parse_complex_types_comprehensive(root: ET.Element, _namespaces: Dict[str, str]) -> Dict[str, Dict[str, Any]]:
    """Parse complex types comprehensively from XSD"""
    complex_types = {}

    # Find all complexType elements
    for complex_type in root.findall('.//{http://www.w3.org/2001/XMLSchema}complexType'):
        type_name = complex_type.get('name')
        if not type_name:
            continue

        type_info = {
            'name': type_name,
            'elements': [],
            'attributes': [],
            'has_id_attribute': False,
            'abstract': complex_type.get('abstract', 'false') == 'true',
            'mixed': complex_type.get('mixed', 'false') == 'true'
        }

        # Parse all nested elements (sequence, choice, all)
        for container in complex_type.findall('.//{http://www.w3.org/2001/XMLSchema}sequence') + \
                        complex_type.findall('.//{http://www.w3.org/2001/XMLSchema}choice') + \
                        complex_type.findall('.//{http://www.w3.org/2001/XMLSchema}all'):
            for element in container.findall('.//{http://www.w3.org/2001/XMLSchema}element'):
                element_name = element.get('name')
                element_ref = element.get('ref')

                if element_name:
                    type_info['elements'].append({
                        'name': element_name,
                        'type': element.get('type', 'string'),
                        'min_occurs': element.get('minOccurs', '1'),
                        'max_occurs': element.get('maxOccurs', '1'),
                        'nillable': element.get('nillable', 'false') == 'true'
                    })
                elif element_ref:
                    # Reference to global element
                    ref_name = element_ref.split(':')[-1] if ':' in element_ref else element_ref
                    type_info['elements'].append({
                        'name': ref_name,
                        'type': 'reference',
                        'ref': element_ref,
                        'min_occurs': element.get('minOccurs', '1'),
                        'max_occurs': element.get('maxOccurs', '1'),
                        'nillable': element.get('nillable', 'false') == 'true'
                    })

        # Parse all attributes (including inherited ones)
        for attribute in complex_type.findall('.//{http://www.w3.org/2001/XMLSchema}attribute'):
            attr_name = attribute.get('name')
            attr_ref = attribute.get('ref')

            if attr_name:
                attr_info = {
                    'name': attr_name,
                    'type': attribute.get('type', 'string'),
                    'use': attribute.get('use', 'optional'),
                    'default': attribute.get('default'),
                    'fixed': attribute.get('fixed')
                }
                type_info['attributes'].append(attr_info)

                # Check for ID attribute
                if attr_name == 'id' or attribute.get('type', '').endswith(':ID'):
                    type_info['has_id_attribute'] = True
            elif attr_ref:
                # Reference to global attribute
                ref_name = attr_ref.split(':')[-1] if ':' in attr_ref else attr_ref
                attr_info = {
                    'name': ref_name,
                    'type': 'reference',
                    'ref': attr_ref,
                    'use': attribute.get('use', 'optional')
                }
                type_info['attributes'].append(attr_info)

                if ref_name == 'id':
                    type_info['has_id_attribute'] = True

        # Parse attribute groups
        for attr_group in complex_type.findall('.//{http://www.w3.org/2001/XMLSchema}attributeGroup'):
            group_ref = attr_group.get('ref')
            if group_ref:
                # Reference to global attribute group
                ref_name = group_ref.split(':')[-1] if ':' in group_ref else group_ref
                type_info['attributes'].append({
                    'name': f'{ref_name}_group',
                    'type': 'attribute_group',
                    'ref': group_ref,
                    'use': 'optional'
                })

        complex_types[type_name] = type_info

    return complex_types


def _parse_associations_comprehensive(root: ET.Element, _namespaces: Dict[str, str],
                                    complex_types: Dict[str, Dict[str, Any]],
                                    all_elements: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Parse association types that represent relationships comprehensively"""
    associations = {}

    for type_name, type_info in complex_types.items():
        # Association types typically have multiple reference elements
        references = []

        for element in type_info.get('elements', []):
            element_name = element['name']

            # Check for various reference patterns
            if (element_name.endswith('Ref') or
                element_name.endswith('Reference') or
                element.get('type') == 'reference' or
                element_name.endswith('ID')):

                # This is likely a reference to another entity
                if element_name.endswith('Ref'):
                    target_type = element_name.replace('Ref', '')
                elif element_name.endswith('Reference'):
                    target_type = element_name.replace('Reference', '')
                elif element_name.endswith('ID'):
                    target_type = element_name.replace('ID', '')
                else:
                    target_type = element_name

                references.append({
                    'name': element_name,
                    'target_type': target_type,
                    'type': element.get('type', 'string'),
                    'min_occurs': element.get('min_occurs', '1'),
                    'max_occurs': element.get('max_occurs', '1')
                })

        # If we have 2+ references, this is likely an association
        if len(references) >= 2:
            associations[type_name] = {
                'references': references,
                'elements': type_info.get('elements', []),
                'attributes': type_info.get('attributes', [])
            }
        # Also check for types that explicitly represent associations/relationships
        elif ('association' in type_name.lower() or
              'relationship' in type_name.lower() or
              'link' in type_name.lower()):
            associations[type_name] = {
                'references': references,
                'elements': type_info.get('elements', []),
                'attributes': type_info.get('attributes', []),
                'is_explicit_association': True
            }

    return associations


def _element_name_to_label(element_name: str) -> str:
    """Convert XSD element name to Neo4j node label"""
    # Convert to proper case
    return element_name


def _parse_complex_types(root: ET.Element, _namespaces: Dict[str, str]) -> Dict[str, Dict[str, Any]]:
    """Parse complex types from XSD"""
    complex_types = {}

    # Find all complexType elements
    for complex_type in root.findall('.//{http://www.w3.org/2001/XMLSchema}complexType'):
        type_name = complex_type.get('name')
        if not type_name:
            continue

        type_info = {
            'elements': [],
            'attributes': [],
            'has_id_attribute': False
        }

        # Parse sequence elements
        sequence = complex_type.find('.//{http://www.w3.org/2001/XMLSchema}sequence')
        if sequence is not None:
            for element in sequence.findall('.//{http://www.w3.org/2001/XMLSchema}element'):
                element_name = element.get('name')
                element_type = element.get('type', 'string')
                if element_name:
                    type_info['elements'].append({
                        'name': element_name,
                        'type': element_type,
                        'min_occurs': element.get('minOccurs', '1'),
                        'max_occurs': element.get('maxOccurs', '1')
                    })

        # Parse attributes
        for attribute in complex_type.findall('.//{http://www.w3.org/2001/XMLSchema}attribute'):
            attr_name = attribute.get('name')
            attr_type = attribute.get('type', 'string')
            if attr_name:
                type_info['attributes'].append({
                    'name': attr_name,
                    'type': attr_type,
                    'use': attribute.get('use', 'optional')
                })

                # Check for ID attribute
                if attr_name == 'id':
                    type_info['has_id_attribute'] = True

        complex_types[type_name] = type_info

    return complex_types


def _parse_associations(_root: ET.Element, _namespaces: Dict[str, str], complex_types: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Parse association types that represent relationships"""
    associations = {}

    for type_name, type_info in complex_types.items():
        # Association types typically have multiple reference elements
        references = []

        for element in type_info.get('elements', []):
            if element['name'].endswith('Ref'):
                # This is likely a reference to another entity
                target_type = element['name'].replace('Ref', '')
                references.append({
                    'name': element['name'],
                    'target_type': target_type
                })

        # If we have 2+ references, this is likely an association
        if len(references) >= 2:
            associations[type_name] = {
                'references': references,
                'elements': type_info.get('elements', [])
            }

    return associations


def _is_association_type(type_name: str, associations: Dict[str, Dict[str, Any]]) -> bool:
    """Check if a type represents an association/relationship"""
    return type_name in associations


def _type_name_to_label(type_name: str) -> str:
    """Convert XSD type name to Neo4j node label"""
    # Remove 'Type' suffix if present
    if type_name.endswith('Type'):
        type_name = type_name[:-4]

    # Convert to proper case
    return type_name


def _element_name_to_property(element_name: str) -> str:
    """Convert XSD element name to graph property name"""
    # Convert to camelCase
    return element_name[0].lower() + element_name[1:] if element_name else element_name


def _association_to_relationship_type(assoc_name: str) -> str:
    """Convert association name to relationship type"""
    # Remove 'Type' suffix and convert to UPPER_CASE
    if assoc_name.endswith('Type'):
        assoc_name = assoc_name[:-4]

    # Convert camelCase to UPPER_SNAKE_CASE
    import re
    return re.sub(r'(?<!^)(?=[A-Z])', '_', assoc_name).upper()