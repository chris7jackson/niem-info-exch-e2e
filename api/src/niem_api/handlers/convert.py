#!/usr/bin/env python3
"""
Handlers for NIEM format conversion operations.

Handles requests for XML to JSON conversion using the NIEMTran tool.
"""

import logging
from typing import Dict, Any

from fastapi import HTTPException, UploadFile
from minio import Minio
from minio.error import S3Error

from ..services import niemtran_service
from ..clients.niemtran_client import is_niemtran_available, NIEMTranError
from ..handlers.schema import get_active_schema_id, get_schema_metadata
from ..clients.s3_client import download_file

logger = logging.getLogger(__name__)


async def _download_schema_files_for_validation(s3: Minio, schema_id: str) -> str:
    """Download schema XSD files from S3 to temporary directory.

    Reuses the same pattern as ingest.py for consistency.

    Args:
        s3: MinIO client
        schema_id: Schema ID

    Returns:
        Path to temporary directory containing schema files
    """
    import tempfile
    from pathlib import Path

    temp_dir = tempfile.mkdtemp(prefix="conversion_validation_")
    logger.info(f"Downloading schema files for {schema_id} to {temp_dir}")

    try:
        # List all objects in the schema folder
        objects = s3.list_objects("niem-schemas", prefix=f"{schema_id}/source/", recursive=True)

        xsd_count = 0
        for obj in objects:
            if obj.object_name.endswith('.xsd'):
                # Download the file
                content = await download_file(s3, "niem-schemas", obj.object_name)

                # Create subdirectories if needed
                relative_path = obj.object_name.replace(f"{schema_id}/source/", "")
                target_path = Path(temp_dir) / relative_path
                target_path.parent.mkdir(parents=True, exist_ok=True)

                # Write file
                with open(target_path, 'wb') as f:
                    f.write(content)

                xsd_count += 1
                logger.debug(f"Downloaded schema file: {relative_path}")

        logger.info(f"Downloaded {xsd_count} XSD schema files")
        return temp_dir

    except Exception as e:
        logger.error(f"Failed to download schema files: {e}")
        # Clean up on error
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise HTTPException(status_code=500, detail=f"Failed to download schema files: {str(e)}")


