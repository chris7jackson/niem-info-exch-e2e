#!/usr/bin/env python3

import json
import logging
import tempfile
import yaml
from pathlib import Path
from typing import List, Dict, Any

from fastapi import HTTPException, UploadFile
from minio import Minio
from ..services.cmf_tool import validate_xml_with_cmf, is_cmf_available
from ..services.neo4j_client import Neo4jClient

logger = logging.getLogger(__name__)


async def handle_xml_ingest(
    files: List[UploadFile],
    s3: Minio,
    schema_id: str = None
) -> Dict[str, Any]:
    """Handle XML file ingestion to Neo4j using import_xml_to_cypher service"""
    logger.info(f"Starting XML ingestion for {len(files)} files using import_xml_to_cypher service")

    try:
        # Get schema ID (use provided or get active)
        if not schema_id:
            from .schema import get_active_schema_id
            schema_id = await get_active_schema_id(s3)
            if not schema_id:
                raise HTTPException(status_code=400, detail="No active schema found and no schema_id provided")

        # Get the mapping specification for this schema (YAML format)
        try:
            mapping_response = s3.get_object("niem-schemas", f"{schema_id}/mapping.yaml")
            mapping_content = mapping_response.read().decode('utf-8')
            mapping = yaml.safe_load(mapping_content)
            mapping_response.close()
            mapping_response.release_conn()
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to load mapping.yaml: {str(e)}")

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
        total_statements_executed = 0

        # Initialize Neo4j client
        neo4j_client = Neo4jClient()

        try:
            for file in files:
                try:
                    content = await file.read()
                    xml_content = content.decode('utf-8')

                    # Optional XSD validation (if available)
                    if xsd_content and is_cmf_available():
                        try:
                            validation_result = await validate_xml_with_cmf(xml_content, xsd_content)
                            if not validation_result.get("valid", False):
                                logger.warning(f"XML validation failed for {file.filename}: {validation_result.get('error', 'Unknown validation error')}")
                                # Continue processing even if validation fails (make it advisory)
                        except Exception as e:
                            logger.warning(f"XML validation error for {file.filename}: {e}")
                            # Continue processing

                    # Use import_xml_to_cypher service to generate Cypher
                    cypher_statements, stats = await _generate_cypher_from_xml(
                        xml_content, mapping, file.filename
                    )

                    if not cypher_statements:
                        results.append({
                            "filename": file.filename,
                            "status": "failed",
                            "error": "No Cypher statements generated from XML"
                        })
                        continue

                    # Execute Cypher statements in Neo4j
                    statements_executed = 0
                    try:
                        # Split cypher into individual statements and execute
                        statements = [stmt.strip() for stmt in cypher_statements.split(';') if stmt.strip()]
                        for statement in statements:
                            if statement and not statement.startswith('//'):
                                neo4j_client.query(statement)
                                statements_executed += 1

                        total_statements_executed += statements_executed

                        # Store XML file in MinIO after successful ingestion
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

                        results.append({
                            "filename": file.filename,
                            "status": "success",
                            "statements_executed": statements_executed,
                            "nodes_created": stats.get("nodes_count", 0),
                            "relationships_created": stats.get("edges_count", 0) + stats.get("contains_count", 0)
                        })

                        logger.info(f"Successfully ingested {file.filename}: {statements_executed} Cypher statements executed")

                    except Exception as e:
                        logger.error(f"Failed to execute Cypher for {file.filename}: {e}")
                        results.append({
                            "filename": file.filename,
                            "status": "failed",
                            "error": f"Cypher execution failed: {str(e)}"
                        })

                except Exception as e:
                    logger.error(f"Failed to process file {file.filename}: {e}")
                    results.append({
                        "filename": file.filename,
                        "status": "failed",
                        "error": str(e)
                    })

        finally:
            neo4j_client.driver.close()

        return {
            "schema_id": schema_id,
            "files_processed": len(files),
            "total_statements_executed": total_statements_executed,
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
    """Handle JSON file ingestion - currently not supported with import_xml_to_cypher service"""
    logger.warning("JSON ingestion is not currently supported with the import_xml_to_cypher service")

    return {
        "schema_id": schema_id,
        "files_processed": 0,
        "total_statements_executed": 0,
        "results": [
            {
                "filename": file.filename,
                "status": "failed",
                "error": "JSON ingestion not supported - use XML format instead"
            } for file in files
        ]
    }


async def _generate_cypher_from_xml(xml_content: str, mapping: Dict[str, Any], filename: str) -> tuple[str, Dict[str, Any]]:
    """
    Generate Cypher statements from XML content using the import_xml_to_cypher service.

    Args:
        xml_content: Raw XML content as string
        mapping: Mapping dictionary (YAML format)
        filename: Source filename for provenance

    Returns:
        Tuple of (cypher_statements, stats)
    """
    try:
        from ..services.import_xml_to_cypher import generate_for_xml, load_mapping

        # Write XML and mapping to temporary files (required by import_xml_to_cypher)
        with tempfile.NamedTemporaryFile(mode='w', suffix='.xml', delete=False) as temp_xml:
            temp_xml.write(xml_content)
            temp_xml_path = Path(temp_xml.name)

        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as temp_mapping:
            yaml.dump(mapping, temp_mapping, default_flow_style=False)
            temp_mapping_path = Path(temp_mapping.name)

        try:
            # Load mapping in the format expected by import_xml_to_cypher
            mapping_loaded, obj_rules, associations, references, ns_map = load_mapping(temp_mapping_path)

            # Generate Cypher statements
            cypher_statements, nodes, contains, edges = generate_for_xml(
                temp_xml_path, mapping_loaded, obj_rules, associations, references, ns_map
            )

            # Create stats
            stats = {
                "nodes_count": len(nodes),
                "contains_count": len(contains),
                "edges_count": len(edges),
                "filename": filename
            }

            logger.info(f"Generated Cypher for {filename}: {len(nodes)} nodes, {len(contains)} containment relationships, {len(edges)} reference/association edges")

            return cypher_statements, stats

        finally:
            # Clean up temporary files
            import os
            try:
                os.unlink(temp_xml_path)
                os.unlink(temp_mapping_path)
            except:
                pass

    except Exception as e:
        logger.error(f"Failed to generate Cypher from XML {filename}: {e}")
        raise