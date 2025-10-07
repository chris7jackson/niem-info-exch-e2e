# API Architecture Documentation

## Overview

The NIEM Information Exchange API follows a **layered architecture** pattern that separates concerns into three main layers:

```
┌─────────────────────────────────────────────────────────────┐
│                         main.py                              │
│              (FastAPI routes & HTTP layer)                   │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                        handlers/                             │
│         (Request/Response orchestration logic)               │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                        services/                             │
│        (Business logic & external integrations)              │
└─────────────────────────────────────────────────────────────┘
```

## Layer 1: `main.py` - HTTP/Routing Layer

**Location**: `/api/src/niem_api/main.py`

**Purpose**: Define HTTP endpoints, handle routing, middleware, and dependency injection.

**Responsibilities**:
- ✅ Define FastAPI routes (`@app.post`, `@app.get`, etc.)
- ✅ HTTP request/response handling
- ✅ Middleware configuration (CORS, authentication)
- ✅ Dependency injection (database connections, S3 clients)
- ✅ Application lifecycle management (startup/shutdown)
- ✅ Input validation (via Pydantic models)
- ❌ Business logic (delegated to handlers)
- ❌ Direct database/S3 operations (delegated to services)

### Key Concepts

#### Application Lifecycle
```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    # Startup
    setup_logging()
    logger.info("Starting NIEM API service")
    await startup_tasks()  # Initialize MinIO, CMF tool

    yield

    # Shutdown
    logger.info("Shutting down NIEM API service")
```

#### Route Definition Pattern
```python
@app.post("/api/ingest/xml")
async def ingest_xml(
    files: List[UploadFile] = File(...),      # Request body
    schema_id: str = Form(None),              # Optional form parameter
    token: str = Depends(verify_token),       # Authentication
    s3=Depends(get_s3_client)                 # Dependency injection
):
    """Ingest XML files directly to Neo4j"""
    from .handlers.ingest import handle_xml_ingest
    return await handle_xml_ingest(files, s3, schema_id)  # Delegate to handler
```

#### Middleware Configuration
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # UI origin
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### Example Routes

| Route | Method | Handler | Purpose |
|-------|--------|---------|---------|
| `/api/schema/xsd` | POST | `handle_schema_upload` | Upload XSD schemas |
| `/api/ingest/xml` | POST | `handle_xml_ingest` | Ingest XML files to graph |
| `/api/graph/query` | POST | `execute_cypher_query` | Execute graph queries |
| `/api/admin/reset` | POST | `handle_reset` | Reset system components |

### Key Pattern: Thin Controllers

**main.py routes should be thin** - they extract parameters, handle HTTP concerns, then immediately delegate to handlers:

```python
# ✅ GOOD: Thin route, delegates to handler
@app.post("/api/ingest/xml")
async def ingest_xml(files: List[UploadFile], s3=Depends(get_s3_client)):
    from .handlers.ingest import handle_xml_ingest
    return await handle_xml_ingest(files, s3)

# ❌ BAD: Business logic in route
@app.post("/api/ingest/xml")
async def ingest_xml(files: List[UploadFile]):
    # Don't do validation, processing, database operations here!
    for file in files:
        content = await file.read()
        # ... complex processing logic ...
    return result
```

## Layer 2: `handlers/` - Orchestration Layer

**Location**: `/api/src/niem_api/handlers/`

**Purpose**: Orchestrate business operations by coordinating multiple services and handling request/response transformation.

**Responsibilities**:
- ✅ Multi-step workflow orchestration
- ✅ Calling multiple services in sequence
- ✅ Request validation and transformation
- ✅ Response formatting
- ✅ Error handling and HTTP exception mapping
- ✅ Transaction coordination
- ❌ Low-level database queries (use services)
- ❌ Direct external API calls (use services)

### Handler Files

#### `handlers/ingest.py`

**Purpose**: Orchestrate XML/JSON ingestion into Neo4j graph database.

**Key Functions**:

##### `handle_xml_ingest(files, s3, schema_id) → Dict[str, Any]`
**Orchestrates the complete XML ingestion workflow:**

