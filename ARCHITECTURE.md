# System Architecture

## Table of Contents

- [Overview](#overview)
- [System Components](#system-components)
- [Technology Stack](#technology-stack)
- [Deployment Architecture](#deployment-architecture)
- [Layered Architecture Pattern](#layered-architecture-pattern)
- [Key Design Principles](#key-design-principles)
- [Data Flow](#data-flow)
- [Related Documentation](#related-documentation)

## Overview

The NIEM Information Exchange system is a **graph-based data processing platform** that transforms NIEM (National Information Exchange Model) XML/JSON data into queryable knowledge graphs using Neo4j.

### Purpose

- **Schema Management**: Validate and manage NIEM XSD schemas using industry-standard tools
- **Data Ingestion**: Convert NIEM XML/JSON into property graphs with full validation
- **Graph Storage**: Store interconnected NIEM data in Neo4j for flexible querying
- **Entity Resolution**: Detect and link duplicate entities using ML (Senzing) or text-based matching
- **Visualization**: Interactive graph exploration and relationship discovery

### Core Capabilities

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   Schema     │────▶│     Data     │────▶│    Entity    │
│  Management  │     │  Ingestion   │     │  Resolution  │
└──────────────┘     └──────────────┘     └──────────────┘
       │                     │                     │
       └─────────────────────┴─────────────────────┘
                             ▼
                    ┌──────────────────┐
                    │   Graph Storage  │
                    │   & Querying     │
                    └──────────────────┘
```

## System Components

### High-Level Architecture

```
┌───────────────────────────────────────────────────────────────────────┐
│                           User Layer                                   │
│  ┌─────────────────────────────────────────────────────────────────┐ │
│  │  Web UI (Next.js/React)                                          │ │
│  │  - Schema Management  - File Upload  - Graph Visualization      │ │
│  └─────────────────────────────────────────────────────────────────┘ │
└────────────────────────────────────┬──────────────────────────────────┘
                                     │ HTTP/REST
                                     ▼
┌───────────────────────────────────────────────────────────────────────┐
│                        Application Layer                               │
│  ┌─────────────────────────────────────────────────────────────────┐ │
│  │  API Service (FastAPI/Python)                                    │ │
│  │  - REST Endpoints  - Request Validation  - Business Logic       │ │
│  │                                                                   │ │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │ │
│  │  │   Handlers   │  │   Services   │  │   Clients    │          │ │
│  │  │ (Orchestrate)│→ │(Business Logic)│→ │(External APIs)│         │ │
│  │  └──────────────┘  └──────────────┘  └──────────────┘          │ │
│  └─────────────────────────────────────────────────────────────────┘ │
└────────────────────┬──────────────────────┬──────────────────────────┘
                     │                      │
                     ▼                      ▼
┌──────────────────────────────┐  ┌──────────────────────────────┐
│      Storage Layer           │  │   Integration Layer          │
│  ┌────────────────────────┐  │  │  ┌────────────────────────┐ │
│  │  Neo4j Graph Database  │  │  │  │   CMFTool (NIEM)       │ │
│  │  - Nodes & Relationships│  │  │  │   - XSD Validation     │ │
│  │  - Cypher Queries      │  │  │  │   - CMF Generation     │ │
│  └────────────────────────┘  │  │  └────────────────────────┘ │
│                               │  │                              │
│  ┌────────────────────────┐  │  │  ┌────────────────────────┐ │
│  │  MinIO Object Storage  │  │  │  │   Senzing SDK          │ │
│  │  - Schemas (XSD)       │  │  │  │   - Entity Resolution  │ │
│  │  - Source Files        │  │  │  │   - ML-based Matching  │ │
│  │  - Generated Mappings  │  │  │  └────────────────────────┘ │
│  └────────────────────────┘  │  │                              │
└──────────────────────────────┘  └──────────────────────────────┘
```

### Component Descriptions

#### **Web UI (Next.js/React)** - `ui/`
- **Purpose**: User interface for all system interactions
- **Technology**: Next.js 14, React 18, TypeScript
- **Key Features**:
  - Schema upload and management
  - XML/JSON file ingestion
  - Graph visualization (Cytoscape.js)
  - Entity resolution controls
  - Neo4j graph explorer
- **Port**: 3000

#### **API Service (FastAPI/Python)** - `api/`
- **Purpose**: Backend REST API for all business logic
- **Technology**: FastAPI, Python 3.11+
- **Architecture**: 3-layer pattern (see [Layered Architecture](#layered-architecture-pattern))
- **Key Features**:
  - Schema validation and storage
  - Dual-mode data converter (XML/JSON → Cypher)
  - Entity resolution orchestration
  - Graph query execution
- **Port**: 8000

#### **Neo4j Graph Database**
- **Purpose**: Store interconnected NIEM data as property graph
- **Technology**: Neo4j Community Edition 5.x
- **Data Model**: See [GRAPH_SCHEMA.md](docs/GRAPH_SCHEMA.md)
- **Ports**: 7474 (HTTP), 7687 (Bolt)

#### **MinIO Object Storage**
- **Purpose**: S3-compatible storage for files and schemas
- **Technology**: MinIO
- **Stored Objects**:
  - XSD schema files
  - Source XML/JSON files
  - Generated mapping.yaml files
  - CMF (Common Model Format) files
- **Ports**: 9000 (API), 9001 (Console)

#### **CMFTool (NIEM Validation)**
- **Purpose**: NIEM schema validation and CMF generation
- **Technology**: Python tool from niemopen/cmftool
- **Integration**: Called via subprocess from API service
- **Location**: `api/third_party/niem-cmf/`

#### **Senzing SDK (Optional)**
- **Purpose**: ML-based entity resolution
- **Technology**: Senzing SDK v4 with gRPC
- **Fallback**: Text-based entity matching (no license required)
- **Documentation**: See [docs/senzing-integration.md](docs/senzing-integration.md)

## Technology Stack

### Frontend Stack

| Technology | Version | Purpose |
|-----------|---------|---------|
| Next.js | 14.x | React framework with SSR/SSG |
| React | 18.x | UI component library |
| TypeScript | 5.x | Type-safe JavaScript |
| Tailwind CSS | 3.x | Utility-first CSS framework |
| Cytoscape.js | 3.x | Graph visualization |
| Axios | 1.x | HTTP client |

### Backend Stack

| Technology | Version | Purpose |
|-----------|---------|---------|
| Python | 3.11+ | Programming language |
| FastAPI | 0.100+ | Web framework |
| Pydantic | 2.x | Data validation |
| Neo4j Driver | 5.x | Graph database client |
| MinIO SDK | 7.x | S3 object storage client |
| Senzing SDK | 4.x | Entity resolution (optional) |

### Infrastructure Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| Container Runtime | Docker 20+ | Application containerization |
| Orchestration | Docker Compose | Multi-container deployment |
| Graph Database | Neo4j 5.x | Property graph storage |
| Object Storage | MinIO | S3-compatible file storage |
| Reverse Proxy | None (dev) | Future: Nginx/Traefik |

### Development Tools

| Tool | Purpose |
|------|---------|
| CMFTool | NIEM XSD → CMF validation |
| NDR Schematron | NIEM naming/design rules |
| Trivy | Container security scanning |
| Bandit | Python security analysis |
| pytest | Python unit testing |

## Deployment Architecture

### Docker Compose Layout

```
┌────────────────────────────────────────────────────────────────┐
│                      Docker Compose Network                     │
│                                                                 │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐                 │
│  │    ui    │───▶│   api    │───▶│  neo4j   │                 │
│  │  :3000   │    │  :8000   │    │:7474/7687│                 │
│  └──────────┘    └──────────┘    └──────────┘                 │
│                         │                                       │
│                         ▼                                       │
│                  ┌──────────┐                                  │
│                  │  minio   │                                  │
│                  │:9000/9001│                                  │
│                  └──────────┘                                  │
│                                                                 │
│  Volumes:                                                       │
│  - neo4j-data     (graph database persistence)                 │
│  - minio-data     (object storage persistence)                 │
│  - api-data       (uploaded files, temp storage)               │
└────────────────────────────────────────────────────────────────┘
```

### Container Specifications

| Service | Base Image | Exposed Ports | Volumes |
|---------|-----------|---------------|---------|
| ui | node:20-alpine | 3000 | (code mount in dev) |
| api | python:3.11-slim | 8000 | api-data, code mount |
| neo4j | neo4j:5-community | 7474, 7687 | neo4j-data |
| minio | minio/minio | 9000, 9001 | minio-data |

### Network Configuration

- **Default Network**: `bridge` (Docker Compose auto-created)
- **Service Discovery**: DNS-based (service names resolve to IPs)
- **External Access**: UI (3000), Neo4j Browser (7474), MinIO Console (9001)
- **Internal Only**: Neo4j Bolt (7687), MinIO API (9000), API (8000)

## Layered Architecture Pattern

The API service follows a **strict 3-layer architecture** to separate concerns:

```
┌─────────────────────────────────────────────────────────────┐
│                    Layer 1: main.py                          │
│              HTTP/Routing Layer (FastAPI routes)             │
│                                                              │
│  Responsibilities:                                           │
│  ✅ Define HTTP endpoints                                   │
│  ✅ Request/response handling                               │
│  ✅ Dependency injection                                    │
│  ✅ Input validation (Pydantic)                             │
│  ❌ NO business logic                                       │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                  Layer 2: handlers/                          │
│              Orchestration Layer (Request handlers)          │
│                                                              │
│  Responsibilities:                                           │
│  ✅ Request orchestration (call multiple services)          │
│  ✅ Transaction management                                  │
│  ✅ Error handling & translation                            │
│  ✅ Response formatting                                     │
│  ❌ NO direct database/S3 access                            │
│  ❌ NO complex business logic                               │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                  Layer 3: services/                          │
│           Business Logic Layer (Domain services)             │
│                                                              │
│  Responsibilities:                                           │
│  ✅ Core business logic                                     │
│  ✅ Data transformations                                    │
│  ✅ External integrations (Neo4j, MinIO, Senzing)          │
│  ✅ Domain-specific operations                              │
│  ✅ Client wrappers (clients/ for external APIs)            │
└─────────────────────────────────────────────────────────────┘
```

### Layer Details

**Layer 1: main.py (Routes)**
- Thin controllers - extract params, validate, delegate
- Example: `@app.post("/api/ingest/xml")` → calls `handle_xml_ingest()`

**Layer 2: handlers/ (Orchestration)**
- Example: `handle_xml_ingest()` orchestrates:
  1. Get schema from MinIO
  2. Validate XML with CMFTool
  3. Convert to Cypher (service)
  4. Execute in Neo4j
  5. Store file in MinIO

**Layer 3: services/ (Business Logic)**
- `xml_to_graph/converter.py` - XML → Cypher transformation
- `json_to_graph/converter.py` - JSON → Cypher transformation
- `schema/xsd_schema_designer.py` - Element tree generation
- `entity_to_senzing.py` - Entity resolution logic
- `clients/` - Neo4j, MinIO, Senzing client wrappers

**Benefits of This Pattern:**
- ✅ Clear separation of concerns
- ✅ Easy to test (mock services)
- ✅ Reusable business logic
- ✅ Maintainable codebase
- ✅ Consistent error handling

See [docs/API_ARCHITECTURE.md](docs/API_ARCHITECTURE.md) for detailed implementation.

## Key Design Principles

### 1. Dual-Mode Data Converter

The system supports **two modes** for XML/JSON ingestion:

**Dynamic Mode** (No selections)
- Creates nodes for ALL complex elements
- Includes extension namespaces automatically
- Best for exploration and discovery
- Zero configuration required

**Mapping Mode** (With selections.json)
- Creates nodes ONLY for selected elements
- Controlled graph structure
- Best for production with known schema
- Schema designer generates selections

See [docs/INGESTION_AND_MAPPING.md](docs/INGESTION_AND_MAPPING.md) for details.

### 2. Schema Isolation

All data is isolated by schema/upload:

```
Node Properties:
- _schema_id: "abc123"      # Which schema was used
- _upload_id: "upload-456"  # Which file batch
- sourceDoc: "crash01.xml"  # Source filename
```

**Benefits:**
- Query single schema: `MATCH (n {_schema_id: $id})`
- Delete by upload: `MATCH (n {_upload_id: $id}) DETACH DELETE n`
- Multi-tenant capable

### 3. Format Parity (XML ↔ JSON)

Same `mapping.yaml` works for both XML and JSON:

```
XSD → CMF → mapping.yaml ← Used by both converters
                ├─▶ XML → Cypher
                └─▶ JSON → Cypher
```

Ensures consistent graph structure regardless of input format.

### 4. Graph Flattening Strategy

**Problem**: NIEM has deep property wrapper hierarchies
```xml
<nc:Person>
  <nc:PersonName>
    <nc:PersonGivenName>John</nc:PersonGivenName>
  </nc:PersonName>
</nc:Person>
```

**Solution**: Flatten properties onto parent objects
```
Person node properties:
- nc_PersonGivenName: "John"
- nc_PersonSurName: "Doe"
```

See [docs/adr/ADR-002-graph-flattening-strategy.md](docs/adr/ADR-002-graph-flattening-strategy.md).

### 5. Entity Resolution Strategy

**Dual-strategy approach:**
1. **Senzing SDK** (with license) - ML-based, fuzzy matching
2. **Text-based** (fallback) - Simple name matching

System automatically detects license and switches modes.

See [docs/senzing-integration.md](docs/senzing-integration.md).

## Data Flow

### Schema Upload Flow

```
User → UI → API → CMFTool → MinIO
         │         │
         │         └─▶ Validate XSD (NDR rules)
         │         └─▶ Generate CMF file
         │         └─▶ Create mapping.yaml
         │
         └─▶ Store XSD, CMF, mapping in MinIO
         └─▶ Return schema_id to user
```

### Data Ingestion Flow

```
User → UI → API → MinIO (get schema)
         │         │
         │         └─▶ Validate XML/JSON against schema
         │         └─▶ Converter: XML/JSON → Cypher statements
         │         └─▶ Neo4j: Execute Cypher (create nodes/edges)
         │         └─▶ MinIO: Store source file
         │
         └─▶ Return ingest results (nodes/edges created)
```

### Entity Resolution Flow

```
User → UI → API → Neo4j (query entities)
         │         │
         │         └─▶ Extract entity data
         │         └─▶ Senzing/Text Matcher: Find duplicates
         │         └─▶ Neo4j: Create ResolvedEntity nodes
         │         └─▶ Neo4j: Link with RESOLVED_TO relationships
         │
         └─▶ Return resolution stats (duplicates found)
```

### Graph Query Flow

```
User → UI → API → Neo4j (execute Cypher)
         │         │
         │         └─▶ Return nodes & relationships as JSON
         │
         └─▶ Render graph visualization
```

See [docs/WORKFLOWS.md](docs/WORKFLOWS.md) for detailed sequence diagrams.

## Development Architecture

### Local Development Environment

```
┌────────────────────────────────────────────────────────────────┐
│                    Development Workstation                      │
│                                                                 │
│  ┌──────────────────────┐      ┌──────────────────────┐       │
│  │   Code Editor (VS    │      │   Docker Desktop     │       │
│  │   Code/PyCharm/etc)  │      │   (Containers)       │       │
│  └──────────────────────┘      └──────────────────────┘       │
│           │                              │                      │
│           ▼                              ▼                      │
│  ┌──────────────────────┐      ┌──────────────────────┐       │
│  │  Git (Version        │      │  Hot Reload (Dev     │       │
│  │  Control)            │      │  mode with volumes)  │       │
│  └──────────────────────┘      └──────────────────────┘       │
└────────────────────────────────────────────────────────────────┘
```

### Development Workflow

**1. Code Changes with Hot Reload**

Docker Compose dev configuration enables hot reload:

```yaml
# docker-compose.override.yml (for local dev)
services:
  api:
    volumes:
      - ./api/src:/app/src  # Mount source code
    command: uvicorn ... --reload  # Enable hot reload

  ui:
    volumes:
      - ./ui/src:/app/src
    # Next.js dev mode auto-reloads
```

**Benefits:**
- ✅ Edit code locally → changes reflect immediately in containers
- ✅ No rebuild required for source code changes
- ✅ Fast iteration cycle

**2. Debugging Strategy**

```
Local Debugging Options:
├── API Service (Python)
│   ├── Logs: docker compose logs api -f
│   ├── Debug prints: logger.debug()
│   ├── Interactive: docker compose exec api python
│   └── VS Code: Remote container debugging
│
├── UI Service (Next.js)
│   ├── Browser DevTools (React DevTools, Network tab)
│   ├── Console logs: console.log()
│   └── Next.js built-in error overlay
│
└── Neo4j Database
    ├── Browser: http://localhost:7474
    ├── Cypher queries: MATCH (n) RETURN n LIMIT 25
    └── Query profiling: PROFILE/EXPLAIN
```

**3. Testing Locally**

```bash
# Unit tests
docker compose exec api pytest tests/

# Integration tests (with running services)
docker compose exec api pytest tests/integration/

# UI tests
docker compose exec ui npm test

# End-to-end tests
npm run test:e2e
```

See [docs/UNIT_TESTING.md](docs/UNIT_TESTING.md) for comprehensive testing guide.

### Development Architecture Layers

```
┌──────────────────────────────────────────────────────────────┐
│  IDE/Editor Layer (Local)                                     │
│  - Code editing, debugging, git                               │
└────────────────┬─────────────────────────────────────────────┘
                 │ File system mount
                 ▼
┌──────────────────────────────────────────────────────────────┐
│  Container Layer (Docker)                                     │
│  - Hot reload, auto-restart                                   │
│  - Development dependencies                                   │
└────────────────┬─────────────────────────────────────────────┘
                 │ Network calls
                 ▼
┌──────────────────────────────────────────────────────────────┐
│  Service Layer (Running containers)                           │
│  - API, UI, Neo4j, MinIO                                     │
│  - Shared Docker network                                     │
└──────────────────────────────────────────────────────────────┘
```

### Local vs Production Differences

| Aspect | Local Development | Production |
|--------|------------------|------------|
| **Code Mounting** | Source mounted as volumes | Copied into image at build |
| **Hot Reload** | Enabled (API, UI) | Disabled |
| **Logging** | DEBUG level, stdout | INFO/WARNING, structured logs |
| **Authentication** | Simple dev token | Full OAuth/JWT |
| **CORS** | Allow localhost:3000 | Specific origins only |
| **Database** | Shared Neo4j container | Dedicated DB cluster |
| **Object Storage** | Local MinIO | AWS S3 or cloud MinIO |
| **Secrets** | .env file | K8s secrets/vault |

## Security Architecture

### Security Layers

```
┌───────────────────────────────────────────────────────────────┐
│  Layer 1: Network Security                                     │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │  - CORS policies (UI ↔ API)                            │  │
│  │  - Internal Docker network (services isolated)          │  │
│  │  - Port exposure control (only necessary ports public)  │  │
│  └─────────────────────────────────────────────────────────┘  │
└───────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌───────────────────────────────────────────────────────────────┐
│  Layer 2: Authentication & Authorization                       │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │  - API token verification (Bearer token)                │  │
│  │  - Request authentication middleware                    │  │
│  │  - Role-based access control (future)                   │  │
│  └─────────────────────────────────────────────────────────┘  │
└───────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌───────────────────────────────────────────────────────────────┐
│  Layer 3: Input Validation                                     │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │  - Pydantic schema validation (API requests)            │  │
│  │  - File type validation (XSD, XML, JSON only)           │  │
│  │  - XSD/NDR schema validation (CMFTool)                  │  │
│  │  - Cypher injection prevention (parameterized queries)  │  │
│  └─────────────────────────────────────────────────────────┘  │
└───────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌───────────────────────────────────────────────────────────────┐
│  Layer 4: Data Security                                        │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │  - Secrets management (environment variables)           │  │
│  │  - Senzing license encryption (base64 encoded)          │  │
│  │  - Database credentials isolation                       │  │
│  │  - File access controls (MinIO buckets)                 │  │
│  └─────────────────────────────────────────────────────────┘  │
└───────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌───────────────────────────────────────────────────────────────┐
│  Layer 5: Container Security                                   │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │  - Trivy vulnerability scanning (images)                │  │
│  │  - Bandit SAST scanning (Python code)                   │  │
│  │  - Non-root user execution                              │  │
│  │  - Read-only file systems (where possible)              │  │
│  └─────────────────────────────────────────────────────────┘  │
└───────────────────────────────────────────────────────────────┘
```

### Authentication Flow

```
┌──────────┐         ┌──────────┐         ┌──────────┐
│   User   │────────▶│    UI    │────────▶│   API    │
└──────────┘         └──────────┘         └──────────┘
                           │                    │
                           │  1. User login     │
                           │  (future: OAuth)   │
                           │                    │
                           │  2. Get token      │
                           │◀───────────────────│
                           │                    │
                           │  3. All requests   │
                           │  Authorization:    │
                           │  Bearer <token>    │
                           ├───────────────────▶│
                           │                    │
                           │  4. Verify token   │
                           │  via middleware    │
                           │                    │
                           │  5. Response       │
                           │◀───────────────────│
```

### Current Security Controls

**Implemented ✅**
- Token-based API authentication
- CORS policy enforcement
- Input validation (Pydantic schemas)
- XSD/NDR validation (CMFTool)
- Parameterized Cypher queries (no injection)
- Container vulnerability scanning (Trivy)
- Python SAST scanning (Bandit)
- Non-root container users
- Secrets in environment variables
- File type validation

**Planned 🔄**
- OAuth 2.0 / OpenID Connect
- Role-Based Access Control (RBAC)
- API rate limiting
- Audit logging
- Encryption at rest (database, object storage)
- Secrets management (Vault, K8s secrets)
- Network policies (K8s)

### Threat Model

| Threat | Risk | Mitigation |
|--------|------|------------|
| **Unauthorized API access** | HIGH | Token authentication, future: OAuth |
| **XSD/XML injection** | MEDIUM | CMFTool validation, file type checks |
| **Cypher injection** | HIGH | Parameterized queries only |
| **Container vulnerabilities** | MEDIUM | Trivy scanning, regular updates |
| **Secrets exposure** | HIGH | Environment variables, .gitignore |
| **DOS attacks** | MEDIUM | Future: rate limiting, request size limits |
| **Data exfiltration** | MEDIUM | Network isolation, future: encryption at rest |

See [SECURITY.md](SECURITY.md) for security policy and vulnerability reporting.

## Test Architecture

### Testing Strategy Pyramid

```
                    ┌─────────────┐
                    │   Manual    │  ← Exploratory testing
                    │  Testing    │
                    └─────────────┘
                    ┌─────────────────┐
                    │  End-to-End     │  ← Full user workflows
                    │    Tests        │  ← (Playwright/Cypress)
                    └─────────────────┘
              ┌───────────────────────────┐
              │   Integration Tests       │  ← API + Neo4j + MinIO
              │  (Service interactions)   │  ← Testcontainers
              └───────────────────────────┘
        ┌─────────────────────────────────────┐
        │      Unit Tests (Majority)          │  ← Fast, isolated
        │  - Handlers, Services, Converters   │  ← pytest + mocks
        └─────────────────────────────────────┘
```

### Test Layers

**Layer 1: Unit Tests (80% of tests)**
- **Scope**: Individual functions, classes, modules
- **Tools**: pytest, unittest.mock
- **Speed**: < 1 second per test
- **Dependencies**: Mock external services (Neo4j, MinIO, etc.)
- **Location**: `api/tests/unit/`, `ui/src/__tests__/`

**Example:**
```python
def test_xml_to_cypher_conversion():
    """Test XML node conversion to Cypher"""
    converter = XMLToGraphConverter(mock_mapping)
    xml_node = ET.fromstring("<nc:Person>...</nc:Person>")

    cypher = converter.convert_node(xml_node)

    assert "CREATE (n:nc_Person" in cypher
    assert "SET n.nc_PersonGivenName" in cypher
```

**Layer 2: Integration Tests (15% of tests)**
- **Scope**: Multiple components working together
- **Tools**: pytest, testcontainers, Docker Compose
- **Speed**: 5-30 seconds per test
- **Dependencies**: Real Neo4j, MinIO (testcontainers)
- **Location**: `api/tests/integration/`

**Example:**
```python
def test_xml_ingestion_end_to_end(neo4j_container, minio_container):
    """Test full XML ingestion pipeline"""
    # Upload schema
    schema_id = upload_schema("crashdriver.xsd")

    # Ingest XML
    result = ingest_xml("crash01.xml", schema_id)

    # Verify graph
    nodes = query_neo4j("MATCH (n) RETURN count(n)")
    assert nodes > 0
```

**Layer 3: End-to-End Tests (5% of tests)**
- **Scope**: Full user workflows via UI
- **Tools**: Playwright, Cypress (future)
- **Speed**: 30-120 seconds per test
- **Dependencies**: All services running (Docker Compose)
- **Location**: `e2e/`

**Example:**
```typescript
test('upload schema and ingest XML', async ({ page }) => {
  await page.goto('http://localhost:3000');
  await page.click('text=Upload Schema');
  await page.setInputFiles('input[type="file"]', 'crashdriver.xsd');
  await page.click('text=Upload');
  await expect(page.locator('.success')).toBeVisible();
});
```

### Test Coverage Goals

| Component | Unit Test Coverage | Integration Coverage |
|-----------|-------------------|---------------------|
| API Handlers | 85%+ | Key workflows covered |
| Services/Converters | 90%+ | Core algorithms tested |
| Client Wrappers | 70%+ | Mock external APIs |
| UI Components | 75%+ | Critical paths tested |

**Current Achievement (per CI/CD):**
- Changed lines: **100% coverage** (enforced by CI)
- Overall codebase: ~80% coverage

### Testing Infrastructure

```
┌────────────────────────────────────────────────────────────┐
│               CI/CD Pipeline (GitHub Actions)               │
│                                                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐       │
│  │  Unit Tests │  │ Integration │  │  Security   │       │
│  │  (pytest)   │→ │   Tests     │→ │  Scanning   │       │
│  │  < 2 min    │  │  (pytest +  │  │  (Trivy +   │       │
│  │             │  │  containers)│  │  Bandit)    │       │
│  │             │  │  < 10 min   │  │  < 5 min    │       │
│  └─────────────┘  └─────────────┘  └─────────────┘       │
│                                                             │
│  Coverage Enforcement:                                      │
│  ✅ 100% of changed lines must be tested                  │
│  ✅ No decrease in overall coverage                        │
│  ✅ All tests must pass before merge                       │
└────────────────────────────────────────────────────────────┘
```

### Test Data Strategy

**Approach: Test Fixtures + Factories**

```python
# Fixtures for consistent test data
@pytest.fixture
def sample_crash_xml():
    """Provides sample CrashDriver XML for testing"""
    return """
    <j:Crash>
      <j:CrashDriver>
        <nc:Person>...</nc:Person>
      </j:CrashDriver>
    </j:Crash>
    """

@pytest.fixture
def mock_neo4j_client():
    """Provides mocked Neo4j client"""
    mock = MagicMock(spec=Neo4jClient)
    mock.query.return_value = [{"n": {...}}]
    return mock
```

**Test Data Sources:**
1. **Golden files**: `tests/fixtures/schemas/`, `tests/fixtures/data/`
2. **Generated data**: Factory patterns for creating test objects
3. **Minimal examples**: Small, focused test cases
4. **Real-world samples**: Anonymized CrashDriver data (in fixtures)

### Mocking Strategy

**External Services (Always Mock in Unit Tests):**
- Neo4j driver → `unittest.mock.MagicMock`
- MinIO client → `unittest.mock.MagicMock`
- Senzing SDK → `unittest.mock.MagicMock`
- CMFTool subprocess → `unittest.mock.patch('subprocess.run')`

**Internal Services (Mock at boundaries):**
- Handlers test → Mock services
- Services test → Mock clients
- Clients test → Mock external APIs

### Continuous Testing

```
Developer Workflow:
┌──────────────┐
│  Write Code  │
└──────┬───────┘
       │
       ▼
┌──────────────┐      ┌──────────────┐
│  Run Tests   │─────▶│  Commit to   │
│  Locally     │      │    Branch    │
└──────────────┘      └──────┬───────┘
                              │
                              ▼
                      ┌──────────────┐
                      │  CI Runs All │
                      │    Tests     │
                      └──────┬───────┘
                              │
                 ┌────────────┴────────────┐
                 │                         │
                 ▼                         ▼
         ┌─────────────┐          ┌─────────────┐
         │  Tests Pass │          │ Tests Fail  │
         │  → Merge    │          │ → Fix Code  │
         └─────────────┘          └─────────────┘
```

See [docs/UNIT_TESTING.md](docs/UNIT_TESTING.md) and [docs/CI_CD_PIPELINE.md](docs/CI_CD_PIPELINE.md) for complete testing guide.

## Related Documentation

### Architecture & Design
- **[API_ARCHITECTURE.md](docs/API_ARCHITECTURE.md)** - Detailed 3-layer pattern, code organization
- **[GRAPH_SCHEMA.md](docs/GRAPH_SCHEMA.md)** - Neo4j data model, node types, relationships
- **[WORKFLOWS.md](docs/WORKFLOWS.md)** - Sequence diagrams for key operations
- **[INTEGRATIONS.md](docs/INTEGRATIONS.md)** - External service integration details
- **[schema_designer.md](docs/schema_designer.md)** - Schema designer architecture

### Implementation Details
- **[INGESTION_AND_MAPPING.md](docs/INGESTION_AND_MAPPING.md)** - Data transformation pipeline
- **[GRAPH_GENERATION_LOGIC.md](docs/GRAPH_GENERATION_LOGIC.md)** - Algorithm deep-dive
- **[senzing-integration.md](docs/senzing-integration.md)** - Entity resolution setup
- **[SENZING_MATCH_DETAILS.md](docs/SENZING_MATCH_DETAILS.md)** - Match transparency feature

### Architecture Decision Records (ADRs)
- **[ADR-001: Batch Processing](docs/adr/ADR-001-batch-processing-pattern.md)** - Batch upload pattern
- **[ADR-002: Graph Flattening](docs/adr/ADR-002-graph-flattening-strategy.md)** - Property flattening rationale

### Operations & Testing
- **[CI_CD_PIPELINE.md](docs/CI_CD_PIPELINE.md)** - Build, test, security pipeline
- **[UNIT_TESTING.md](docs/UNIT_TESTING.md)** - Testing strategy and examples
- **[VERSIONING.md](docs/VERSIONING.md)** - Semantic versioning approach

### Getting Started
- **[README.md](README.md)** - Quick start, walkthrough, deployment
- **[CONTRIBUTING.md](CONTRIBUTING.md)** - Development workflow, standards
- **[SECURITY.md](SECURITY.md)** - Security policy, reporting

---

**Last Updated**: 2024-11-08
**Architecture Version**: 1.0
**System Version**: 0.1.0-alpha
