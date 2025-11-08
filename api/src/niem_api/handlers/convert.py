#!/usr/bin/env python3
"""
Handlers for NIEM format conversion operations.

Handles requests for XML to JSON conversion using the NIEMTran tool.
Implements batch processing with controlled concurrency as defined in
docs/adr/001-batch-processing-architecture.md
"""

import asyncio
import logging
from typing import Dict, Any, List
from pathlib import Path

from fastapi import HTTPException, UploadFile
from minio import Minio
from minio.error import S3Error

from ..services import niemtran_service
from ..clients.niemtran_client import is_niemtran_available, NIEMTranError
from ..handlers.schema import get_active_schema_id, get_schema_metadata
from ..clients.s3_client import download_file
from ..core.config import batch_config

logger = logging.getLogger(__name__)

# Shared semaphore for system-wide concurrency control
# Configurable via BATCH_MAX_CONCURRENT_OPERATIONS environment variable
# Lazy-initialized to avoid event loop issues at module load time
_conversion_semaphore = None


def _get_semaphore() -> asyncio.Semaphore:
    """Get or create the conversion semaphore."""
    global _conversion_semaphore
    if _conversion_semaphore is None:
        _conversion_semaphore = asyncio.Semaphore(batch_config.MAX_CONCURRENT_OPERATIONS)
    return _conversion_semaphore


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


def _create_success_result(
    filename: str,
    json_content: Any,
    json_string: str,
    schema_id: str,
    schema_filename: str
) -> Dict[str, Any]:
    """Create success result dictionary for a single file.

    Args:
        filename: Original XML filename
        json_content: Parsed JSON content
        json_string: Formatted JSON string
        schema_id: Schema ID used
        schema_filename: CMF filename used

    Returns:
        Success result dictionary
    """
    return {
        "filename": filename,
        "status": "success",
        "json_content": json_content,
        "json_string": json_string,
        "schema_id": schema_id,
        "schema_filename": schema_filename
    }


def _create_error_result(
    filename: str,
    error_message: str,
    validation_details: Dict[str, Any] = None
) -> Dict[str, Any]:
    """Create error result dictionary for a single file.

    Args:
        filename: Original XML filename
        error_message: Error message
        validation_details: Optional validation error details

    Returns:
        Error result dictionary
    """
    result = {
        "filename": filename,
        "status": "failed",
        "error": error_message
    }

    if validation_details:
        result["validation_details"] = validation_details

    return result


async def _convert_single_file(
    file: UploadFile,
    s3: Minio,
    schema_id: str,
    schema_metadata: Dict[str, Any],
    cmf_content: str,
    schema_dir: str,
    context_uri: str
) -> Dict[str, Any]:
    """Convert a single XML file to JSON with error handling.

    This function is called concurrently for multiple files, controlled by semaphore.
    The complete @context is always included in the conversion result.

    Args:
        file: Uploaded XML file
        s3: MinIO client
        schema_id: Schema ID to use
        schema_metadata: Schema metadata
        cmf_content: CMF file content
        schema_dir: Path to schema directory for validation
        context_uri: Optional context URI

    Returns:
        Result dictionary with success or error status
    """
    xml_file_path = None

    try:
        # Acquire semaphore to limit concurrent conversions
        async with _get_semaphore():
            logger.info(f"Starting conversion for: {file.filename}")

            # Read XML content
            try:
                xml_content = await file.read()
                logger.debug(f"Read XML file: {file.filename} ({len(xml_content)} bytes)")
            except Exception as e:
                logger.error(f"Failed to read XML file {file.filename}: {e}")
                return _create_error_result(file.filename, f"Failed to read file: {str(e)}")

            # Validate XML against XSD schemas
            xml_file_path = Path(schema_dir) / file.filename
            try:
                xml_file_path.write_bytes(xml_content)

                # Import validation function from ingest
                from . import ingest
                ingest._validate_xml_content(xml_content.decode('utf-8'), schema_dir, file.filename)

                logger.debug(f"XML validation passed for: {file.filename}")
            except HTTPException as e:
                # Validation failed - extract error details
                if hasattr(e, 'detail') and isinstance(e.detail, dict):
                    validation_result = e.detail.get('validation_result', {})
                    return _create_error_result(
                        file.filename,
                        e.detail.get('message', 'XML validation failed'),
                        validation_result
                    )
                else:
                    return _create_error_result(file.filename, str(e.detail) if hasattr(e, 'detail') else str(e))
            except Exception as e:
                logger.error(f"Validation error for {file.filename}: {e}")
                return _create_error_result(file.filename, f"Validation error: {str(e)}")

            # Perform conversion
            try:
                logger.debug(f"Starting NIEMTran conversion for: {file.filename}")
                conversion_result = await niemtran_service.convert_xml_to_json(
                    xml_content=xml_content,
                    cmf_content=cmf_content,
                    context_uri=context_uri
                )

                if not conversion_result["success"]:
                    logger.error(f"Conversion failed for {file.filename}: {conversion_result.get('error')}")
                    return _create_error_result(
                        file.filename,
                        conversion_result.get("error", "Conversion failed")
                    )

                logger.info(f"Conversion successful for: {file.filename}")

                # Get CMF filename from metadata
                cmf_filename = schema_metadata.get("cmf_filename", "unknown.cmf")

                return _create_success_result(
                    file.filename,
                    conversion_result.get("json_content"),
                    conversion_result.get("json_string"),
                    schema_id,
                    cmf_filename
                )

            except NIEMTranError as e:
                logger.error(f"NIEMTran error for {file.filename}: {e}")
                return _create_error_result(file.filename, f"Conversion tool error: {str(e)}")
            except Exception as e:
                logger.error(f"Unexpected conversion error for {file.filename}: {e}")
                return _create_error_result(file.filename, f"Unexpected error: {str(e)}")

    except asyncio.TimeoutError:
        logger.error(f"Conversion timed out for: {file.filename}")
        return _create_error_result(file.filename, "Conversion timed out")
    except Exception as e:
        logger.error(f"Unexpected error processing {file.filename}: {e}")
        return _create_error_result(file.filename, f"Unexpected error: {str(e)}")
    finally:
        # Clean up the XML file
        if xml_file_path and xml_file_path.exists():
            try:
                xml_file_path.unlink()
            except Exception as e:
                logger.warning(f"Failed to clean up XML file {xml_file_path}: {e}")


