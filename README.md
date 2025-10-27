# NIEM Information Exchange - Proof of Concept

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

An demonstration of NIEM (National Information Exchange Model) data processing and graph ingestion system.

## Overview

This system provides end-to-end NIEM information exchange capabilities:

1. **Schema Management** - Upload and validate NIEM XSD schemas using CMF (Common Model Format) tools
2. **Data Ingestion** - Validate and ingest XML/JSON files against NIEM schemas
3. **Graph Storage** - Neo4j for storing and querying interconnected NIEM data
4. **Web Interface** - React/Next.js UI for management and monitoring
5. **Graph Visualization** - Interactive graph exploration and querying interface

## Architecture

### Components

- **UI** (Next.js): Schema management, file upload, graph visualization, admin interface
- **API** (FastAPI): REST API endpoints, data ingestion, graph operations
- **MinIO**: S3-compatible object storage for files and schemas
- **Neo4j**: Graph database for storing and querying interconnected NIEM data

### Data Flow

```
XSD Upload → NDR Validation → Schema Storage (MinIO)
     ↓
XML/JSON Upload → CMF Validation → Graph Parsing → Neo4j Storage → File Storage (MinIO)
```

## Third-Party Dependencies

This project includes vendored third-party tools in the `third_party/` directory. See individual README files for license information, update instructions, and attribution details:
- **NIEM CMF Tool** (`third_party/niem-cmf/`) - Apache 2.0 licensed validation tooling from [niemopen/cmftool](https://github.com/niemopen/cmftool)
- **NIEM NDR Tools** (`third_party/niem-ndr/`) - CC BY 4.0 licensed validation rules and execution tools from [NIEM/NIEM-NDR](https://github.com/NIEM/NIEM-NDR) and [niemopen/niem-naming-design-rules](https://github.com/niemopen/niem-naming-design-rules)

## API Documentation

The API provides automatic interactive documentation via FastAPI:

### Interactive Documentation (once system is running)

- **Swagger UI**: http://localhost:8000/docs
  - Full interactive API explorer with "Try it out" buttons
  - Test endpoints directly from your browser
  - See request/response schemas in real-time

- **ReDoc**: http://localhost:8000/redoc
  - Clean, readable API reference documentation
  - Better for printing or detailed review
  - Three-column layout for easy navigation

- **OpenAPI Schema**: http://localhost:8000/openapi.json
  - Raw OpenAPI 3.0 specification
  - Import into Postman, Insomnia, or other API clients

### Main API Endpoints

- **Schema Management**: Upload, validate, and activate NIEM XSD schemas
- **Data Ingestion**: Upload and validate XML/JSON files against schemas
- **NDR Validation**: Type-aware NIEM NDR validation (reference/extension/subset schemas)
- **Graph Operations**: Query and manage Neo4j graph data
- **System Admin**: Health checks, statistics, reset operations

## Quick Start

### Prerequisites

- Docker Desktop installed and running
- Docker Compose (included with Docker Desktop)
- **Make** (for build automation):
  - macOS/Linux: Pre-installed
  - Windows: Git Bash (included with [Git for Windows](https://gitforwindows.org/)) or WSL2
- 8GB+ RAM recommended
- Ports 3000+, 7474, 7687, 8000+, 9000, 9001 available

### 1. Start the System

```bash
# Clone and enter directory
git clone <repository-url>
cd niem-info-exch-e2e

# Optional: Copy environment configuration for customization
cp .env.example .env

# Start infrastructure and application in development mode
make dev-up

# Wait for services to be healthy (2-3 minutes)
# Infrastructure starts automatically if not already running
```

### 2. Access the Web Interface

Open http://localhost:3000 in your browser

### 3. View Logs and Status

Check logs and service status:

```bash
# View application logs (API + UI)
make logs

# Filter logs (pipe to grep)
make logs | grep ERROR

# View infrastructure logs
make infra-logs

# Check current configuration
make help
```

### 4. Stopping Services

```bash
# Stop this worktree's application services
make dev-down

# Stop shared infrastructure (affects all worktrees!)
make infra-down

# Stop everything (infrastructure + all worktrees)
make clean-all
```

## Development Workflows

This project uses a Makefile-based workflow that automatically manages infrastructure and assigns unique ports per worktree.

### Single Worktree Development

For working on a single branch:

```bash
# Start development environment (auto-starts infrastructure if needed)
make dev-up

# View logs
make logs

# Stop application
make dev-down
```

**Features**:
- Hot reloading enabled automatically
- Source code mounted as volumes (changes reflect immediately)
- Infrastructure shared across worktrees (Neo4j + MinIO)
- Automatic port assignment (default: API=8000, UI=3000)

### Multi-Worktree Development

For working on multiple git branches simultaneously (e.g., comparing features, parallel development):

```bash
# Worktree 1: main branch
cd ~/code/niem/main
make dev-up
# → Automatically assigns: API=8000, UI=3000, Project=niem-main

# Worktree 2: feature-auth branch
cd ~/code/niem/feature-auth
make dev-up
# → Automatically assigns: API=8001, UI=3001, Project=niem-feature-auth

# Worktree 3: test-docker-tree branch
cd ~/code/niem/test-docker-tree
make dev-up
# → Automatically assigns: API=8002, UI=3002, Project=niem-test-docker-tree

# Now access all three:
# http://localhost:3000 - main
# http://localhost:3001 - feature-auth
# http://localhost:3002 - test-docker-tree
# All sharing the same Neo4j and MinIO data
```

**How it works**:
- Port offset calculated from branch name hash (0-9)
- Each worktree gets unique container names
- All worktrees share infrastructure (one Neo4j, one MinIO)
- No manual configuration needed

**Available commands**:
```bash
make help          # Show all commands and current configuration
make dev-up        # Start development environment
make dev-down      # Stop this worktree only
make prod-up       # Start in production mode (no hot reload)
make logs          # View application logs
make infra-up      # Manually start infrastructure
make infra-down    # Stop infrastructure (affects all worktrees!)
make infra-logs    # View infrastructure logs
make clean-all     # Stop everything
```

### Production Mode

For production-like testing without hot reload:

```bash
# Start in production mode
make prod-up

# View logs
make logs

# Stop everything when done
make clean-all
```

**Differences from dev**:
- No source code volume mounts
- Optimized multi-stage builds (~70% smaller images)
- Production commands (no auto-reload)
- Standalone Next.js output

### Build Optimizations

The Dockerfiles use BuildKit features for faster builds:

**Enable BuildKit** (if not already default):
```bash
export DOCKER_BUILDKIT=1
export COMPOSE_DOCKER_CLI_BUILD=1
```

**Cache Benefits**:
- `pip install` results cached (API rebuilds in ~10s instead of ~60s)
- `npm ci` results cached (UI rebuilds in ~15s instead of ~90s)
- Multi-stage builds reduce final image size by ~70%

### Port Reference

**Infrastructure** (shared, fixed ports):

| Service | Port | Access |
|---------|------|--------|
| Neo4j Browser | 7474 | http://localhost:7474 |
| Neo4j Bolt | 7687 | bolt://localhost:7687 |
| MinIO API | 9001 | http://localhost:9001 |
| MinIO Console | 9002 | http://localhost:9002 |

**Application** (per-worktree, auto-assigned):

| Worktree | API Port | UI Port |
|----------|----------|---------|
| main (offset 0) | 8000 | 3000 |
| feature-x (offset 1) | 8001 | 3001 |
| test-y (offset 2) | 8002 | 3002 |
| ... | 8000-8009 | 3000-3009 |

Run `make help` to see your current port assignments.

### Troubleshooting

**Port conflicts**:
```bash
# Check your assigned ports
make help

# Find what's using a port
lsof -i :8000  # macOS/Linux
netstat -ano | findstr :8000  # Windows

# Ports are auto-assigned based on branch name
# To force different ports, set in .env:
API_PORT=8005
UI_PORT=3005
```

**Shared infrastructure not found**:
```bash
# Verify infrastructure is running
docker network inspect niem-infra

# Start if needed
make infra-up
```

**Hot reload not working**:
```bash
# Verify you're in dev mode (not prod mode)
make logs | grep "uvicorn.*reload"

# Check file permissions (especially on Windows)
# Files must be readable by Docker
```

**Make command not found (Windows)**:
```bash
# Install Git for Windows (includes Git Bash)
# Download from: https://gitforwindows.org/

# Or use WSL2 for full Linux environment
```

**Build cache issues**:
```bash
# Rebuild without cache
docker compose build --no-cache --profile dev
make dev-up
```

## Complete Walkthrough: CrashDriver Sample Data

This section provides a comprehensive end-to-end walkthrough using the included CrashDriver sample data, demonstrating schema validation, data ingestion, error handling, graph visualization, and system administration.

### Step 1: Schema Upload - Testing Different Scenarios

The `samples/CrashDriver-cmf/` directory contains three schema folders to test different validation scenarios:

#### 1.1 Valid Schema Set (CrashDriverSchemaSet/) ✅

Navigate to the **"Schemas"** tab and upload the complete schema set:

1. **Select all XSD files** from `samples/CrashDriver-cmf/CrashDriverSchemaSet/`:
   - `CrashDriver.xsd` - Main exchange schema
   - `PrivacyMetadata.xsd` - Privacy extension schema
   - `niem/` folder - NIEM reference schemas (core, justice, human services)
   - `utility/` folder - NIEM utility schemas (structures, appinfo)

2. **Upload with NDR Validation Skipped** (for now):
   - ⚠️ Check **"Skip NDR Validation"** checkbox
   - Click upload

   > **TODO**: NDR validation for schema sets requires resolving rules by schema type: references, extensions, etc. Currently only the extension NDR rules are being applied causing validation errors acrros other schema types that would otherwise be valid.

3. **Expected Result**: Schema set uploads successfully and generates mapping

**What this schema defines**:
- `j:Crash` - Crash incident with date, location, vehicles
- `j:CrashDriver` / `j:CrashPerson` - Driver/person information
- `j:Charge` - Legal charges
- `j:PersonChargeAssociation` - Links persons to charges
- `nc:Metadata` / `priv:PrivacyMetadata` - Metadata and privacy controls

#### 1.2 Invalid Schema - Missing Imports (CrashDriverMissingImports/) ❌

Test error handling with incomplete schema:

1. **Upload files** from `samples/CrashDriver-cmf/CrashDriverMissingImports/`:
   - Only contains `CrashDriver.xsd` and `PrivacyMetadata.xsd`
   - Missing required NIEM import schemas

2. **Expected Result**:
   - Upload fails with validation errors
   - Error panel shows missing namespace/import errors
   - Schema is NOT stored or made available for activation

**Error Example**:
```
Validation Error: Cannot resolve import for namespace
'https://docs.oasis-open.org/niemopen/ns/model/niem-core/6.0/'
```

#### 1.3 Invalid Schema - NDR Violations (CrashDriverInvalidNDR/) ❌

Test NDR validation (when enabled):

1. **Upload** `samples/CrashDriver-cmf/CrashDriverInvalidNDR/invalid-schema.xsd`
2. **Without skipping NDR**: Upload will fail with NDR rule violations
3. **With skip checked**: Upload succeeds but schema may not work correctly

**Expected NDR Errors** (when validation enabled):
- Element naming violations
- Type definition errors
- Structure/pattern issues

### Step 2: Upload Valid XML Data

With the active schema set from Step 1.1, navigate to **"Upload Data"** tab → **"XML Files"** sub-tab:

#### 2.1 Valid XML Files ✅

Upload valid crash driver data:

1. **CrashDriver1.xml**:
   ```
   samples/CrashDriver-cmf/CrashDriver1.xml
   ```
   - Crash on 1907-05-04 at coordinates (51.87, -1.28)
   - Driver: Peter Death Bredon Wimsey (fictional character, born 1890-05-04)
   - License: A1234567
   - Injury with privacy metadata references
   - Charge: "Furious Driving" (not a felony)

2. **CrashDriver2.xml**:
   ```
   samples/CrashDriver-cmf/CrashDriver2.xml
   ```
   - Additional crash incident with different driver and charges

**Expected Result**:
- ✅ Validation passes
- Creates 20-50+ nodes per file
- Shows success message with node/relationship counts
- Files stored in MinIO `niem-data` bucket
- Graph structure reflects XML hierarchy

#### 2.2 Invalid XML Files - Testing Error Handling ❌

Upload invalid files to see error handling:

1. **CrashDriverInvalid1.xml** - Schema validation errors:
   ```
   samples/CrashDriver-cmf/CrashDriverInvalid1.xml
   ```
   - Contains elements not defined in schema
   - Shows expandable error panel with validation details

2. **CrashDriverInvalid2.xml** - Different validation issues:
   ```
   samples/CrashDriver-cmf/CrashDriverInvalid2.xml
   ```
   - Type mismatches or required element violations
   - Error panel shows specific line/column information

**Expected Error Display**:
```
❌ Validation failed: CrashDriverInvalid1.xml
```

### Step 3: Upload Valid JSON Data

Switch to **"JSON Files"** sub-tab:

#### 3.1 Valid JSON Files ✅

Upload JSON-LD formatted crash data:

1. **CrashDriver1.json**:
   ```
   samples/CrashDriver-cmf/CrashDriver1.json
   ```
   - Same crash data as XML but in JSON-LD format
   - Uses `@context` for namespace mappings
   - Uses `@id` for references (replaces XML `structures:ref`)

2. **Expected Result**:
   - ✅ JSON Schema validation passes
   - Creates graph with `qname` properties for proper display
   - Nodes labeled with NIEM qualified names (e.g., `j:Crash`, `nc:Person`)

#### 3.2 Invalid JSON Files - Testing Error Handling ❌

Upload invalid JSON to test validation:

1. **CrashDriverInvalid1.json** - Schema violations:
   ```
   samples/CrashDriver-cmf/CrashDriverInvalid1.json
   ```
   - Shows all validation errors at once (not just first error)
   - Detailed error messages with JSON paths

2. **CrashDriverInvalid2.json** - Additional test cases:
   ```
   samples/CrashDriver-cmf/CrashDriverInvalid2.json
   ```

   > **TODO**: JSON schema validation doesn't have required fields when generated from CMF and allows all other optional fields which allows other json files not related to schema to be uploaded. 

### Step 4: Graph Visualization

Navigate to the **"Graph"** tab to explore the ingested data:

#### 4.1 View Complete Graph

1. **Default query** loads automatically:
   ```cypher
   MATCH (n) OPTIONAL MATCH (n)-[r]-(m) RETURN n, r, m
   ```

2. **Graph Display**:
   - Nodes colored by type (auto-generated distinguishable colors)
   - Node labels show `qname` (e.g., `j:Crash`, `nc:Person`, `exch:CrashDriverInfo`)
   - Relationships labeled with types (`HAS_`, `J_PERSONCHARGEASSOCIATION`, etc.)
   - Interactive: click nodes/edges for details in brower development console by inspecting element. 

3. **Layout Options**:
   - Force Physics (default) - Smart force-directed layout
   - Circular - Nodes arranged in circle
   - Grid - Systematic arrangement
   - Hierarchical - Tree-like structure
   - Concentric - Layered by connectivity

4. **Legend Panel** (right side):
   - Shows all node types with colors
   - Lists relationship types with styling
   - Interaction help

### Step 5: Neo4j Direct Access

Open Neo4j Browser at **http://localhost:7474** (username: `neo4j`, password: `password`):

#### Explore Data Structure

1. **View full graph**:
   ```cypher
   MATCH (m) RETURN m
   ```

### Step 6: Verify Data Storage in MinIO

Access MinIO at **http://localhost:9002** (username: `minio`, password: `minio123`):

1. **niem-schemas bucket**:
   - Contains uploaded XSD schemas
   - CMF JSON representations
   - Generated mapping YAML files
   - Files organized by timestamp and hash

2. **niem-data bucket**:
   - Contains ingested XML/JSON files
   - Original file content preserved
   - File metadata and executed cypher query

### Step 7: System Administration

Navigate to the **"Admin"** tab:

#### 7.1 View System Status

- **Neo4j Statistics**:
  - Total node count
  - Total relationship count
  - Node types (labels) count
  - Relationship types count

- **Storage Status**:
  - MinIO bucket information
  - Schema storage status

#### 7.2 Reset the System

To clean all data and start fresh:

**Option 1: UI Admin Panel** (if available)
1. Go to Admin tab
2. Click "Reset System" button
3. Confirm reset operation

### Step 8: Full Cycle Test

Complete end-to-end test workflow:

1. ✅ Upload valid schema set (CrashDriverSchemaSet/, skip NDR)
2. ✅ Activate schema
3. ✅ Upload CrashDriver1.xml → Verify success
4. ❌ Upload CrashDriverInvalid1.xml → View errors
5. ✅ Upload CrashDriver1.json → Verify success
6. ❌ Upload CrashDriverInvalid1.json → View errors
7. 📊 View graph visualization → Explore nodes/relationships
8. 🔍 Query in Neo4j Browser → Run custom Cypher
9. 💾 Check MinIO → Verify file storage
10. 🔄 Admin reset → Clean system
11. 🔁 Repeat with different schemas/data

## Key Features Demonstrated

This walkthrough demonstrates:

1. **Schema Validation**:
   - ✅ Valid schema set upload with complete NIEM imports
   - ❌ Error handling for missing imports/dependencies
   - ⚠️ NDR validation with skip option for complex schema sets
   - 📋 Automatic mapping generation from XSD to graph model

2. **Multi-format Data Ingestion**:
   - XML with NIEM structures (ID/ref pattern)
   - JSON-LD with @context and @id references
   - Same graph model from both formats

3. **Comprehensive Error Handling**:
   - Schema validation errors with detailed messages
   - XML validation against XSD with line/column info
   - JSON Schema validation with all errors displayed at once
   - User-friendly expandable error panels

4. **Graph Modeling**:
   - XML/JSON hierarchy → Neo4j graph structure
   - Qualified names (qname) for readable node labels
   - Privacy metadata and reference relationships
   - Source file tracking for data provenance

5. **Interactive Graph Visualization**:
   - Auto-colored nodes by type
   - Multiple layout algorithms
   - Custom Cypher query support
   - Click for node/relationship details

6. **System Administration**:
   - Real-time statistics (node/relationship counts)
   - Complete system reset capability
   - MinIO storage verification
   - Health monitoring

## Next Steps

- Upload your own NIEM-compliant XSD schemas
- Test with different NIEM domains (Justice, Immigration, Emergency Management, etc.)
- Experiment with custom privacy extensions
- Build custom Cypher queries for your use case

## Known Issues & TODO

1. **Graph Visualizations**: Limitations on rebuilding graph UI from neo4j browser for full set of nodes and edges.

3. **Design Documentation**: Update architecture diagrams and component documentation to reflect current implementation.

4. **Version Control**: Implement semantic versioning mapped to NIEM versions for proper release management. See [GitHub Issues #1-5] for detailed plan.

## License

This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.

Copyright 2025 Christopher Jackson

### Third-Party Licenses

This project includes third-party software components:

- **NIEM CMF Tool** ([niemopen/cmftool](https://github.com/niemopen/cmftool)) - Apache License 2.0
- **NIEM NDR Tools** ([NIEM/NIEM-NDR](https://github.com/NIEM/NIEM-NDR)) - Creative Commons Attribution 4.0 International

See the [NOTICE](NOTICE) file for complete attribution details.






