#!/usr/bin/env python3

import logging
import os
import time
from contextlib import asynccontextmanager
from typing import List

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from neo4j import GraphDatabase

from .core.auth import verify_token
from .core.dependencies import get_s3_client
from .core.logging import setup_logging
from .models.models import EntityResolutionRequest, ResetRequest, SchemaResponse

logger = logging.getLogger(__name__)

# Application start time for uptime calculation
_app_start_time = time.time()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    # Startup
    setup_logging()
    logger.info("Starting NIEM API service")

    # Initialize MinIO buckets, etc.
    await startup_tasks()

    yield

    # Shutdown
    logger.info("Shutting down NIEM API service")



async def startup_tasks():
    """Initialize external services"""
    try:

        # Create MinIO buckets
        from .clients.s3_client import create_buckets
        await create_buckets()


        # Download and setup CMF tool
        from .clients.cmf_client import download_and_setup_cmf
        cmf_setup = await download_and_setup_cmf()
        if cmf_setup:
            logger.info("CMF tool setup completed successfully")
        else:
            logger.warning("CMF tool setup failed - some features may not be available")

        # Setup scheval tool
        from .clients.scheval_client import download_and_setup_scheval
        scheval_setup = await download_and_setup_scheval()
        if scheval_setup:
            logger.info("Scheval tool setup completed successfully")
        else:
            logger.warning("Scheval tool setup failed - schematron validation may not be available")

        # Download and setup NIEMTran tool
        from .clients.niemtran_client import download_and_setup_niemtran
        niemtran_setup = await download_and_setup_niemtran()
        if niemtran_setup:
            logger.info("NIEMTran tool setup completed successfully")
        else:
            logger.warning("NIEMTran tool setup failed - XML to JSON conversion will not be available")

        # Setup Senzing license (auto-decode if needed)
        from .core.config import senzing_config
        senzing_available = senzing_config.ensure_license()

        # Initialize Senzing configuration if available
        if senzing_available:
            try:
                from .startup.initialize_senzing import initialize_senzing
                senzing_configured = initialize_senzing()
                if senzing_configured:
                    logger.info("✓ Senzing entity resolution is available and configured")
                else:
                    logger.info("✓ Senzing license found but configuration failed - using fallback")
            except ImportError:
                logger.info("Senzing initialization module not found - using defaults")
                senzing_configured = senzing_available
        else:
            logger.info("✗ Senzing entity resolution not available (no license) - using text-based entity matching")

        logger.info("Startup tasks completed successfully")

        # TODO potentially, fetch all third party references. i.e. niem open reference xsd schemas.
        # niem cmftool, niem naming design rules. Or document how to update.

    except Exception as e:
        logger.error(f"Startup tasks failed: {e}")
        raise


app = FastAPI(
    title="NIEM Information Exchange API",
    description="API for managing NIEM schemas and data ingestion",
    version=os.getenv("APP_VERSION", "unknown"),
    lifespan=lifespan
)

# CORS middleware
allowed_origins = os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add version header middleware
@app.middleware("http")
async def add_version_header(request, call_next):
    """Add version information to response headers"""
    response = await call_next(request)
    response.headers["X-API-Version"] = os.getenv("APP_VERSION", "unknown")
    return response

@app.get("/healthz")
async def health_check():
    """Liveness probe - checks if application is alive and can serve requests"""
    # If we can execute this code, the app is alive
    current_time = time.time()
    return {
        "status": "healthy",
        "timestamp": current_time,
        "uptime": current_time - _app_start_time,
        "api_version": os.getenv("APP_VERSION", "unknown"),
        "git_commit": os.getenv("GIT_COMMIT", "unknown"),
        "build_date": os.getenv("BUILD_DATE", "unknown"),
        "niem_version": "6.0"
    }


@app.get("/readyz")
async def readiness_check():
    """Readiness probe - lightweight check for orchestrators (K8s, Docker)"""
    try:
        # Quick MinIO connectivity test
        s3_client = get_s3_client()
        list(s3_client.list_buckets())

        # Quick Neo4j connectivity test
        neo4j_uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        neo4j_user = os.getenv("NEO4J_USER", "neo4j")
        neo4j_password = os.getenv("NEO4J_PASSWORD", "password")

        driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))
        with driver.session() as session:
            session.run("RETURN 1").single()
        driver.close()

        return {"status": "ready"}

    except Exception as e:
        logger.warning(f"Readiness check failed: {e}")
        raise HTTPException(status_code=503, detail={"status": "not_ready"}) from e




# Schema Management Routes