```python
async def handle_xml_ingest(files, s3, schema_id=None):
    """Handle XML file ingestion to Neo4j"""

    # Step 1: Get schema ID (use provided or get active)
    schema_id = await _get_schema_id(s3, schema_id)

    # Step 2: Load mapping specification
    mapping = _load_mapping_from_s3(s3, schema_id)

    # Step 3: Download schema files for validation
    schema_dir = await _download_schema_files(s3, schema_id)

    # Step 4: Process each file
    neo4j_client = Neo4jClient()
    results = []
    for file in files:
        result, statements_executed = await _process_single_file(
            file, mapping, neo4j_client, s3, schema_dir
        )
        results.append(result)

    # Step 5: Return summary
    return {
        "schema_id": schema_id,
        "files_processed": len(files),
        "total_statements_executed": total_statements_executed,
        "results": results
    }
```

**Private Helper Functions** (prefixed with `_`):
- `_get_schema_id()` - Get schema ID from request or active schema
- `_load_mapping_from_s3()` - Load mapping YAML from S3
- `_download_schema_files()` - Download XSD schemas for validation
- `_validate_xml_content()` - Validate XML against XSD using CMF tool
- `_process_single_file()` - Process one XML file end-to-end
- `_generate_cypher_from_xml()` - Call service to convert XML → Cypher
- `_execute_cypher_statements()` - Execute Cypher in Neo4j
- `_store_processed_files()` - Store XML and Cypher in S3
- `_create_success_result()` - Format success response
- `_create_error_result()` - Format error response

**Key Pattern**: The handler breaks complex operations into clear, testable steps.

#### `handlers/schema.py`

**Purpose**: Manage NIEM schema uploads, validation, and activation.

**Key Functions**:

##### `handle_schema_upload(files, s3, skip_niem_resolution) → SchemaResponse`
**Multi-step schema processing workflow:**

```python
async def handle_schema_upload(files, s3, skip_niem_resolution=False):
    """Handle XSD schema upload and validation"""

    # Step 1: Validate and read files
    file_contents, primary_file, schema_id = await _validate_and_read_files(files)

    # Step 2: Validate NIEM NDR conformance
    niem_ndr_report = await _validate_niem_ndr(primary_content, primary_file.filename)

    # Step 3: Convert to CMF and JSON Schema
    cmf_result, json_schema_result = await _convert_to_cmf(
        file_contents, primary_file, primary_content, skip_niem_resolution
    )

    # Step 4: Store all schema files in S3
    await _store_schema_files(s3, schema_id, file_contents, cmf_result, json_schema_result)

    # Step 5: Generate and store mapping YAML
    await _generate_and_store_mapping(s3, schema_id, cmf_result)

    # Step 6: Store metadata and mark as active
    await _store_schema_metadata(s3, schema_id, primary_file, file_contents, timestamp)

    return SchemaResponse(schema_id=schema_id, niem_ndr_report=niem_ndr_report, is_active=True)
```

##### `get_all_schemas(s3) → List[Dict]`
**Retrieve all uploaded schemas:**

```python
async def get_all_schemas(s3: Minio):
    """Get all schemas from MinIO storage"""
    schemas = []
    active_schema_id = get_active_schema_id(s3)  # Service call

    objects = s3.list_objects("niem-schemas", recursive=False)
    for obj in objects:
        if obj.object_name.endswith('/'):
            schema_dir = obj.object_name.rstrip('/')
            metadata = json.loads(s3.get_object(...).read())
            metadata["active"] = (metadata["schema_id"] == active_schema_id)
            schemas.append(metadata)

    return sorted(schemas, key=lambda x: x.get("uploaded_at", ""), reverse=True)
```

#### `handlers/graph.py`

**Purpose**: Execute graph queries and retrieve graph data.

**Key Functions**:

##### `execute_cypher_query(cypher_query) → Dict[str, Any]`
**Execute arbitrary Cypher query:**

```python
def execute_cypher_query(cypher_query: str) -> Dict[str, Any]:
    """Execute a Cypher query and return structured graph data"""
    client = get_neo4j_client()  # Service dependency
    try:
        return client.query_graph(cypher_query)  # Delegate to service
    except Exception as e:
        logger.error(f"Error executing Cypher query: {e}")
        raise
```

##### `get_full_graph(limit) → Dict[str, Any]`
**Get complete graph structure:**

