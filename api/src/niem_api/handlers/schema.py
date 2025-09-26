#!/usr/bin/env python3

import hashlib
import json
import logging
import os
import yaml
from datetime import datetime
from typing import Dict, List, Any, Optional

import httpx
from fastapi import HTTPException, UploadFile
from minio import Minio
from minio.error import S3Error

from ..models.models import SchemaResponse, NiemNdrReport, NiemNdrViolation
from ..services.storage import upload_file
from ..services.ndr_validator import NiemNdrValidator
from ..services.cmf_tool import convert_xsd_to_cmf, convert_cmf_to_jsonschema, is_cmf_available

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

        # Convert XSD to CMF using CMF tool
        cmf_conversion_result = None
        json_schema_conversion_result = None

        if is_cmf_available():
            try:
                cmf_conversion_result = await convert_xsd_to_cmf(content.decode())
                if cmf_conversion_result.get("status") != "success":
                    logger.warning(f"XSD to CMF conversion failed: {cmf_conversion_result.get('error', 'Unknown error')}")
                    cmf_conversion_result = None
                else:
                    # Convert CMF to JSON Schema
                    try:
                        cmf_content = cmf_conversion_result["cmf_content"]
                        json_schema_conversion_result = await convert_cmf_to_jsonschema(cmf_content)
                        if json_schema_conversion_result.get("status") != "success":
                            logger.warning(f"CMF to JSON Schema conversion failed: {json_schema_conversion_result.get('error', 'Unknown error')}")
                            json_schema_conversion_result = None
                    except Exception as e:
                        logger.warning(f"CMF to JSON Schema conversion failed: {e}")
                        json_schema_conversion_result = None
            except Exception as e:
                logger.warning(f"XSD to CMF conversion failed: {e}")
                cmf_conversion_result = None
        else:
            logger.warning("CMF tool not available, proceeding without CMF conversion")

        # Store original XSD file in MinIO
        await upload_file(s3, "niem-schemas", f"{schema_id}/schema.xsd", content, "application/xml")

        # Store CMF file if conversion succeeded
        if cmf_conversion_result and cmf_conversion_result.get("cmf_content"):
            cmf_content = cmf_conversion_result["cmf_content"].encode('utf-8')
            await upload_file(s3, "niem-schemas", f"{schema_id}/schema.cmf", cmf_content, "application/xml")
            logger.info(f"Successfully converted and stored CMF file for schema {schema_id}")

        # Store JSON Schema file if conversion succeeded
        if json_schema_conversion_result and json_schema_conversion_result.get("jsonschema"):
            json_schema_content = json.dumps(json_schema_conversion_result["jsonschema"], indent=2).encode('utf-8')
            await upload_file(s3, "niem-schemas", f"{schema_id}/schema.json", json_schema_content, "application/json")
            logger.info(f"Successfully converted and stored JSON Schema file for schema {schema_id}")

        # Generate mapping YAML from CMF if CMF conversion succeeded
        if cmf_conversion_result and cmf_conversion_result.get("cmf_content"):
            try:
                import tempfile
                from ..services.cmf_to_mapping import generate_mapping_from_cmf_file

                cmf_content = cmf_conversion_result["cmf_content"]

                # Write CMF content to temporary file
                with tempfile.NamedTemporaryFile(mode='w', suffix='.cmf', delete=False) as temp_cmf:
                    temp_cmf.write(cmf_content)
                    temp_cmf_path = temp_cmf.name

                try:
                    # Generate mapping using the existing implementation
                    mapping_dict = generate_mapping_from_cmf_file(temp_cmf_path)

                    # Write mapping to temporary file for validation
                    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as temp_mapping:
                        yaml.dump(mapping_dict, temp_mapping, default_flow_style=False, indent=2)
                        temp_mapping_path = temp_mapping.name

                    try:
                        # Validate mapping coverage
                        from ..services.validate_mapping_coverage import validate_mapping_coverage
                        coverage_result = validate_mapping_coverage(temp_cmf_path, temp_mapping_path)

                        # Add coverage information to mapping
                        mapping_dict["coverage_validation"] = coverage_result

                        # Convert to YAML and store (with coverage info)
                        mapping_yaml = yaml.dump(mapping_dict, default_flow_style=False, indent=2)
                        mapping_content = mapping_yaml.encode('utf-8')
                        await upload_file(s3, "niem-schemas", f"{schema_id}/mapping.yaml", mapping_content, "application/x-yaml")

                        # Log results
                        summary = coverage_result.get("summary", {})
                        logger.info(f"Successfully generated and stored mapping YAML for schema {schema_id}")
                        logger.info(f"Mapping stats: {len(mapping_dict['namespaces'])} namespaces, {len(mapping_dict['objects'])} objects, {len(mapping_dict['associations'])} associations, {len(mapping_dict['references'])} references")
                        logger.info(f"Coverage validation: {summary.get('overall_coverage_percentage', 0):.1f}% overall coverage")

                        if summary.get("has_critical_issues", False):
                            logger.warning(f"Mapping has critical validation issues - check coverage_validation section in mapping.yaml")

                    finally:
                        # Clean up temporary mapping file
                        try:
                            os.unlink(temp_mapping_path)
                        except:
                            pass

                finally:
                    # Clean up temporary file
                    import os
                    try:
                        os.unlink(temp_cmf_path)
                    except:
                        pass

            except Exception as e:
                logger.warning(f"Failed to generate mapping YAML: {e}")
                # Continue processing even if mapping generation fails

        # Store schema metadata in MinIO
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