@app.post("/api/schema/xsd", response_model=SchemaResponse)
async def upload_schema(
    files: list[UploadFile] = File(...),
    file_paths: str = Form("[]"),
    skip_niem_ndr: bool = Form(False),
    token: str = Depends(verify_token),
    s3=Depends(get_s3_client)
):
    """Upload and validate XSD schema(s) - supports multiple related XSD files.

    All required schema files (main schema, NIEM references, and custom references)
    must be uploaded together. The system validates that all dependencies are present.

    Args:
        files: XSD schema files to upload (must include all referenced schemas)
        file_paths: JSON array of relative file paths (preserves directory structure)
        skip_niem_ndr: If True, skip NIEM NDR validation
        token: Authentication token
        s3: MinIO client dependency
    """
    import json

    from .handlers.schema import handle_schema_upload

    # Parse file paths JSON
    try:
        paths = json.loads(file_paths)
    except json.JSONDecodeError:
        paths = []

    return await handle_schema_upload(files, s3, skip_niem_ndr, paths)


@app.post("/api/schema/activate/{schema_id}")
async def activate_schema(
    schema_id: str,
    token: str = Depends(verify_token),
    s3=Depends(get_s3_client)
):
    """Activate a schema"""
    from .handlers.schema import handle_schema_activation
    return await handle_schema_activation(schema_id, s3)


@app.get("/api/schema")
async def get_schemas(s3=Depends(get_s3_client)):
    """Get all schemas"""
    from .handlers.schema import get_all_schemas
    return get_all_schemas(s3)


@app.get("/api/schema/{schema_id}/file/{file_type}")
async def download_schema_file(
    schema_id: str,
    file_type: str,
    token: str = Depends(verify_token),
    s3=Depends(get_s3_client)
):
    """Download generated schema files (CMF or JSON Schema).

    Args:
        schema_id: ID of the schema
        file_type: Type of file ('cmf' or 'json')
    """
    from fastapi.responses import Response

    from .handlers.schema import handle_schema_file_download

    content, filename = await handle_schema_file_download(schema_id, file_type, s3)

    # Determine content type based on file type
    content_type = "application/json" if file_type == "json" else "application/xml"

    return Response(
        content=content,
        media_type=content_type,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        }
    )


@app.get("/api/schema/{schema_id}/element-tree")
async def get_element_tree(
    schema_id: str,
    token: str = Depends(verify_token),
    s3=Depends(get_s3_client)
):
    """Get element tree structure for graph schema design.

    Args:
        schema_id: ID of the schema

    Returns:
        Element tree with hierarchical structure and metadata
    """
    from .handlers.schema import handle_get_element_tree

    return await handle_get_element_tree(schema_id, s3)


@app.post("/api/schema/{schema_id}/apply-design")
async def apply_schema_design(
    schema_id: str,
    selections: dict[str, bool],
    token: str = Depends(verify_token),
    s3=Depends(get_s3_client)
):
    """Apply user schema design selections and regenerate mapping.yaml.

    Args:
        schema_id: ID of the schema
        selections: Dictionary mapping qnames to selection state

    Returns:
        Success message and updated schema metadata
    """
    from .handlers.schema import handle_apply_schema_design

    return await handle_apply_schema_design(schema_id, selections, s3)


# Data Ingestion Routes

@app.post("/api/ingest/xml")
async def ingest_xml(
    files: list[UploadFile] = File(...),
    schema_id: str = Form(None),  # Optional schema selection
    token: str = Depends(verify_token),
    s3=Depends(get_s3_client)
):
    """Ingest XML files directly to Neo4j"""
    from .handlers.ingest import handle_xml_ingest
    return await handle_xml_ingest(files, s3, schema_id)


@app.post("/api/ingest/json")
async def ingest_json(
    files: list[UploadFile] = File(...),
    schema_id: str = Form(None),  # Optional schema selection
    token: str = Depends(verify_token),
    s3=Depends(get_s3_client)
):
    """Ingest NIEM JSON files directly to Neo4j.

    NIEM JSON uses JSON-LD features (@context, @id, @type) with NIEM-specific conventions.
    Files are validated against JSON Schema and converted to graph using the same mapping as XML.
    """
    from .handlers.ingest import handle_json_ingest
    return await handle_json_ingest(files, s3, schema_id)


@app.get("/api/ingest/files")
async def get_uploaded_files(
    token: str = Depends(verify_token),
    s3=Depends(get_s3_client)
):
    """Get list of uploaded data files"""
    from .handlers.ingest import handle_get_uploaded_files
    return await handle_get_uploaded_files(s3)


# Conversion Routes

