# External Service Integration Architecture

## Table of Contents

- [Overview](#overview)
- [Integration Map](#integration-map)
- [Neo4j Integration](#neo4j-integration)
- [MinIO Integration](#minio-integration)
- [CMFTool Integration](#cmftool-integration)
- [Senzing Integration](#senzing-integration)
- [Integration Patterns](#integration-patterns)
- [Failure Modes and Resilience](#failure-modes-and-resilience)

## Overview

The NIEM Information Exchange system integrates with four external services to provide end-to-end data processing capabilities. Each integration serves a specific architectural purpose and follows established patterns for reliability and maintainability.

### External Dependencies

| Service | Purpose | Type | Required |
|---------|---------|------|----------|
| **Neo4j** | Graph storage and querying | Database | Yes |
| **MinIO** | File and schema storage | Object Storage | Yes |
| **CMFTool** | NIEM XSD validation | External Tool | Yes |
| **Senzing** | ML-based entity resolution | ML Engine | No (Optional) |

## Integration Map

### Service Interaction Diagram

```
┌────────────────────────────────────────────────────────────────┐
│                        API Service                              │
│                                                                 │
│  ┌──────────────┐   ┌──────────────┐   ┌──────────────┐      │
│  │   Handlers   │──▶│   Services   │──▶│   Clients    │      │
│  │(Orchestrate) │   │(Business Logic)│  │(Integration) │      │
│  └──────────────┘   └──────────────┘   └──────────────┘      │
│                                              │   │   │   │     │
└──────────────────────────────────────────────┼───┼───┼───┼─────┘
                                               │   │   │   │
                        ┌──────────────────────┘   │   │   └────────────┐
                        │                          │   │                │
                        ▼                          ▼   ▼                ▼
              ┌─────────────────┐      ┌─────────────────┐   ┌─────────────────┐
              │     Neo4j       │      │     MinIO       │   │    Senzing      │
              │  Graph Database │      │ Object Storage  │   │   SDK (Opt)     │
              │                 │      │                 │   │                 │
              │ • Bolt Protocol │      │ • S3 API        │   │ • gRPC API      │
              │ • Cypher Queries│      │ • Buckets       │   │ • SQLite/PG     │
              └─────────────────┘      └─────────────────┘   └─────────────────┘
                                               │
                                               ▼
                                      ┌─────────────────┐
                                      │    CMFTool      │
                                      │  (Subprocess)   │
                                      │                 │
                                      │ • XSD Validate  │
                                      │ • Generate CMF  │
                                      └─────────────────┘
```

### Integration Layers

**Layer 1: Client Wrappers**
- Encapsulate external service APIs
- Handle connection management
- Provide consistent error handling
- Abstract away protocol details

**Layer 2: Service Logic**
- Use clients to implement business logic
- Orchestrate multiple client calls
- Transform data between formats
- Handle domain-specific operations

**Layer 3: Handler Orchestration**
- Coordinate multiple services
- Manage transactions
- Handle HTTP request/response
- Aggregate results

## Neo4j Integration

### Purpose

Graph database for storing and querying interconnected NIEM data as property graphs.

### Integration Pattern

**Client Wrapper Pattern**:
```
API Service
    ↓
Neo4j Client (wrapper)
    ↓
Neo4j Python Driver (official)
    ↓
Bolt Protocol (TCP 7687)
    ↓
Neo4j Database
```

### Key Capabilities

**1. Graph Storage**
- Execute Cypher CREATE statements
- Batch execution for performance
- Parameterized queries for security

**2. Graph Querying**
- Execute Cypher MATCH statements
- Return nodes and relationships as JSON
- Support pagination and limits

**3. Admin Operations**
- Create indexes and constraints
- Database statistics
- Delete operations (cleanup)

### Connection Management

**Connection Pool**:
```
API Service maintains connection pool
    ├─ Min connections: 1
    ├─ Max connections: 50
    ├─ Connection timeout: 30s
    └─ Idle timeout: 300s
```

**Benefits**:
- Reuse connections (performance)
- Handle concurrent requests
- Automatic reconnection on failure

### Data Format

**API → Neo4j**:
- Cypher statements (string)
- Query parameters (dict)
- Batch arrays (list of statements)

**Neo4j → API**:
- Result records (list of dicts)
- Node properties (JSON-serializable)
- Relationship properties (JSON-serializable)

### Error Handling

**Transient Errors** (Retry):
- Connection timeout → Retry with exponential backoff
- Lock timeout → Retry after delay
- Network errors → Reconnect and retry

**Permanent Errors** (Fail Fast):
- Syntax errors in Cypher → Return error to user
- Constraint violations → Return validation error
- Authentication failure → Fail startup

### Performance Considerations

**Batch Execution**:
- Execute Cypher in batches of 1000 statements
- Reduces network round-trips
- Better transaction performance

**Parameterized Queries**:
- Prevents Cypher injection
- Enables query plan caching
- Better performance

**Indexing Strategy**:
- Index on `id` (unique constraint)
- Index on `_upload_id` (for filtering)
- Index on `_schema_id` (for multi-tenant)
- Index on `qname` (for type queries)

## MinIO Integration

### Purpose

S3-compatible object storage for schemas, source files, and generated artifacts.

### Integration Pattern

**Client Wrapper Pattern**:
```
API Service
    ↓
MinIO Client (wrapper)
    ↓
MinIO Python SDK (official)
    ↓
HTTP/S3 API (port 9000)
    ↓
MinIO Server
```

### Storage Organization

**Bucket Structure**:
```
niem-schemas/
    ├── {schema_id}/
    │   ├── crashdriver.xsd        (uploaded schema)
    │   ├── schema.cmf             (generated CMF)
    │   ├── mapping.yaml           (generated mapping)
    │   ├── selections.json        (user customization)
    │   └── metadata.json          (schema metadata)
    │
niem-uploads/
    ├── {upload_id}/
    │   ├── crash01.xml            (source files)
    │   ├── crash02.xml
    │   └── manifest.json          (upload metadata)
```

**Design Rationale**:
- Schema artifacts grouped by schema_id
- Source files grouped by upload_id
- Easy to list/delete by ID
- Supports multi-tenant isolation

### Key Operations

**1. Schema Storage**
- Upload XSD files
- Store generated CMF
- Store/retrieve mapping.yaml
- Store/retrieve selections.json

**2. File Storage**
- Upload XML/JSON source files
- Stream large files (chunked upload)
- Generate presigned URLs for downloads

**3. Metadata Management**
- Store schema metadata
- Track upload history
- Version tracking

### Error Handling

**Transient Errors** (Retry):
- Network timeout → Retry 3 times
- Connection refused → Wait and retry
- Rate limiting → Exponential backoff

**Permanent Errors** (Fail Fast):
- Bucket doesn't exist → Create bucket
- Object not found → Return 404 to user
- Invalid credentials → Fail startup
- Disk full → Alert and stop uploads

### Performance Considerations

**Streaming Uploads**:
- Large files uploaded in chunks
- Progress reporting
- Memory-efficient (doesn't load entire file)

**Presigned URLs**:
- Generate temporary download links
- Offload download traffic from API
- Better scalability

## CMFTool Integration

### Purpose

NIEM XSD validation and Common Model Format (CMF) generation using official NIEM tooling.

### Integration Pattern

**Subprocess Pattern** (Not network-based):
```
API Service
    ↓
Subprocess Call (Python)
    ↓
CMFTool (Python CLI)
    ↓
File I/O (temp files)
    ↓
Return Result (stdout/stderr)
```

### Why Subprocess vs Library?

**Design Choice**: Execute CMFTool as subprocess rather than importing as library

**Rationale**:
- ✅ Isolation (CMFTool errors don't crash API)
- ✅ Timeout control (kill long-running validations)
- ✅ Version independence (can upgrade CMFTool separately)
- ✅ Resource limits (can constrain memory/CPU)
- ❌ Slower than library import (but acceptable for infrequent operations)

### Key Operations

**1. XSD Validation**
```
Input: XSD file content
Process: cmftool validate-ndr --input schema.xsd
Output: Validation results (errors, warnings)
```

**2. CMF Generation**
```
Input: XSD file content
Process: cmftool xsd-to-cmf --input schema.xsd
Output: CMF file (XML intermediate format)
```

### Workflow

```
API receives XSD
    ↓
Write to temp file
    ↓
Execute: cmftool xsd-to-cmf temp.xsd
    ↓
Read CMF from stdout
    ↓
Parse and validate CMF
    ↓
Return to caller
    ↓
Delete temp files
```

### Error Handling

**CMFTool Errors**:
- Invalid XSD → Parse errors → Return to user
- NDR violations → Validation errors → Return to user
- CMFTool crash → Log error → Return generic error
- Timeout (> 60s) → Kill process → Return timeout error

**Mitigation**:
- Timeout protection (60s limit)
- Temp file cleanup (always)
- Error message extraction from stderr
- Graceful degradation (validation optional)

### Performance Considerations

**Execution Time**:
- Small schemas (< 10 files): 1-5 seconds
- Medium schemas (10-50 files): 5-30 seconds
- Large schemas (50+ files): 30-120 seconds

**Resource Limits**:
- Memory: 2GB max (Docker container limit)
- CPU: 2 cores (Docker container limit)
- Timeout: 60 seconds (configurable)

**Optimization**:
- Skip NDR validation (optional flag)
- Cache CMF results (future enhancement)
- Parallel validation (future enhancement)

## Senzing Integration

### Purpose

Optional ML-based entity resolution for detecting duplicate entities across documents.

### Integration Pattern

**Dual-Strategy Pattern** (Optional dependency):
```
API Service
    ↓
Check: Senzing Available?
    ├─ YES → Use Senzing SDK (ML-based)
    │          ↓
    │       Senzing gRPC API
    │          ↓
    │       Senzing Engine (SQLite/PostgreSQL)
    │
    └─ NO ──→ Use Text-Based Matching (Fallback)
               ↓
            Simple name comparison
```

### Why Optional?

**Design Choice**: System works without Senzing license

**Benefits**:
- ✅ Development without license (text-based matching)
- ✅ Testing without license
- ✅ Gradual adoption (add license when needed)
- ✅ Cost flexibility (license optional)

**Fallback Strategy**:
- Text-based matching provides basic entity resolution
- Same graph structure (ResolvedEntity nodes)
- Same API interface
- Lower accuracy but functional

### Integration Flow

**With Senzing License**:
```
Extract entities from Neo4j
    ↓
Convert to Senzing format
    ↓
Add records to Senzing engine
    ↓
Query Senzing for entity resolution
    ↓
Senzing returns: ENTITY_ID, MATCH_KEY, confidence scores
    ↓
Create ResolvedEntity nodes in Neo4j
    ↓
Link entities with RESOLVED_TO relationships
```

**Without Senzing License**:
```
Extract entities from Neo4j
    ↓
Normalize names (lowercase, remove punctuation)
    ↓
Group by normalized name (match key)
    ↓
Create ResolvedEntity nodes in Neo4j
    ↓
Link entities with RESOLVED_TO relationships
```

### Data Format

**API → Senzing**:
```
{
  "DATA_SOURCE": "NIEM_GRAPH",
  "RECORD_ID": "file_P01",
  "NAME_FULL": "John Smith",
  "DATE_OF_BIRTH": "1990-01-15",
  "SSN_NUMBER": "123-45-6789"
}
```

**Senzing → API**:
```
{
  "ENTITY_ID": 12345,
  "ENTITY_NAME": "John Smith",
  "RECORDS": [
    {
      "RECORD_ID": "file1_P01",
      "MATCH_KEY": "+NAME+DOB",
      "MATCH_LEVEL": 3,
      "CONFIDENCE": 95
    }
  ]
}
```

### Error Handling

**Senzing Errors**:
- License not found → Fallback to text-based
- License expired → Fallback to text-based
- Database connection error → Fail entity resolution (user error)
- SDK import error → Fallback to text-based

**Graceful Degradation**:
- Always have working fallback (text-based matching)
- Log which mode is active
- Inform user in API response

## Integration Patterns

### Pattern 1: Client Wrapper

**Purpose**: Encapsulate external service details

**Structure**:
```
Client Wrapper (our code)
  ├─ Connection management
  ├─ Error handling
  ├─ Retry logic
  ├─ Data transformation
  └─ Logging

External SDK (third-party)
  └─ Protocol details
```

**Benefits**:
- Consistent error handling across all services
- Easy to mock for testing
- Can swap implementations
- Centralized logging

**Applied To**: Neo4j, MinIO, Senzing

### Pattern 2: Subprocess Execution

**Purpose**: Execute external tools without library coupling

**Structure**:
```
API Service
  ↓
Subprocess (isolated process)
  ├─ Timeout control
  ├─ Resource limits
  ├─ Temp file I/O
  └─ Result parsing

External Tool (CMFTool)
  └─ Command-line interface
```

**Benefits**:
- Isolation (tool crash doesn't crash API)
- Version independence
- Resource control
- Easy to replace tool

**Applied To**: CMFTool, NDR validation

### Pattern 3: Optional Dependency (Strategy Pattern)

**Purpose**: Provide functionality with or without optional service

**Structure**:
```
IF service available
  THEN use primary strategy
  ELSE use fallback strategy

Both strategies implement same interface
```

**Benefits**:
- System works in degraded mode
- Development without all services
- Gradual feature adoption
- Cost flexibility

**Applied To**: Senzing (ML vs text-based matching)

### Pattern 4: Object Storage for Config

**Purpose**: Store configuration in object storage, not database

**Rationale**:
- Schema files are large (XSD can be MB+)
- Mapping.yaml changes frequently
- Version history desired
- Binary files (XSD, CMF)

**Benefits**:
- Database stays lightweight (graph data only)
- Easy backup/restore (just copy MinIO bucket)
- Versioning support (future)
- Presigned URLs for downloads

**Applied To**: Schemas, mappings, selections, source files

## Neo4j Integration

### Service Contract

**Purpose**: Store and query graph data

**Interface**:
```
CREATE
  Input: Cypher CREATE statements + parameters
  Output: Nodes/relationships created count
  Error Modes: Syntax error, constraint violation

QUERY
  Input: Cypher MATCH statements + parameters
  Output: List of result records
  Error Modes: Syntax error, timeout

DELETE
  Input: Cypher DELETE statements + parameters
  Output: Nodes/relationships deleted count
  Error Modes: Constraint violation
```

### Design Decisions

**Decision 1: Parameterized Queries Only**

**Approach**: All queries use parameters, never string interpolation

**Why**: Prevent Cypher injection attacks

**Example**:
```
Good:
  MATCH (n {id: $id}) RETURN n
  Parameters: {id: "user_input"}

Bad (rejected):
  MATCH (n {id: 'user_input'}) RETURN n
```

**Decision 2: Batch Execution**

**Approach**: Execute CREATE statements in batches of 1000

**Why**: Reduce network overhead, better transaction performance

**Trade-off**: Larger transactions (longer lock time) vs fewer round-trips

**Decision 3: Connection Pooling**

**Approach**: Maintain persistent connection pool

**Why**: Connection setup is expensive (authentication, handshake)

**Benefit**: 10-100x faster for repeated queries

### Failure Modes

| Failure | Impact | Mitigation |
|---------|--------|------------|
| **Connection lost** | Cannot execute queries | Retry with backoff |
| **Transaction timeout** | Large batch fails | Reduce batch size |
| **Constraint violation** | Duplicate ID | Return error to user |
| **Out of memory** | Query fails | Add LIMIT to queries |
| **Deadlock** | Transaction stuck | Timeout and retry |

## MinIO Integration

### Service Contract

**Purpose**: S3-compatible object storage for files

**Interface**:
```
PUT Object
  Input: Bucket, key, content
  Output: Object metadata (size, etag)
  Error Modes: Bucket doesn't exist, disk full

GET Object
  Input: Bucket, key
  Output: Object content (bytes/stream)
  Error Modes: Object not found, access denied

LIST Objects
  Input: Bucket, prefix
  Output: List of object keys
  Error Modes: Bucket doesn't exist

DELETE Object
  Input: Bucket, key
  Output: Success/failure
  Error Modes: Object not found (ignored)
```

### Design Decisions

**Decision 1: Bucket-Per-Purpose**

**Approach**: Separate buckets for schemas vs uploads

**Buckets**:
- `niem-schemas` - Schema artifacts
- `niem-uploads` - Source files

**Why**: Easier access control, clearer organization, independent lifecycle

**Decision 2: ID-Based Prefixing**

**Approach**: Use schema_id/upload_id as object key prefixes

**Example**:
- Schema: `niem-schemas/schema-abc123/crashdriver.xsd`
- Upload: `niem-uploads/upload-xyz789/crash01.xml`

**Why**: Easy to list/delete all objects for a schema/upload

**Decision 3: Streaming for Large Files**

**Approach**: Stream file uploads/downloads (don't load into memory)

**Why**: Memory-efficient, supports large files (GB+), better performance

### Failure Modes

| Failure | Impact | Mitigation |
|---------|--------|------------|
| **MinIO down** | Cannot upload/download | Queue operations, retry |
| **Disk full** | Cannot upload | Check space, alert user |
| **Network timeout** | Upload fails | Retry with backoff |
| **Bucket missing** | Operations fail | Auto-create bucket on startup |
| **Object not found** | Download fails | Return 404 to user |

## CMFTool Integration

### Service Contract

**Purpose**: NIEM schema validation and CMF generation

**Interface**:
```
Validate XSD
  Input: XSD file path
  Output: Validation result (pass/fail + messages)
  Error Modes: Invalid XML, NDR violations, tool crash

Generate CMF
  Input: XSD file path
  Output: CMF content (XML)
  Error Modes: Invalid XSD, parse errors, tool crash
```

### Design Decisions

**Decision 1: Subprocess Execution**

**Approach**: Execute CMFTool as external process, not Python import

**Why**:
- Isolation (tool crash doesn't crash API)
- Timeout control (kill long operations)
- Resource limits (constrain memory)
- Version independence (upgrade separately)

**Trade-off**: Slower (subprocess overhead) vs safer (isolation)

**Decision 2: Temp File I/O**

**Approach**: Write input to temp file, read output from stdout/file

**Why**:
- CMFTool expects file paths, not streams
- Temp file auto-cleanup
- Works with tool's design

**Decision 3: Timeout Protection**

**Approach**: Kill CMFTool after 60 seconds

**Why**:
- Large schemas can hang
- Prevent resource exhaustion
- User feedback (timeout vs infinite wait)

### Failure Modes

| Failure | Impact | Mitigation |
|---------|--------|------------|
| **CMFTool not found** | Cannot validate schemas | Fail startup, show setup error |
| **Invalid XSD** | Validation fails | Return errors to user |
| **CMFTool timeout** | Schema upload fails | Kill process, return timeout error |
| **CMFTool crash** | Generation fails | Log error, return generic message |
| **Temp file I/O error** | Cannot process | Check disk space, return error |

## Senzing Integration

### Service Contract

**Purpose**: ML-based entity resolution (optional)

**Interface**:
```
Add Record
  Input: Entity data (JSON)
  Output: Success/failure
  Error Modes: Invalid data, license error

Get Entity
  Input: Record ID
  Output: Resolved entity data + match details
  Error Modes: Record not found, database error

Initialize Engine
  Input: License file, database config
  Output: Success/failure
  Error Modes: Invalid license, database connection error
```

### Design Decisions

**Decision 1: Optional Dependency**

**Approach**: Detect license on startup, fallback if unavailable

**License Detection**:
```
Startup:
  Check for g2license_*/ folder
    ├─ Found → Decode license → Initialize Senzing
    └─ Not Found → Log warning → Use text-based matching

API Response:
  Include resolution_method: "senzing" or "text_based"
```

**Why**: System works without license (development, testing, cost)

**Decision 2: Dual Strategy**

**Approach**: Same API interface for both strategies

**Strategies**:
- Senzing SDK: ML-based, fuzzy matching, confidence scores
- Text-Based: Simple name normalization, exact matching

**Benefits**:
- Transparent to API consumers
- Easy testing (mock Senzing)
- Gradual migration (add license anytime)

**Decision 3: Database Backend**

**Approach**: Senzing uses separate database (SQLite or PostgreSQL)

**Why**:
- Senzing manages its own entity graph
- Different schema from Neo4j
- Isolation (Senzing issues don't affect Neo4j)

**Options**:
- SQLite: Development, single-user
- PostgreSQL: Production, multi-user

### Failure Modes

| Failure | Impact | Mitigation |
|---------|--------|------------|
| **No license** | Use text-based | Automatic fallback |
| **License expired** | Use text-based | Log warning, fallback |
| **Database error** | Resolution fails | Return error, user retries |
| **SDK import error** | Use text-based | Log warning, fallback |
| **Record add fails** | Entity skipped | Log warning, continue |

## Failure Modes and Resilience

### Overall Resilience Strategy

**Principle**: Fail gracefully, never crash

```
Critical Services (Required):
  Neo4j, MinIO
    ├─ Fail Fast: Don't start if unavailable
    └─ Retry: Connection errors

Optional Services:
  Senzing
    └─ Fallback: Use alternative strategy

External Tools:
  CMFTool
    ├─ Timeout: Kill and return error
    └─ Fail Safe: Return error, don't crash
```

### Retry Logic

**Exponential Backoff**:
```
Attempt 1: Immediate
Attempt 2: Wait 1 second
Attempt 3: Wait 2 seconds
Attempt 4: Wait 4 seconds
Max Attempts: 3
```

**Applied To**:
- Neo4j connection errors
- MinIO network timeouts
- Transient database errors

**Not Applied To**:
- Validation errors (permanent)
- User input errors (permanent)
- Constraint violations (permanent)

### Circuit Breaker Pattern (Future)

**Concept**: Stop calling failing service after threshold

```
Service fails 5 times in a row
    ↓
Circuit opens (stop calling service)
    ↓
Wait 60 seconds
    ↓
Try once (half-open state)
    ├─ Success → Close circuit (resume normal)
    └─ Failure → Keep circuit open
```

**Benefits**:
- Prevent cascading failures
- Faster error responses (don't wait for timeout)
- Give failing service time to recover

**Future Enhancement**: Not currently implemented

### Health Checks

**Service Health Monitoring**:
```
/healthz endpoint checks:
  ├─ Neo4j: SELECT 1 query
  ├─ MinIO: List buckets
  ├─ CMFTool: Version check
  └─ Senzing: is_available() check

Response:
  {
    "status": "healthy",
    "services": {
      "neo4j": "ok",
      "minio": "ok",
      "cmftool": "ok",
      "senzing": "degraded"  // Optional, not critical
    }
  }
```

## Integration Testing Strategy

### Test Doubles

**Unit Tests** (Mock All External Services):
```
Test: XML to Cypher conversion
Mock: Neo4j client, MinIO client
Focus: Business logic correctness
```

**Integration Tests** (Real External Services):
```
Test: Full ingestion pipeline
Real: Neo4j (testcontainer), MinIO (testcontainer)
Focus: Integration correctness
```

**End-to-End Tests** (All Real Services):
```
Test: Complete user workflow
Real: All services (Docker Compose)
Focus: System correctness
```

### Mocking Strategy

**When to Mock**:
- Unit tests (always)
- Fast tests (always)
- CI/CD pipeline (unit tests)

**When to Use Real**:
- Integration tests (verify contracts)
- Performance tests (measure real behavior)
- Deployment verification (smoke tests)

## Security Considerations

### Authentication

**Neo4j**: Username/password (from environment)
**MinIO**: Access key/secret key (from environment)
**CMFTool**: No authentication (subprocess)
**Senzing**: License file (file-based)

### Network Security

**Internal Network** (Docker Compose):
```
All services on same Docker network
    ├─ Service discovery via DNS
    ├─ No external exposure (except UI, Neo4j Browser, MinIO Console)
    └─ Firewall rules (Docker manages)
```

**External Access**:
- UI: Port 3000 (public)
- Neo4j Browser: Port 7474 (public for dev, private for prod)
- MinIO Console: Port 9001 (public for dev, private for prod)

**Internal Only**:
- API: Port 8000 (accessed via UI proxy)
- Neo4j Bolt: Port 7687
- MinIO API: Port 9000

### Data Security

**Secrets Management**:
- Environment variables (not hardcoded)
- .env file (gitignored)
- Senzing license (base64 encoded)

**Data in Transit**:
- Neo4j: Bolt protocol (can enable TLS)
- MinIO: HTTP (can enable HTTPS)
- CMFTool: Local subprocess (no network)

**Data at Rest**:
- Neo4j: Unencrypted (can enable encryption)
- MinIO: Unencrypted (can enable encryption)
- Senzing: Database encryption depends on backend

## Performance Profile

### Integration Performance

| Integration | Operation | Typical Latency | Throughput |
|------------|-----------|-----------------|------------|
| **Neo4j** | Single query | 10-50ms | 1000+ queries/sec |
| **Neo4j** | Batch insert (1000) | 500-2000ms | 500-2000 nodes/sec |
| **MinIO** | Upload file (1MB) | 100-500ms | 10-50 files/sec |
| **MinIO** | Download file (1MB) | 50-200ms | 20-100 files/sec |
| **CMFTool** | Validate XSD | 1-30 seconds | 1-2 schemas/min |
| **Senzing** | Add record | 10-50ms | 100-500 records/sec |
| **Senzing** | Get entity | 5-20ms | 500-1000 queries/sec |

### Bottlenecks

**Identified Bottlenecks**:
1. **CMFTool validation** - Slowest operation (1-30s per schema)
2. **Neo4j batch inserts** - Can be slow for large documents
3. **Senzing initialization** - Takes 5-10s on startup

**Mitigation Strategies**:
1. Cache CMF results (future)
2. Optimize Cypher batching
3. Lazy Senzing initialization (only when needed)

## Related Documentation

- **[ARCHITECTURE.md](../ARCHITECTURE.md)** - Overall system architecture
- **[WORKFLOWS.md](WORKFLOWS.md)** - Sequence diagrams showing integration flows
- **[senzing-integration.md](senzing-integration.md)** - Detailed Senzing setup guide
- **[API_ARCHITECTURE.md](API_ARCHITECTURE.md)** - API layer design and client organization

---

**Last Updated**: 2024-11-08
**Documentation Version**: 1.0