```python
def get_full_graph(limit: int = 1000) -> Dict[str, Any]:
    """Get the complete graph structure with all nodes and relationships"""
    cypher_query = f"""
    MATCH (n)
    OPTIONAL MATCH (n)-[r]-(m)
    RETURN n, r, m
    LIMIT {limit}
    """
    return execute_cypher_query(cypher_query)  # Reuse query handler
```

##### `get_database_summary() → Dict[str, Any]`
**Get database statistics:**

```python
def get_database_summary() -> Dict[str, Any]:
    """Get a comprehensive summary of the database structure"""
    client = get_neo4j_client()  # Service
    stats = client.get_stats()  # Service call
    schema = client.get_schema()  # Service call

    return {
        **stats,
        **schema,
        "summary": f"Database contains {stats['nodeCount']} nodes..."
    }
```

#### `handlers/admin.py`

**Purpose**: Administrative operations for system management.

**Key Functions**:

##### `handle_reset(request, s3) → ResetResponse`
**Orchestrate system reset:**

```python
async def handle_reset(request: ResetRequest, s3: Minio) -> ResetResponse:
    """Handle system reset"""
    counts = {}

    # Get current counts
    if request.schemas:
        counts["schemas"] = count_schemas(s3)  # Helper function
    if request.data:
        data_counts = count_data_files(s3)  # Helper function
        counts.update(data_counts)
    if request.neo4j:
        neo4j_counts = count_neo4j_objects()  # Service function
        counts.update({f"neo4j_{k}": v for k, v in neo4j_counts.items()})

    # Dry run - just return counts
    if request.dry_run:
        confirm_token = secrets.token_urlsafe(32)
        return ResetResponse(counts=counts, confirm_token=confirm_token)

    # Validate confirm token
    if not request.confirm_token:
        raise HTTPException(status_code=400, detail="confirm_token required")

    # Execute reset operations
    if request.schemas:
        reset_schemas(s3)  # Service function
    if request.data:
        reset_data_files(s3)  # Service function
    if request.neo4j:
        reset_neo4j()  # Service function

    return ResetResponse(counts=counts, message="Reset completed successfully")
```

### Handler Design Patterns

#### 1. Workflow Orchestration
Handlers coordinate multi-step processes:

```python
async def complex_operation():
    # Step 1: Validate input
    validation_result = await validate_service(data)

    # Step 2: Process data
    processed = await processing_service(validation_result)

    # Step 3: Store results
    await storage_service(processed)

    # Step 4: Notify
    await notification_service(processed)

    # Step 5: Return formatted response
    return format_response(processed)
```

#### 2. Error Handling
Handlers translate service errors into HTTP responses:

```python
try:
    result = await service_operation()
    return {"status": "success", "data": result}
except ValidationError as e:
    raise HTTPException(status_code=400, detail=f"Validation failed: {e}")
except StorageError as e:
    raise HTTPException(status_code=500, detail=f"Storage failed: {e}")
except Exception as e:
    logger.error(f"Unexpected error: {e}")
    raise HTTPException(status_code=500, detail="Internal server error")
```

#### 3. Response Formatting
Handlers format service results into consistent API responses:

```python
def _create_success_result(filename, statements_executed, stats):
    """Create success result dictionary"""
    return {
        "filename": filename,
        "status": "success",
        "statements_executed": statements_executed,
        "nodes_created": stats.get("nodes_count", 0),
        "relationships_created": stats.get("edges_count", 0) + stats.get("contains_count", 0)
    }
```

## Layer 3: `services/` - Business Logic Layer

**Location**: `/api/src/niem_api/services/`

**Purpose**: Implement core business logic, data transformations, and external system integrations.