@app.post("/api/convert/xml-to-json")
async def convert_xml_to_json(
    files: List[UploadFile] = File(None),
    file: UploadFile = File(None),
    schema_id: str = Form(None),
    context_uri: str = Form(None),
    token: str = Depends(verify_token),
    s3=Depends(get_s3_client)
):
    """Convert NIEM XML message(s) to JSON format.

    Supports both single file and batch conversion.
    Uses the active schema's CMF model to perform the conversion.
    The resulting JSON follows NIEM JSON-LD conventions.
    The complete @context is always included in conversion results.

    This is a utility tool for demo purposes - converted JSON is returned
    but not stored or ingested.

    Batch processing uses controlled concurrency (max 3 files simultaneously)
    to prevent resource exhaustion. See docs/adr/001-batch-processing-architecture.md

    Args:
        files: Multiple XML files to convert (for batch processing)
        file: Single XML file to convert (for backward compatibility)
        schema_id: Optional schema ID (uses active schema if not provided)
        context_uri: Optional URI to include as "@context:" URI pair
        token: Authentication token
        s3: MinIO client dependency

    Returns:
        JSON response with converted content (batch format if multiple files)
    """
    from .handlers.convert import handle_xml_to_json_batch

    # Handle backward compatibility: accept either 'file' or 'files', or both
    if file and files:
        # Both provided - combine them
        files = [file] + files
    elif file:
        # Only single file - convert to list for batch handler
        files = [file]
    elif not files:
        raise HTTPException(
            status_code=400,
            detail="No files provided. Please upload at least one XML file."
        )

    return await handle_xml_to_json_batch(files, s3, schema_id, context_uri)


# Admin Routes

@app.post("/api/admin/reset")
async def reset_system(
    request: ResetRequest,
    token: str = Depends(verify_token),
    s3=Depends(get_s3_client)
):
    """Reset system components"""
    from .handlers.admin import handle_reset
    return handle_reset(request, s3)


@app.get("/api/admin/neo4j/stats")
async def get_neo4j_stats(
    token: str = Depends(verify_token)
):
    """Get Neo4j database statistics"""
    from .handlers.admin import count_neo4j_objects
    return count_neo4j_objects()


@app.post("/api/graph/query")
async def execute_graph_query(
    request: dict,
    token: str = Depends(verify_token)
):
    """Execute a Cypher query and return ALL graph data exactly as Neo4j provides it"""
    from .handlers.graph import execute_cypher_query

    cypher_query = request.get("query")
    limit = request.get("limit")  # None if not provided

    return execute_cypher_query(cypher_query, limit)


@app.get("/api/graph/full")
async def get_full_graph(
    limit: int = 500,
    token: str = Depends(verify_token)
):
    """Get the complete graph structure with all nodes and relationships"""
    from .handlers.graph import get_full_graph
    return get_full_graph(limit)


# Entity Resolution Routes

@app.post("/api/entity-resolution/run")
async def run_entity_resolution(
    request: EntityResolutionRequest,
    token: str = Depends(verify_token)
):
    """Run entity resolution on the current graph.

    Identifies duplicate entities based on name and other attributes,
    creates ResolvedEntity nodes to show which entities represent
    the same real-world entity.

    Args:
        request: Request body with selected node types to resolve (required)
    """
    from .handlers.entity_resolution import handle_run_entity_resolution

    if not request.selectedNodeTypes:
        raise HTTPException(
            status_code=400,
            detail="selectedNodeTypes is required and cannot be empty"
        )

    return handle_run_entity_resolution(request.selectedNodeTypes)


@app.get("/api/entity-resolution/node-types")
async def get_available_node_types(
    token: str = Depends(verify_token)
):
    """Get all available node types that can be resolved.

    Returns node types that have name properties and can be
    used for entity resolution.
    """
    from .handlers.entity_resolution import handle_get_available_node_types
    return handle_get_available_node_types()


@app.get("/api/entity-resolution/status")
async def get_entity_resolution_status(
    token: str = Depends(verify_token)
):
    """Get current entity resolution statistics"""
    from .handlers.entity_resolution import handle_get_resolution_status
    return handle_get_resolution_status()


@app.delete("/api/entity-resolution/reset")
async def reset_entity_resolution(
    token: str = Depends(verify_token)
):
    """Reset entity resolution by removing all ResolvedEntity nodes"""
    from .handlers.entity_resolution import handle_reset_entity_resolution
    return handle_reset_entity_resolution()


if __name__ == "__main__":
    import uvicorn
    host = os.getenv("API_HOST", "0.0.0.0")  # nosec B104
    port = int(os.getenv("API_PORT", "8000"))
    uvicorn.run(app, host=host, port=port)