async def handle_xml_to_json_conversion(
    file: UploadFile,
    s3: Minio,
    schema_id: str = None,
    include_context: bool = False,
    context_uri: str = None
) -> Dict[str, Any]:
    """
    Handle XML to JSON conversion request.

    This handler orchestrates the conversion process:
    1. Validates that NIEMTran tool is available
    2. Determines which schema to use (provided or active)
    3. Downloads the CMF file from S3
    4. Validates the XML content
    5. Performs the conversion using NIEMTran
    6. Returns the JSON result

    Args:
        file: Uploaded XML file
        s3: MinIO client
        schema_id: Optional schema ID (uses active schema if not provided)
        include_context: Include complete @context in result
        context_uri: Optional URI to include as "@context:" URI pair

    Returns:
        Dictionary with:
        - success: bool - conversion status
        - json_content: dict - parsed JSON (if successful)
        - json_string: str - formatted JSON string (if successful)
        - message: str - status message
        - schema_id: str - schema ID used for conversion
        - schema_filename: str - CMF filename used
        - error: str - error message (if failed)

    Raises:
        HTTPException: For various error conditions (tool unavailable, schema not found, etc.)
    """
    logger.info(f"Starting XML to JSON conversion for file: {file.filename}")

    schema_dir = None

    try:
        # Step 1: Check if NIEMTran tool is available
        if not is_niemtran_available():
            logger.error("NIEMTran tool is not available")
            raise HTTPException(
                status_code=503,
                detail="XML to JSON conversion is not available on this server. NIEMTran tool is not installed."
            )

        # Step 2: Determine which schema to use
        if schema_id is None:
            # Use active schema
            schema_id = get_active_schema_id(s3)
            if not schema_id:
                logger.error("No active schema found and no schema_id provided")
                raise HTTPException(
                    status_code=400,
                    detail="No active schema found. Please upload and activate a schema first, or specify a schema_id."
                )
            logger.info(f"Using active schema: {schema_id}")
        else:
            logger.info(f"Using specified schema: {schema_id}")

        # Step 3: Get schema metadata
        schema_metadata = get_schema_metadata(s3, schema_id)
        if not schema_metadata:
            logger.error(f"Schema not found: {schema_id}")
            raise HTTPException(
                status_code=404,
                detail=f"Schema '{schema_id}' not found"
            )

        # Step 4: Get CMF filename from metadata
        cmf_filename = schema_metadata.get("cmf_filename")
        if not cmf_filename:
            logger.error(f"No CMF file found for schema: {schema_id}")
            raise HTTPException(
                status_code=400,
                detail=f"Schema '{schema_id}' does not have a CMF file. CMF conversion may have failed during schema upload."
            )

        # Step 5: Download CMF file from S3
        try:
            logger.info(f"Downloading CMF file from S3: {schema_id}/{cmf_filename}")
            cmf_content_bytes = await download_file(s3, "niem-schemas", f"{schema_id}/{cmf_filename}")
            cmf_content = cmf_content_bytes.decode("utf-8")
            logger.info(f"Successfully downloaded CMF file ({len(cmf_content)} bytes)")
        except S3Error as e:
            logger.error(f"Failed to download CMF file from S3: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to retrieve CMF file for schema '{schema_id}'"
            )

        # Step 6: Download XSD schema files to temporary directory
        schema_dir = await _download_schema_files_for_validation(s3, schema_id)

        # Step 7: Read XML content
        try:
            xml_content = await file.read()
            logger.info(f"Read XML file: {file.filename} ({len(xml_content)} bytes)")
        except Exception as e:
            logger.error(f"Failed to read XML file: {e}")
            raise HTTPException(
                status_code=400,
                detail=f"Failed to read XML file: {str(e)}"
            )

        # Step 8: Validate XML against XSD schemas using CMF xval
        # Use the same validation function as ingest.py for consistency
        from pathlib import Path
        xml_file = Path(schema_dir) / file.filename
        try:
            xml_file.write_bytes(xml_content)

            # Import validation function from ingest
            from . import ingest
            ingest._validate_xml_content(xml_content.decode('utf-8'), schema_dir, file.filename)

            logger.info("XML validation passed")
        except HTTPException as e:
            # Validation failed - extract error details
            if hasattr(e, 'detail') and isinstance(e.detail, dict):
                validation_result = e.detail.get('validation_result', {})
                error_count = len(validation_result.get('errors', []))
                warning_count = len(validation_result.get('warnings', []))

                # Format error messages
                error_messages = []
                for error in validation_result.get('errors', [])[:5]:  # First 5 errors
                    loc = f"{error.get('file', 'unknown')}"
                    if error.get('line'):
                        loc += f":{error['line']}"
                    error_messages.append(f"{loc}: {error.get('message', 'Unknown error')}")

                detail = {
                    "message": e.detail.get('message', 'XML validation failed'),
                    "error_count": error_count,
                    "warning_count": warning_count,
                    "errors": error_messages
                }

                raise HTTPException(status_code=400, detail=detail)
            else:
                raise
        finally:
            # Clean up the XML file
            if xml_file.exists():
                xml_file.unlink()

        # Step 9: Perform conversion
        logger.info("Starting NIEMTran conversion")
        conversion_result = await niemtran_service.convert_xml_to_json(
            xml_content=xml_content,
            cmf_content=cmf_content,
            include_context=include_context,
            context_uri=context_uri
        )

        if not conversion_result["success"]:
            logger.error(f"Conversion failed: {conversion_result.get('error')}")
            raise HTTPException(
                status_code=400,
                detail={
                    "message": "XML to JSON conversion failed",
                    "error": conversion_result.get("error"),
                    "stderr": conversion_result.get("stderr"),
                    "stdout": conversion_result.get("stdout")
                }
            )

        logger.info("Conversion successful")

        # Add metadata to result
        conversion_result["schema_id"] = schema_id
        conversion_result["schema_filename"] = cmf_filename
        conversion_result["source_filename"] = file.filename

        return conversion_result

    except NIEMTranError as e:
        logger.error(f"NIEMTran error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Conversion tool error: {str(e)}"
        )
    except HTTPException:
        # Re-raise HTTPException as-is
        raise
    except Exception as e:
        logger.error(f"Unexpected error during conversion: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Unexpected error during conversion: {str(e)}"
        )

    finally:
        # Clean up schema directory
        if schema_dir:
            import shutil
            try:
                shutil.rmtree(schema_dir, ignore_errors=True)
                logger.info(f"Cleaned up schema directory: {schema_dir}")
            except Exception as e:
                logger.warning(f"Failed to clean up schema directory: {e}")
