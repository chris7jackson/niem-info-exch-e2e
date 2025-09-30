#!/usr/bin/env python3

import asyncio
import logging
import os
import time
from contextlib import asynccontextmanager
from typing import List

from fastapi import FastAPI, HTTPException, Depends, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from neo4j import GraphDatabase

from .core.dependencies import get_s3_client
from .models.models import SchemaResponse, ResetRequest
from .core.auth import verify_token
from .core.logging import setup_logging

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

        logger.info("Startup tasks completed successfully")

        # TODO potentially, fetch all third party references. i.e. niem open reference xsd schemas. niem cmftool, niem naming design rules. Or document how to update. 

    except Exception as e:
        logger.error(f"Startup tasks failed: {e}")
        raise


app = FastAPI(
    title="NIEM Information Exchange API",
    description="API for managing NIEM schemas and data ingestion",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # UI origin
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/healthz")
async def health_check():
    """Liveness probe - checks if application is alive and can serve requests"""
    # If we can execute this code, the app is alive
    current_time = time.time()
    return {
        "status": "healthy",
        "timestamp": current_time,
        "uptime": current_time - _app_start_time
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
        raise HTTPException(status_code=503, detail={"status": "not_ready"})


  

# Schema Management Routes

@app.post("/api/schema/xsd", response_model=SchemaResponse)
async def upload_schema(
    files: List[UploadFile] = File(...),
    skip_niem_resolution: bool = Form(False),
    token: str = Depends(verify_token),
    s3=Depends(get_s3_client)
):
    """Upload and validate XSD schema(s) - supports multiple related XSD files

    Args:
        files: XSD schema files to upload
        skip_niem_resolution: If True, only use uploaded files without NIEM dependency resolution
        token: Authentication token
        s3: MinIO client dependency
    """
    from .handlers.schema import handle_schema_upload
    return await handle_schema_upload(files, s3, skip_niem_resolution)


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
    return await get_all_schemas(s3)


# Data Ingestion Routes

@app.post("/api/ingest/xml")
async def ingest_xml(
    files: List[UploadFile] = File(...),
    schema_id: str = Form(None),  # Optional schema selection
    token: str = Depends(verify_token),
    s3=Depends(get_s3_client)
):
    """Ingest XML files directly to Neo4j"""
    from .handlers.ingest import handle_xml_ingest
    return await handle_xml_ingest(files, s3, schema_id)


@app.post("/api/ingest/json")
async def ingest_json(
    files: List[UploadFile] = File(...),
    schema_id: str = Form(None),  # Optional schema selection
    token: str = Depends(verify_token),
    s3=Depends(get_s3_client)
):
    """Ingest JSON files directly to Neo4j"""
    from .handlers.ingest import handle_json_ingest
    return await handle_json_ingest(files, schema_id)


@app.get("/api/ingest/files")
async def get_uploaded_files(
    token: str = Depends(verify_token),
    s3=Depends(get_s3_client)
):
    """Get list of uploaded data files"""
    from .handlers.ingest import handle_get_uploaded_files
    return await handle_get_uploaded_files(s3)


# Admin Routes

@app.post("/api/admin/reset")
async def reset_system(
    request: ResetRequest,
    token: str = Depends(verify_token),
    s3=Depends(get_s3_client)
):
    """Reset system components"""
    from .handlers.admin import handle_reset
    return await handle_reset(request, s3)


@app.post("/api/admin/graph-schema/configure")
async def configure_graph_schema(
    token: str = Depends(verify_token),
    s3=Depends(get_s3_client)
):
    """Configure graph schema from active mapping"""
    from .handlers.admin import handle_configure_graph_schema
    return handle_configure_graph_schema(s3)


@app.get("/api/admin/graph-schema/info")
async def get_graph_schema_info(
    token: str = Depends(verify_token)
):
    """Get current graph schema information"""
    from .handlers.admin import handle_get_graph_schema_info
    return handle_get_graph_schema_info()


@app.post("/api/admin/neo4j/clear-schema")
async def clear_neo4j_schema_endpoint(
    token: str = Depends(verify_token)
):
    """Clear Neo4j schema (indexes and constraints) only"""
    try:
        from .handlers.admin import clear_neo4j_schema

        result = clear_neo4j_schema()
        return {
            "status": "success",
            "message": "Neo4j schema cleared successfully",
            "result": result
        }

    except Exception as e:
        logger.error(f"Failed to clear Neo4j schema: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to clear Neo4j schema: {str(e)}")


@app.post("/api/admin/neo4j/clear-data")
async def clear_neo4j_data_endpoint(
    token: str = Depends(verify_token)
):
    """Clear Neo4j data (nodes and relationships) only"""
    try:
        from .handlers.admin import clear_neo4j_data

        result = clear_neo4j_data()
        return {
            "status": "success",
            "message": "Neo4j data cleared successfully",
            "result": result
        }

    except Exception as e:
        logger.error(f"Failed to clear Neo4j data: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to clear Neo4j data: {str(e)}")


@app.post("/api/admin/neo4j/clear-all")
async def clear_neo4j_all(
    token: str = Depends(verify_token)
):
    """Clear all Neo4j data and schema"""
    try:
        from .handlers.admin import reset_neo4j

        reset_neo4j()
        return {
            "status": "success",
            "message": "Neo4j cleared completely (data and schema)"
        }

    except Exception as e:
        logger.error(f"Failed to clear Neo4j: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to clear Neo4j: {str(e)}")


@app.get("/api/admin/neo4j/stats")
async def get_neo4j_stats(
    token: str = Depends(verify_token)
):
    """Get Neo4j database statistics"""
    try:
        from .handlers.admin import count_neo4j_objects

        stats = count_neo4j_objects()
        return {
            "status": "success",
            "stats": stats
        }

    except Exception as e:
        logger.error(f"Failed to get Neo4j stats: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get Neo4j stats: {str(e)}")


@app.post("/api/graph/query")
async def execute_graph_query(
    request: dict,
    token: str = Depends(verify_token)
):
    """Execute a Cypher query and return ALL graph data exactly as Neo4j provides it"""
    try:
        from .handlers.graph import execute_cypher_query

        cypher_query = request.get("query", "MATCH (n)-[r]->(m) RETURN n, r, m LIMIT 100")
        limit = request.get("limit", 100)

        # Add limit to query if not already present and user hasn't specified their own
        if "LIMIT" not in cypher_query.upper() and limit:
            cypher_query += f" LIMIT {limit}"

        result = execute_cypher_query(cypher_query)
        return {
            "status": "success",
            "data": result
        }

    except Exception as e:
        logger.error(f"Failed to execute graph query: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to execute graph query: {str(e)}")


@app.get("/api/graph/full")
async def get_full_graph(
    limit: int = 500,
    token: str = Depends(verify_token)
):
    """Get the complete graph structure with all nodes and relationships"""
    try:
        from .handlers.graph import get_full_graph

        result = get_full_graph(limit)
        return {
            "status": "success",
            "data": result
        }

    except Exception as e:
        logger.error(f"Failed to get full graph: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get full graph: {str(e)}")


@app.get("/api/graph/summary")
async def get_database_summary(
    token: str = Depends(verify_token)
):
    """Get comprehensive database summary with all node types and relationship types"""
    try:
        from .handlers.graph import get_database_summary

        result = get_database_summary()
        return {
            "status": "success",
            "data": result
        }

    except Exception as e:
        logger.error(f"Failed to get database summary: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get database summary: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)