**Responsibilities**:
- ✅ Core business logic
- ✅ Data transformation algorithms
- ✅ Database operations
- ✅ External API integrations
- ✅ File I/O operations
- ✅ Reusable utility functions
- ❌ HTTP request/response handling (that's main.py)
- ❌ Multi-service orchestration (that's handlers)

### Service Files

#### `services/import_xml_to_cypher.py`

**Purpose**: Convert NIEM XML documents into Neo4j Cypher statements.

**Core Functionality**: XML → Graph Transformation

**Key Functions**:

##### `generate_for_xml_content(xml_content, mapping_dict, filename) → Tuple[str, Dict, List, List]`
**Main entry point for XML conversion:**

```python
def generate_for_xml_content(xml_content, mapping_dict, filename="memory"):
    """Generate Cypher statements from XML content

    Returns:
        Tuple of (cypher_statements, nodes_dict, contains_list, edges_list)
    """
    # Load mapping configuration
    mapping, obj_rules, associations, references, ns_map = load_mapping_from_dict(mapping_dict)

    # Parse XML
    root = ET.fromstring(xml_content)
    xml_ns_map = parse_ns(xml_content)

    # Generate file-specific prefix for node IDs
    file_prefix = hashlib.sha1(f"{filename}_{time.time()}".encode()).hexdigest()[:8]

    # Initialize data structures
    nodes = {}  # id -> (label, qname, props_dict)
    edges = []  # (from_id, from_label, to_id, to_label, rel_type, rel_props)
    contains = []  # (parent_id, parent_label, child_id, child_label, HAS_REL)

    # Traverse XML tree and build graph structure
    def traverse(elem, parent_info=None, path_stack=None):
        # Complex traversal logic...
        pass

    # Start traversal
    traverse(root, None, [])

    # Generate Cypher statements
    cypher_statements = _generate_cypher_from_structures(nodes, contains, edges, filename)

    return cypher_statements, nodes, contains, edges
```

**Helper Functions**:
- `synth_id()` - Generate synthetic IDs for elements without explicit IDs
- `qname_from_tag()` - Extract qualified name from XML tag
- `local_from_qname()` - Extract local name from qualified name
- `get_metadata_refs()` - Extract metadata reference IDs
- `collect_scalar_setters()` - Extract scalar properties from elements
- `build_refs_index()` - Index reference rules by owner object
- `build_assoc_index()` - Index association rules by qualified name

**Algorithm Overview**:

```
1. Parse XML and mapping
2. Generate unique file prefix
3. Traverse XML tree recursively:
   a. For each element:
      - Determine if it should be a node (has ID, mapped, has metadata refs)
      - Generate node ID (explicit, URI reference, or synthetic)
      - Create node entry
      - Create containment edge to parent
      - Process metadata references
      - Handle role-based relationships (structures:uri)
      - Process reference edges from mapping
   b. Special cases:
      - Skip reference-only elements (xsi:nil + structures:ref)
      - Handle associations as both edges and nodes
      - Skip root wrapper if not mapped
4. Resolve placeholder labels
5. Generate Cypher MERGE statements
6. Return Cypher + metadata
```

#### `services/neo4j_client.py`

**Purpose**: Neo4j database connection and query execution.

**Key Functions**:

##### `query_graph(cypher_query, parameters) → Dict[str, Any]`
**Execute Cypher and return structured graph data:**

```python
def query_graph(self, cypher_query: str, parameters: Optional[Dict] = None):
    """Execute a Cypher query and return structured graph data"""
    with self.driver.session() as session:
        result = session.run(cypher_query, parameters or {})

        nodes = {}
        relationships = {}

        # Extract nodes and relationships from result
        for record in result:
            for key, value in record.items():
                self._extract_graph_elements(value, nodes, relationships)

        # Return structured format
        return {
            "nodes": list(nodes.values()),
            "relationships": list(relationships.values()),
            "metadata": {
                "nodeLabels": sorted(list(all_labels)),
                "relationshipTypes": sorted(list(all_rel_types)),
                "nodeCount": len(nodes),
                "relationshipCount": len(relationships)
            }
        }
```

##### `_extract_graph_elements(value, nodes, relationships)`
**Recursively extract Neo4j graph elements:**

```python
def _extract_graph_elements(self, value: Any, nodes: Dict, relationships: Dict):
    """Extract graph elements from Neo4j result values"""
    if isinstance(value, Node):
        node_id = str(value.id)
        if node_id not in nodes:
            nodes[node_id] = {
                "id": node_id,
                "label": list(value.labels)[0],
                "labels": list(value.labels),
                "properties": dict(value.items())
            }

    elif isinstance(value, Relationship):
        rel_id = str(value.id)
        if rel_id not in relationships:
            relationships[rel_id] = {
                "id": rel_id,
                "type": value.type,
                "startNode": str(value.start_node.id),
                "endNode": str(value.end_node.id),
                "properties": dict(value.items())
            }
```

#### `services/cmf_tool.py`

**Purpose**: Integration with CMF (Common Model Format) command-line tool.

**Key Functions**:

##### `run_cmf_command(cmd, working_dir) → Dict[str, Any]`
**Execute CMF tool commands:**

```python
def run_cmf_command(cmd: List[str], working_dir: str = None) -> Dict[str, Any]:
    """Run a CMF tool command

    Args:
        cmd: Command and arguments as list (e.g., ['xval', '--schema', 'file.xsd'])
        working_dir: Working directory for command execution

    Returns:
        {"returncode": int, "stdout": str, "stderr": str}
    """
    cmf_bin = os.path.join(CMF_DIR, "bin", "cmftool")
    full_cmd = [cmf_bin] + cmd

    result = subprocess.run(
        full_cmd,
        cwd=working_dir,
        capture_output=True,
        text=True,
        timeout=300
    )

    return {
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr
    }
```

##### `convert_xsd_to_cmf(xsd_content, schema_dir, filename) → Dict[str, Any]`
**Convert XSD schema to CMF format:**

```python
async def convert_xsd_to_cmf(xsd_content, schema_dir, filename):
    """Convert XSD to CMF using CMF tool

    Returns:
        {
            "status": "success" | "error",
            "cmf_content": str,  # If successful
            "error": str,  # If failed
            "details": List[str]  # Error details
        }
    """
    # Write XSD to temp file
    xsd_file = schema_dir / filename

    # Run: cmftool xsd2cmf --xsd file.xsd --cmf output.cmf
    cmd = ["xsd2cmf", "--xsd", str(xsd_file), "--cmf", str(cmf_file)]
    result = run_cmf_command(cmd, working_dir=schema_dir)

    if result["returncode"] == 0:
        cmf_content = cmf_file.read_text()
        return {"status": "success", "cmf_content": cmf_content}
    else:
        return {"status": "error", "error": result["stderr"], "details": [result["stdout"]]}
```

#### `services/storage.py`

**Purpose**: MinIO (S3-compatible) object storage operations.

**Key Functions**:

##### `upload_file(s3, bucket, object_name, content, content_type) → None`
**Upload file to S3:**

```python
async def upload_file(s3: Minio, bucket: str, object_name: str, content: bytes, content_type: str):
    """Upload file to MinIO bucket"""
    from io import BytesIO

    # Ensure bucket exists
    if not s3.bucket_exists(bucket):
        s3.make_bucket(bucket)

    # Upload content
    s3.put_object(
        bucket,
        object_name,
        BytesIO(content),
        length=len(content),
        content_type=content_type
    )
```

##### `list_files(s3, bucket) → List[Dict]`
**List files in bucket:**

```python
async def list_files(s3: Minio, bucket: str) -> List[Dict]:
    """List all files in a bucket"""
    if not s3.bucket_exists(bucket):
        return []

    objects = s3.list_objects(bucket, recursive=True)
    files = []

    for obj in objects:
        files.append({
            "name": obj.object_name,
            "size": obj.size,
            "last_modified": obj.last_modified.isoformat() if obj.last_modified else None,
            "content_type": obj.content_type
        })

    return files
```

#### `services/cmf_to_mapping.py`

**Purpose**: Generate mapping YAML from CMF files.

**Key Function**:

##### `generate_mapping_from_cmf_content(cmf_content) → Dict[str, Any]`
**Parse CMF and generate mapping structure:**

```python
def generate_mapping_from_cmf_content(cmf_content: str) -> Dict[str, Any]:
    """Generate mapping dictionary from CMF content

    Returns:
        {
            "namespaces": {...},
            "objects": [...],
            "associations": [...],
            "references": [...],
            "augmentations": [...],
            "polymorphism": {...}
        }
    """
    # Parse CMF XML
    cmf_root = ET.fromstring(cmf_content)

    # Extract namespaces
    namespaces = extract_namespaces(cmf_root)

    # Extract object types
    objects = extract_object_types(cmf_root, namespaces)

    # Extract associations
    associations = extract_associations(cmf_root, namespaces)

    # Build mapping structure
    return {
        "namespaces": namespaces,
        "objects": objects,
        "associations": associations,
        "references": [],
        "augmentations": [],
        "polymorphism": {
            "strategy": "extraLabel",
            "store_actual_type_property": "xsiType"
        }
    }
```

#### `services/niem_dependency_resolver.py`

**Purpose**: Resolve NIEM schema dependencies and perform tree-shaking.

**Key Function**:

##### `resolve_niem_schema_dependencies(file_contents, resolved_dir) → Dict[str, str]`
**Copy required NIEM schemas to resolved directory:**

```python
def resolve_niem_schema_dependencies(file_contents: Dict[str, str], resolved_dir: Path) -> Dict[str, str]:
    """Resolve NIEM schema dependencies

    Args:
        file_contents: {filename: content} for uploaded schemas
        resolved_dir: Directory to copy NIEM schemas to

    Returns:
        {relative_path: source_path} for copied NIEM schemas
    """
    copied_files = {}
    required_namespaces = extract_imported_namespaces(file_contents)

    niem_base_path = Path("/app/third_party/niem-xsd")

    for namespace in required_namespaces:
        if is_niem_namespace(namespace):
            schema_file = find_niem_schema_for_namespace(namespace, niem_base_path)
            if schema_file:
                # Copy to resolved directory
                relative_path = copy_to_resolved_dir(schema_file, resolved_dir)
                copied_files[relative_path] = str(schema_file)

    return copied_files
```

#### `services/validate_mapping_coverage.py`

**Purpose**: Validate that mapping covers all CMF elements.

**Key Function**:

##### `validate_mapping_coverage_from_data(cmf_content, mapping_dict) → Dict[str, Any]`
**Check mapping coverage:**

```python
def validate_mapping_coverage_from_data(cmf_content: str, mapping_dict: Dict) -> Dict:
    """Validate mapping coverage against CMF

    Returns:
        {
            "coverage": {
                "objecttypes_total": int,
                "objecttypes_mapped": int,
                "unmapped_objects_advisory": [...]
            },
            "consistency": {
                "missing_cardinalities": {...},
                "bad_endpoints": [...]
            },
            "summary": {
                "overall_coverage_percentage": float,
                "has_critical_issues": bool
            }
        }
    """
    # Parse CMF to extract all object types
    cmf_root = ET.fromstring(cmf_content)
    all_objects = extract_all_object_types(cmf_root)

    # Check which are mapped
    mapped_qnames = {obj["qname"] for obj in mapping_dict.get("objects", [])}
    unmapped = [obj for obj in all_objects if obj not in mapped_qnames]

    coverage_percentage = (len(mapped_qnames) / len(all_objects)) * 100 if all_objects else 100

    return {
        "coverage": {
            "objecttypes_total": len(all_objects),
            "objecttypes_mapped": len(mapped_qnames),
            "unmapped_objects_advisory": unmapped
        },
        "summary": {
            "overall_coverage_percentage": coverage_percentage,
            "has_critical_issues": False
        }
    }
```

### Service Design Patterns

#### 1. Pure Functions
Services should be stateless and testable:

```python
# ✅ GOOD: Pure function, no side effects
def transform_data(input_data: Dict) -> Dict:
    """Transform input data to output format"""
    return {
        "transformed": input_data.get("value", "").upper(),
        "timestamp": time.time()
    }

# ❌ BAD: Stateful, modifies global state
global_cache = {}
def transform_data(input_data: Dict) -> Dict:
    global_cache[input_data["id"]] = input_data  # Side effect!
    return {"transformed": input_data["value"]}
```

#### 2. Dependency Injection
Services receive dependencies as parameters:

```python
# ✅ GOOD: Dependencies injected
def process_file(s3_client: Minio, neo4j_client: Neo4jClient, file_content: bytes):
    # Use injected clients
    pass

# ❌ BAD: Creates dependencies internally
def process_file(file_content: bytes):
    s3_client = Minio(...)  # Hard-coded dependency
    neo4j_client = Neo4jClient(...)  # Hard to test
    pass
```

#### 3. Single Responsibility
Each service does one thing well:

```python
# ✅ GOOD: Focused service
def validate_xml_against_xsd(xml_content: str, xsd_path: str) -> bool:
    """Validate XML content against XSD schema"""
    # ... validation logic only ...
    pass

# ❌ BAD: Does too much
def validate_and_process_and_store_xml(xml_content: str):
    # Validates XML
    # Processes XML
    # Stores in database
    # Sends notifications
    # This should be split into multiple services
    pass
```

## Data Flow Example: XML Ingestion

Let's trace a complete request through all three layers:

### 1. HTTP Request Arrives
```http
POST /api/ingest/xml
Content-Type: multipart/form-data

files: [CrashDriver1.xml]
schema_id: abc123
```

### 2. main.py (Routing Layer)
```python
@app.post("/api/ingest/xml")
async def ingest_xml(
    files: List[UploadFile] = File(...),
    schema_id: str = Form(None),
    token: str = Depends(verify_token),      # ← Authentication check
    s3=Depends(get_s3_client)                # ← Dependency injection
):
    from .handlers.ingest import handle_xml_ingest
    return await handle_xml_ingest(files, s3, schema_id)  # ← Delegate to handler
```

**Responsibilities**:
- Extract request parameters
- Inject dependencies (S3 client)
- Verify authentication
- Call handler

### 3. handlers/ingest.py (Orchestration Layer)
```python
async def handle_xml_ingest(files, s3, schema_id):
    # Step 1: Get schema
    schema_id = await _get_schema_id(s3, schema_id)  # ← Service call

    # Step 2: Load mapping
    mapping = _load_mapping_from_s3(s3, schema_id)  # ← Service call

    # Step 3: Download XSD schemas
    schema_dir = await _download_schema_files(s3, schema_id)  # ← Service call

    # Step 4: Process files
    neo4j_client = Neo4jClient()  # ← Create service client
    for file in files:
        # Step 4a: Read file
        content = await file.read()
        xml_content = content.decode('utf-8')

        # Step 4b: Validate XML
        _validate_xml_content(xml_content, schema_dir, file.filename)  # ← Service call

        # Step 4c: Generate Cypher
        cypher, stats = _generate_cypher_from_xml(xml_content, mapping, file.filename)
        # ↓ Calls services/import_xml_to_cypher.py

        # Step 4d: Execute Cypher
        _execute_cypher_statements(cypher, neo4j_client)  # ← Service call

        # Step 4e: Store files
        await _store_processed_files(s3, content, file.filename, cypher)  # ← Service call

    # Step 5: Return formatted response
    return {
        "schema_id": schema_id,
        "files_processed": len(files),
        "results": results
    }
```

**Responsibilities**:
- Orchestrate multi-step workflow
- Call multiple services
- Handle errors
- Format response

### 4. services/import_xml_to_cypher.py (Business Logic Layer)
```python
def generate_for_xml_content(xml_content, mapping_dict, filename):
    """Convert XML to Cypher"""

    # Parse XML
    root = ET.fromstring(xml_content)
    xml_ns_map = parse_ns(xml_content)  # ← Pure function

    # Generate file prefix
    file_prefix = hashlib.sha1(f"{filename}_{time.time()}".encode()).hexdigest()[:8]

    # Initialize data structures
    nodes = {}
    edges = []
    contains = []

    # Traverse XML tree (complex algorithm)
    def traverse(elem, parent_info, path_stack):
        elem_qn = qname_from_tag(elem.tag, xml_ns_map)  # ← Pure function

        # Determine node ID
        sid = elem.attrib.get(f"{{{STRUCT_NS}}}id")
        if sid:
            node_id = f"{file_prefix}_{sid}"
        else:
            node_id = synth_id(parent_id, elem_qn, ordinal_path, file_prefix)  # ← Pure function

        # Create node
        nodes[node_id] = [node_label, elem_qn, props]

        # Create containment edge
        rel = "HAS_" + re.sub(r'[^A-Za-z0-9]', '_', local_from_qname(elem_qn)).upper()
        contains.append((parent_id, parent_label, node_id, node_label, rel))

        # Recurse to children
        for child in elem:
            traverse(child, (node_id, node_label), path_stack + [elem])

    # Start traversal
    traverse(root, None, [])

    # Generate Cypher statements
    cypher_statements = _build_cypher_from_graph(nodes, contains, edges, filename)

    return cypher_statements, nodes, contains, edges
```

**Responsibilities**:
- Core XML → Graph algorithm
- Pure business logic
- No external dependencies
- Testable in isolation

### 5. Response Returns

**services** → **handlers** → **main.py** → **HTTP Response**

```json
{
  "schema_id": "abc123",
  "files_processed": 1,
  "total_statements_executed": 42,
  "results": [
    {
      "filename": "CrashDriver1.xml",
      "status": "success",
      "statements_executed": 42,
      "nodes_created": 19,
      "relationships_created": 29
    }
  ]
}
```

## Architecture Benefits

### 1. Separation of Concerns
- **main.py**: HTTP protocol, routing, authentication
- **handlers**: Workflow orchestration, error handling
- **services**: Business logic, algorithms, integrations

### 2. Testability
Each layer can be tested independently:

```python
# Test service (pure logic, no HTTP)
def test_generate_cypher():
    xml = "<root>...</root>"
    mapping = {"objects": [...]}
    cypher, nodes, contains, edges = generate_for_xml_content(xml, mapping, "test.xml")
    assert len(nodes) == 19
    assert "MERGE" in cypher

# Test handler (mocked services)
@mock.patch('handlers.ingest._generate_cypher_from_xml')
async def test_handle_xml_ingest(mock_generate):
    mock_generate.return_value = ("MERGE...", {"nodes_count": 19})
    result = await handle_xml_ingest(files, s3, "schema1")
    assert result["files_processed"] == 1

# Test route (integration test)
def test_ingest_xml_endpoint(client):
    response = client.post("/api/ingest/xml", files={"files": xml_file})
    assert response.status_code == 200
```

### 3. Reusability
Services can be called from multiple handlers:

```python
# Used by ingest handler
cypher = generate_for_xml_content(xml, mapping, filename)

# Could also be used by validation handler
cypher = generate_for_xml_content(xml, mapping, filename)  # Reuse!

# Or batch processing handler
for xml_file in batch:
    cypher = generate_for_xml_content(xml_file, mapping, filename)  # Reuse!
```

### 4. Maintainability
Changes are localized:

- **Change validation logic**: Edit `services/cmf_tool.py`
- **Change API response format**: Edit `handlers/ingest.py`
- **Add new endpoint**: Edit `main.py`
- **Change graph algorithm**: Edit `services/import_xml_to_cypher.py`

## Best Practices

### DO ✅

1. **main.py**: Thin controllers, just route to handlers
2. **handlers**: Orchestrate multiple services, handle errors
3. **services**: Pure business logic, no HTTP concerns
4. **Dependency Injection**: Pass dependencies as parameters
5. **Error Handling**: Catch exceptions in handlers, return HTTP errors
6. **Logging**: Log at all layers for debugging
7. **Type Hints**: Use type annotations everywhere
8. **Documentation**: Docstrings for all public functions

### DON'T ❌

1. **main.py**: Don't put business logic in routes
2. **handlers**: Don't make direct database queries (use services)
3. **services**: Don't handle HTTP requests/responses
4. **Global State**: Avoid global variables and singletons
5. **Tight Coupling**: Services shouldn't depend on handlers
6. **Mixed Concerns**: One function = one responsibility

## File Organization

```
api/src/niem_api/
├── main.py                          # FastAPI app, routes, middleware
├── core/
│   ├── auth.py                      # Authentication utilities
│   ├── dependencies.py              # Dependency injection providers
│   └── logging.py                   # Logging configuration
├── handlers/
│   ├── ingest.py                    # XML/JSON ingestion orchestration
│   ├── schema.py                    # Schema upload orchestration
│   ├── graph.py                     # Graph query orchestration
│   └── admin.py                     # Admin operations orchestration
├── services/
│   ├── import_xml_to_cypher.py      # XML → Cypher conversion
│   ├── neo4j_client.py              # Neo4j operations
│   ├── cmf_tool.py                  # CMF tool integration
│   ├── cmf_to_mapping.py            # CMF → Mapping conversion
│   ├── niem_dependency_resolver.py  # NIEM schema resolution
│   ├── validate_mapping_coverage.py # Mapping validation
│   └── storage.py                   # MinIO/S3 operations
└── models/
    └── models.py                    # Pydantic data models
```

## Summary

| Layer | Purpose | Examples | Key Pattern |
|-------|---------|----------|-------------|
| **main.py** | HTTP routing & middleware | Routes, CORS, auth | Thin controllers |
| **handlers/** | Workflow orchestration | Multi-step processes | Coordinator |
| **services/** | Business logic & integrations | Algorithms, DB ops, APIs | Pure functions |

**Remember**: Data flows **down** (main → handlers → services), responses flow **up** (services → handlers → main). Each layer has a clear responsibility and doesn't cross boundaries.