async def handle_xml_to_json_batch(
    files: List[UploadFile],
    s3: Minio,
    schema_id: str = None,
    context_uri: str = None
) -> Dict[str, Any]:
    """
    Handle batch XML to JSON conversion request.

    Implements controlled concurrency as defined in ADR-001.
    Processes multiple files with semaphore-controlled parallelism.
    The complete @context is always included in conversion results.

    Args:
        files: List of uploaded XML files
        s3: MinIO client
        schema_id: Optional schema ID (uses active schema if not provided)
        context_uri: Optional URI to include as "@context:" URI pair

    Returns:
        Dictionary with:
        - files_processed: int - total files in batch
        - successful: int - number of successful conversions
        - failed: int - number of failed conversions
        - results: List[Dict] - per-file results

    Raises:
        HTTPException: For various error conditions
    """
    logger.info(f"Starting batch conversion for {len(files)} files")

    schema_dir = None

    try:
        # Step 1: Validate batch size (configurable via BATCH_MAX_CONVERSION_FILES env var)
        max_files = batch_config.get_batch_limit('conversion')
        if len(files) > max_files:
            raise HTTPException(
                status_code=400,
                detail=f"Batch size exceeds maximum of {max_files} files. "
                       f"Received {len(files)} files. "
                       f"To increase this limit, set BATCH_MAX_CONVERSION_FILES in your .env file and restart the API service."
            )

        # Step 2: Check if NIEMTran tool is available
        if not is_niemtran_available():
            logger.error("NIEMTran tool is not available")
            raise HTTPException(
                status_code=503,
                detail="XML to JSON conversion is not available on this server. NIEMTran tool is not installed."
            )

        # Step 3: Determine which schema to use
        if schema_id is None:
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

        # Step 4: Get schema metadata
        schema_metadata = get_schema_metadata(s3, schema_id)
        if not schema_metadata:
            logger.error(f"Schema not found: {schema_id}")
            raise HTTPException(
                status_code=404,
                detail=f"Schema '{schema_id}' not found"
            )

        # Step 5: Get CMF filename from metadata
        cmf_filename = schema_metadata.get("cmf_filename")
        if not cmf_filename:
            logger.error(f"No CMF file found for schema: {schema_id}")
            raise HTTPException(
                status_code=400,
                detail=f"Schema '{schema_id}' does not have a CMF file. CMF conversion may have failed during schema upload."
            )

        # Step 6: Download CMF file from S3
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

        # Step 7: Download XSD schema files to temporary directory
        schema_dir = await _download_schema_files_for_validation(s3, schema_id)

        # Step 8: Process all files with timeout and concurrency control
        logger.info(f"Processing {len(files)} files with max {batch_config.MAX_CONCURRENT_OPERATIONS} concurrent conversions")

        # Create tasks for all files with timeout
        tasks = [
            asyncio.wait_for(
                _convert_single_file(
                    file, s3, schema_id, schema_metadata, cmf_content,
                    schema_dir, context_uri
                ),
                timeout=batch_config.OPERATION_TIMEOUT
            )
            for file in files
        ]

        # Execute all tasks (semaphore controls actual concurrency)
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results and handle any exceptions
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                # Task raised an exception
                logger.error(f"Task failed for {files[i].filename}: {result}")
                processed_results.append(_create_error_result(
                    files[i].filename,
                    f"Processing error: {str(result)}"
                ))
            else:
                processed_results.append(result)

        # Calculate summary statistics
        successful = sum(1 for r in processed_results if r["status"] == "success")
        failed = len(processed_results) - successful

        logger.info(f"Batch conversion complete: {successful} successful, {failed} failed")

        return {
            "files_processed": len(files),
            "successful": successful,
            "failed": failed,
            "results": processed_results
        }

    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        logger.error(f"Unexpected error during batch conversion: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Unexpected error during batch conversion: {str(e)}"
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
