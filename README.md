# NIEM Information Exchange - Proof of Concept

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

An demonstration of NIEM (National Information Exchange Model) data processing and graph ingestion system.

## Overview

This system provides end-to-end NIEM information exchange capabilities:

1. **Schema Management** - Upload and validate NIEM XSD schemas using CMF (Common Model Format) tools
2. **Data Ingestion** - Validate and ingest XML/JSON files against NIEM schemas
3. **Graph Storage** - Neo4j for storing and querying interconnected NIEM data
4. **Entity Resolution** - ML-based duplicate detection using Senzing SDK (with license) or text-based entity matching (without)
5. **Web Interface** - React/Next.js UI for management and monitoring
6. **Graph Visualization** - Interactive graph exploration and querying interface

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
     ↓
Entity Resolution (Optional) → Duplicate Detection → ResolvedEntity Nodes
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
- **Entity Resolution**: Detect and merge duplicate entities using ML or text-based entity matching
- **System Admin**: Health checks, statistics, reset operations

## Quick Start

### Prerequisites

- Docker Desktop installed and running
- Docker Compose (included with Docker Desktop)
- 8GB+ RAM recommended
- Ports 3000, 7474, 7687, 8000, 9000, 9001 available

### Entity Resolution & Senzing Setup (Optional)

The system supports two modes of entity resolution:

**Text-Based Matching (Default)**
- Works without any license - zero configuration
- Simple name matching with case-insensitive comparison
- Basic punctuation normalization
- Good for development and testing

**Senzing ML-Based Resolution (Optional - Requires License)**
- Machine learning-based entity matching
- Fuzzy name matching and phonetic matching
- Address standardization and date normalization
- Relationship analysis with confidence scoring
- Match transparency - see exactly why entities matched ([Match Details Feature](docs/SENZING_MATCH_DETAILS.md))

#### Quick License Setup

```bash
# 1. Get license from Senzing (contact support@senzing.com)
# 2. Unzip into api/ directory
unzip g2license_YYYYMMDD-HHMMSS.zip -d api/

# 3. Start system
docker compose up -d
```

License auto-decodes on startup and is shared with all services.

**Verify setup:**
```bash
./scripts/check_senzing.sh
```

See [docs/SENZING_SETUP.md](docs/SENZING_SETUP.md) for detailed setup and troubleshooting.

#### Common Issues

**License not detected?**
```bash
# Check folder structure
ls -la api/g2license_*/
# Should show a folder with g2.lic_base64 inside

# Check decoded license was created
ls -la api/secrets/senzing/g2.lic
# Should exist after restart

# Check permissions
chmod -R 755 api/g2license_*/
```

**Senzing SDK not found?**
- Docker: Installed automatically via uv
- Local dev: Run `uv pip install senzing-grpc` or `uv sync --all-extras`

#### Health Check

Verify Senzing is working correctly:

```bash
# Quick diagnostic script
./scripts/check_senzing.sh

# Or check via API
curl http://localhost:8000/api/entity-resolution/health \
  -H "Authorization: Bearer devtoken" | jq .
```

**Expected response when healthy**:
```json
{
  "overall_status": "healthy",
  "license_configured": true,
  "client_initialized": true,
  "connection_status": "healthy"
}
```

If status is "unhealthy", check:
- License file exists: `ls -la api/secrets/senzing/g2.lic`
- Services running: `docker compose ps`
- Logs: `docker compose logs senzing-grpc api`

**For detailed troubleshooting and alternative installation methods**, see:
- [Senzing Integration Guide](docs/senzing-integration.md) - Technical details, database configuration
- [Senzing Match Details](docs/SENZING_MATCH_DETAILS.md) - Match transparency features

### 1. Start the System

```bash
# Clone and enter directory
git clone <repository-url>
cd niem-info-exch-e2e

# Copy environment configuration
cp .env.example .env

# (Optional) Add your Senzing license for entity resolution
# See "Senzing License (Optional)" section above
# If you skip this, the system will use text-based entity matching

# Start all services (works with default dev credentials)
docker compose up -d

# Wait for services to be healthy (2-3 minutes)
docker compose ps
```

**Note:** The system ships with default credentials for development convenience. You can start using it immediately without changing any passwords. For production deployments, see the [Security & Production Deployment](#security--production-deployment) section.

### 2. Access the Web Interface

Open http://localhost:3000 in your browser

### 3. Development Workflow with Hot Reloading

For local development, the project includes a `docker-compose.override.yml` file that enables hot reloading for both API and UI services. This file is **automatically applied** when you run `docker compose up`.

#### What Gets Hot Reloaded

- **API Changes**: Any Python file changes in `./api/src` trigger automatic reload via uvicorn
- **UI Changes**: Any code changes in `./ui/src`, `./ui/app`, components, styles, etc. trigger Next.js Fast Refresh

#### Development Commands

```bash
# Start with hot reloading (override is auto-applied)
docker compose up

# Or in detached mode
docker compose up -d

# View live logs
docker compose logs -f api
docker compose logs -f ui
```

#### When You Still Need to Rebuild

Hot reloading works for code changes, but you need to rebuild for:

| Change Type | Command | Reason |
|-------------|---------|--------|
| Python dependencies (`pyproject.toml`, `uv.lock`) | `docker compose up -d --build api` | New packages need installation |
| Node dependencies (`package.json`) | `docker compose up -d --build ui` | npm packages need installation |
| Dockerfile changes | `docker compose up -d --build` | Container configuration changed |
| Environment variables (`.env`) | `docker compose restart` | No rebuild needed, just restart |

#### Testing Hot Reload

To verify hot reloading is working, you can test both API and UI changes:

**Method 1: Watch Logs (Recommended)**

Open separate terminals to watch logs:

```bash
# Terminal 1: Watch API logs
docker compose logs -f api

# Terminal 2: Watch UI logs
docker compose logs -f ui
```

**Method 2: Test API Hot Reload**

1. Make a change to any Python file in `./api/src/`:
   ```bash
   # Example: Edit api/src/niem_api/main.py
   # Add a message to the readyz endpoint return value
   ```

2. Watch the API logs - you'll see:
   ```
   WARNING:  WatchFiles detected changes in 'src/niem_api/main.py'. Reloading...
   INFO:     Application startup complete.
   ```

3. Test the change:
   ```bash
   curl http://localhost:8000/readyz
   ```

**Method 3: Test UI Hot Reload**

1. Open http://localhost:3000 in your browser

2. Make a change to any file in `./ui/src/`:
   ```bash
   # Example: Edit ui/src/pages/index.tsx
   # Change the Dashboard heading text
   ```

3. Watch your browser - it should automatically refresh (Fast Refresh)

4. Check UI logs for compilation:
   ```
   ✓ Compiled /pages/index in XXXms
   ```

**Method 4: Test from Browser Console**

Open your browser's developer console (F12) and watch the Network tab while making UI changes. You'll see Hot Module Replacement (HMR) websocket messages.

#### Local Development without Docker (using uv)

For developers who prefer to run the API locally without Docker:

**Prerequisites:**
- Python 3.12+
- [uv](https://docs.astral.sh/uv/) package manager

**Setup:**

```bash
# Install uv (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Navigate to the API directory
cd api

# Install dependencies (uv will auto-install Python 3.12 if needed)
uv sync --all-extras

# Run the API server
uv run uvicorn src.niem_api.main:app --host 0.0.0.0 --port 8000 --reload
```

**Running tests:**

```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=src --cov-report=html

# Run specific test types
uv run pytest tests/unit/
uv run pytest tests/integration/
```

**Code quality checks:**

```bash
# Linting
uv run ruff check src/

# Formatting
uv run black src/

# Type checking
uv run mypy src/
```

**Note:** You'll still need Neo4j and MinIO running (via Docker or natively) for the API to function properly.

#### Production Deployment

For production, **ignore or remove** the `docker-compose.override.yml` file:

```bash
# Option 1: Explicitly use only base config
docker compose -f docker-compose.yml up -d

# Option 2: Add to .gitignore or .dockerignore for production builds
echo "docker-compose.override.yml" >> .gitignore
```

### 4. Rebuilding After Code Changes (Production)

When deploying to production or when hot reloading isn't available:

#### Rebuild All Services (API + UI)

```bash
# Stop services
docker compose down

# Rebuild and restart all services
docker compose up -d --build

# Or in one command:
docker compose up -d --build --force-recreate
```

#### View Logs

Check logs during/after rebuild to verify successful startup:

```bash
# All services
docker compose logs -f

# Specific service
docker compose logs -f api
docker compose logs -f ui

# Last 50 lines
docker compose logs --tail=50 api
```

#### Common Rebuild Scenarios

| Scenario | Command | Notes |
|----------|---------|-------|
| Pull latest code | `git pull && docker compose up -d --build` | Rebuilds changed services |
| API code changes | `docker compose up -d --build api` | Python dependencies cached unless requirements change |
| UI code changes | `docker compose up -d --build ui` | npm dependencies cached unless package.json changes |
| Environment changes | `docker compose down && docker compose up -d` | No rebuild needed for .env changes |
| Dependency updates | `docker compose build --no-cache` then `docker compose up -d` | Forces fresh install of all dependencies |
| Complete reset | `docker compose down -v && docker compose up -d --build` | Removes volumes (deletes all data!) |


## Complete Walkthrough: CrashDriver Sample Data

> **Sample Data Sources:** The Crash Driver example is sourced from the [CrashDriver repository](https://github.com/iamdrscott/CrashDriver) maintained by iamdrscott. The NEICE IEPD sample is sourced from the [NEICE Clearinghouse Direct Technical Documents](https://support.neice.us/support/solutions/articles/6000251773-current-neice-clearinghouse-direct-technical-documents) and the [NEICE Clearinghouse attachment](https://support.neice.us/helpdesk/attachments/6173370056).

This section provides a comprehensive end-to-end walkthrough using the included CrashDriver sample data, demonstrating schema validation, data ingestion, error handling, graph visualization, and system administration.

## Part 1: CrashDriver Sample - Happy Path with Entity Resolution

This walkthrough demonstrates the complete workflow using the CrashDriver NIEM 6.0 sample, including schema upload, data ingestion, graph visualization, and entity resolution.

### Step 1: Upload CrashDriver Schema

Navigate to the **"Schemas"** tab and upload the CrashDriver model schema:

1. **Select all XSD files** from `samples/CrashDriver/model.xsd/`:
   - `CrashDriver.xsd` - Main exchange schema
   - `PrivacyMetadata.xsd` - Privacy extension schema
   - `niem/` folder - NIEM reference schemas (core, justice, human services, adapters)
   - `utility/` folder - NIEM utility schemas (structures, appinfo)

   a. Make sure to set CrashDriver.xsd as the primary schema in the UI.

2. **First Upload Attempt - WITH NDR Validation**:
   - Do NOT check "Skip NDR Validation"
   - Click upload
   - **Expected Result**: Upload fails with validation errors
   - Some files are not conformant to NIEM 6.0 naming design rules
   - Error messages indicate NDR violations

3. **Second Upload Attempt - Skip NDR Validation**:
   - ⚠️ Check **"Skip NDR Validation"** checkbox
   - Click upload again
   - **Expected Result**: 
     - Schema set uploads successfully
     - Schema appears in the uploaded schemas list

4. **After Upload**:
   - Option to design graph schema appears - **Skip and use defaults instead**
   - Schema is now available for use
   - You can download:
     - **CMF (Common Model Format) file** - How NIEM defines schemas for format conversion
     - **JSON Schema** - Used for validating JSON instance documents

**What this schema defines**:
- `exch:CrashDriverInfo` - Root element for crash driver reports
- `j:Crash` - Crash incident with date, location, vehicles
- `j:CrashDriver` / `j:CrashPerson` - Driver/person information with URI-based references
- `j:Charge` - Legal charges
- `j:PersonChargeAssociation` - Links persons to charges
- `nc:Metadata` / `priv:PrivacyMetadata` - Metadata and privacy controls

### Step 2: Upload msg2.xml and View Graph

Navigate to **"Upload Data"** tab → **"XML Files"** sub-tab:

1. **Upload** `samples/CrashDriver/examples/msg2.xml`:
   - This file contains multiple crash persons, crash drivers, and associations
   - Crash on 1907-05-04 at coordinates (51.87, -1.28)
   - Multiple persons:
     - P01: Peter Death Bredon Wimsey (driver, injured, charged)
     - P02: Harriet Deborah Wimsey (crash person, married to P01)
     - P03: Mervyn Bunder (crash person, household member/butler/valet of P01)
   - Charge: "Furious Driving" (linked to P01)
   - Demonstrates `structures:uri` references for entity resolution

2. **Expected Result**:
   - ✅ Validation passes
   - Creates 28 nodes
   - Shows success message with node/relationship counts
   - File stored in MinIO `niem-data` bucket

3. **View the Graph** - Navigate to **"Graph"** tab:
   - **Associations**: View relationship nodes like `j:PersonChargeAssociation`, `nc:PersonUnionAssociation`, `hs:PersonOtherKinAssociation`
   - **Entities from multiple URIs or IDs**: See how person P01 appears in multiple roles:
     - `j:CrashDriver` with `structures:uri="#P01"`
     - `j:CrashPerson` with `structures:uri="#P01"`
     - Same person entity referenced across different roles
   - **Full view of entire instance document (not flattened)**: 
     - Complete hierarchical structure preserved
     - All nested elements visible as separate nodes
     - Relationships show the full XML document structure
     - See the complete graph representation of the entire instance document

### Step 3: Upload msg2.json

Switch to **"JSON Files"** sub-tab:

1. **Upload** `samples/CrashDriver/examples/msg2.json`:
   - Same crash data as msg2.xml but in JSON-LD format
   - Uses `@id` for references (replaces XML `structures:uri`)
   - Demonstrates multi-format ingestion

2. **Expected Result**:
   - ✅ JSON Schema validation passes
   - Creates the same graph structure as the XML version
   - Same nodes and relationships as XML version
   - Nodes labeled with NIEM qualified names (e.g., `j:Crash`, `nc:Person`)
   - URI references properly resolved
   - Verify in the Graph tab that the structure matches msg2.xml 

### Step 4: Entity Resolution with Senzing SDK (First Pass)

After uploading both msg2.xml and msg2.json, run Senzing entity resolution:

1. **Navigate to Graph Tab** and open the **Entity Resolution** panel:
   - Click "Entity Resolution" in the sidebar
   - Verify it shows "Method: Senzing SDK" (requires Senzing license - see Setup section)

2. **Select Node Types**:
   - Select `j:CrashPerson` and `j:CrashDriver`
   - **How node selection works**:
     - Nodes available to select dynamically pull person, org, location elements from NIEM core model
     - System checks if these properties exist on a child node 1-3 hops away OR are flattened onto a node itself
     - This allows entity resolution to work with various graph structures

3. **Run Resolution**:
   - Click "Run Entity Resolution"
   - See `ResolvedEntity` nodes be created
   - Shows statistics (entities found, duplicates detected, confidence scores)

4. **Expected Results**:
   - **Cross-Format Entity Resolution**: Same people from both XML and JSON files are matched:
     - Person P01 (Peter Death Bredon Wimsey) from msg2.xml matched with P01 from msg2.json
     - Person P02 (Harriet Deborah Wimsey) from msg2.xml matched with P02 from msg2.json
     - Person P03 (Mervyn Bunder) from msg2.xml matched with P03 from msg2.json
   - **ResolvedEntity nodes** created linking:
     - Same persons across XML and JSON formats
     - Same persons across different roles within the incident
   - View resolved entities in the graph or query:
     ```cypher
     MATCH (n)-[:RESOLVED_TO]->(re:ResolvedEntity)
     RETURN n, re
     ```

### Step 5: View Neo4j Browser, MinIO Browser, and Uploaded Files

1. **Open Neo4j Browser**:
   - Navigate to **http://localhost:7474**
   - Login with username: `neo4j`, password: `password` (or your configured password)
   - Explore the graph data directly with Cypher queries:
     ```cypher
     MATCH (n) RETURN n
     ```
   - See all the nodes and relationships created from msg2.xml and msg2.json
   - Query for specific entities or relationships

2. **Access MinIO Browser**:
   - Navigate to **http://localhost:9002**
   - Login with username: `minio`, password: `minio123` (or your configured password)
   - **View uploaded schemas** in `niem-schemas` bucket:
     - Contains uploaded XSD schemas from `model.xsd/`
     - CMF JSON representations
     - Generated mapping YAML files
     - Files organized by timestamp and hash
   - **View uploaded instance files** in `niem-data` bucket:
     - `msg2.xml` - Original XML file
     - `msg2.json` - Original JSON file
     - File metadata and executed cypher queries
     - Original file content preserved

3. **Verify File Storage**:
   - Confirm both XML and JSON files are stored
   - Check file metadata shows correct upload timestamps
   - Verify schema files are properly stored

### Step 6: Reset System

Before proceeding to the schema design workflow, reset the system:

1. **Reset Uploaded Instance Files**:
   - Navigate to **"Admin"** tab (or use API)
   - Reset uploaded instance files
   - This clears the data files from MinIO `niem-data` bucket

2. **Reset Neo4j Database**:
   - Reset Neo4j database to clear all graph data
   - This removes all nodes and relationships
   - Graph is now empty and ready for the next part

3. **Expected Result**:
   - All uploaded instance files cleared
   - Neo4j database empty
   - Graph ready for schema design workflow

### Step 7: Schema Design Workflow

Now we'll create a schema design to filter which nodes appear in the graph:

1. **Go to Schema Page**:
   - Navigate to **"Schemas"** tab
   - Find the uploaded CrashDriver `model.xsd` schema

2. **Open Graph Designer**:
   - Click on the schema to open Graph Designer
   - Or navigate to **"Schema Designer"** tab and select the model.xsd schema

3. **Select Specific Elements**:
   - Create a new schema design
   - Select the following elements:
     - `exch:CrashDriverInfo` - Root element
     - `j:Crash` - Crash event
     - `j:Charge` - Criminal charges
     - `j:CrashDriver` - Drivers involved
     - `j:CrashPerson` - Persons involved
     - `j:PersonChargeAssociation` - Association linking persons to charges
   - Include all associations between these selected elements
   - Save the schema design

4. **Re-upload msg2.xml**:
   - Navigate to **"Upload Data"** tab → **"XML Files"** sub-tab
   - Upload `samples/CrashDriver/examples/msg2.xml` again
   - **Expected Result**: Should see ONLY the selected nodes appear (filtered graph)
   - Graph now shows only the elements specified in the schema design
   - Other elements from the full document are excluded

5. **Re-upload msg2.json**:
   - Switch to **"JSON Files"** sub-tab
   - Upload `samples/CrashDriver/examples/msg2.json` again
   - **Expected Result**: Should see same filtered graph as XML version
   - Only the selected elements appear in the graph

6. **Run Senzing Entity Resolution Again**:
   - Navigate to **"Graph"** tab
   - Open Entity Resolution panel
   - Select `j:CrashDriverType` and `j:CrashPersonType`
   - Click "Run Entity Resolution"
   - **Expected Result**: 
     - See that crash driver can be resolved via Senzing SDK
     - ResolvedEntity nodes created for the filtered schema design
     - Entity resolution works with the selected elements only
     - Demonstrates how schema design affects entity resolution scope

## Key Features Demonstrated

This walkthrough demonstrates:

1. **Schema Validation**:
   - ✅ NIEM conformant schema set upload
   - ❌ Error handling for missing imports/dependencies
   - ⚠️ NDR validation with skip option for complex schema sets
   - 📋 Automatic mapping generation from XSD to graph model

2. **Graph Schema Designer**:
   - Select nodes to build in graph and flatten graph for differnet analytics usecases
   - Dynamic graph creation from instance data when no mapping applied
   - View schema node properties and types (associations, augmentations)

3. **Multi-format Data Ingestion**:
   - XML with NIEM structures (ID/ref pattern) validated against XSD schema
   - JSON-LD with @context and @id references validated against JSON schema (generated via CMF Tool)
   - Same graph model from both formats

4. **Comprehensive Error Handling**:
   - Schema validation errors with detailed messages
   - XML validation against XSD with line/column info
   - JSON Schema validation with all errors displayed at once
   - User-friendly expandable error panels

5. **Graph Modeling**:
   - XML/JSON hierarchy → Neo4j graph structure
   - Qualified names (qname) for readable node labels
   - Resolved Entity, Association, and Reference relationships
   - Source file tracking for data provenance

6. **Entity Resolution**:
   - Dynamic node type selection from graph
   - Dual-mode operation: Senzing SDK (with license) or text-based entity matching
   - Creates ResolvedEntity nodes for duplicates
   - Confidence scoring and relationship tracking

7. **Interactive Graph Visualization**:
   - Auto-colored nodes by type
   - Multiple layout algorithms
   - Custom Cypher query support
   - Click for node/relationship details

8. **System Administration**:
   - Real-time statistics (node/relationship counts)
   - Complete system reset capability
   - MinIO storage verification
   - Health monitoring


## Security & Production Deployment

### ⚠️ Default Credentials Warning

This system ships with **default credentials for development convenience**. These MUST be changed for production deployments!

#### Default Credentials (Change These!)

| Service | Username | Default Password | Environment Variable |
|---------|----------|------------------|---------------------|
| Neo4j | `neo4j` | `password` | `NEO4J_PASSWORD` |
| MinIO | `minio` | `minio123` | `MINIO_ROOT_PASSWORD` |
| API Auth | N/A | `devtoken` | `DEV_TOKEN` |
| Senzing PostgreSQL | `senzing` | `changeme` | `SENZING_DB_PASSWORD` |

### Production Security Checklist

Before deploying to production, complete these security steps:

#### 1. **Change All Default Passwords**

Generate strong, random passwords for all services:

```bash
# Generate strong passwords
openssl rand -base64 32  # For passwords
openssl rand -hex 32     # For tokens

# Update your .env file with new passwords
# NEVER commit your .env file to version control!
```

Edit `.env` and update these variables:
- `NEO4J_PASSWORD` - Neo4j database password
- `MINIO_ROOT_PASSWORD` - MinIO object storage password
- `DEV_TOKEN` - API authentication token
- `SENZING_DB_PASSWORD` - Senzing PostgreSQL password (if using Senzing)

#### 2. **Verify .env is Not Committed**

The `.env` file is already in `.gitignore`, but double-check:

```bash
# This should show .env is ignored
git check-ignore .env

# Verify .env is not tracked
git ls-files | grep "^\.env$"  # Should return nothing
```

#### 3. **Senzing License Security**

The Senzing license contains sensitive information:

- ✅ License folders (`g2license_*`) are automatically gitignored
- ✅ Decoded license files (`api/secrets/`) are gitignored
- ⚠️ Never commit license files to version control
- ⚠️ Never share license files publicly
- ✅ License is automatically decoded from `api/g2license_*/` on startup

#### 4. **Production Deployment Recommendations**

For production environments:

1. **Use Docker Secrets** (for Docker Swarm) or **Kubernetes Secrets**
   ```bash
   # Example with Docker Secrets
   echo "your-strong-password" | docker secret create neo4j_password -
   ```

2. **Enable HTTPS/TLS**
   - Add nginx or traefik reverse proxy
   - Configure SSL certificates (Let's Encrypt recommended)
   - Update `MINIO_SECURE=true` for MinIO TLS

3. **Network Security**
   - Use Docker networks to isolate services
   - Don't expose internal ports (7687, 9000, 5432) to public
   - Only expose ports 80/443 through reverse proxy

4. **Enable PostgreSQL SSL** (if using Senzing with PostgreSQL)
   - Configure PostgreSQL with SSL certificates
   - Update connection strings to use `sslmode=require`

5. **Rotate Credentials Regularly**
   - Implement password rotation policy (quarterly recommended)
   - Update API tokens periodically

#### 5. **Audit Logs & Monitoring**

Enable logging and monitoring for security events:

```bash
# View authentication logs
docker compose logs api | grep -i "auth\|token"

# Monitor failed login attempts
docker compose logs api | grep -i "401\|403"

# Check Neo4j security logs
docker compose logs neo4j | grep -i "auth\|failed"
```

### Environment Variable Reference

All sensitive configuration is externalized to environment variables. See `.env.example` for the complete list with descriptions.

**Required for basic operation:**
- `NEO4J_PASSWORD` - Must be changed from default
- `MINIO_ROOT_PASSWORD` - Must be changed from default
- `DEV_TOKEN` - Must be changed from default

**Required for Senzing entity resolution:**
- Senzing license (via `api/g2license_*/` folder - auto-detected)
- `SENZING_DB_PASSWORD` - PostgreSQL password for Senzing

**Optional customization:**
- `SENZING_GRPC_URL` - Senzing gRPC server URL (default: `senzing-grpc:8261`)
- `SENZING_CONFIG_PATH` - Path to g2.ini config (default: `/app/config/g2.ini`)

### Security Warnings in Logs

The system will log security warnings when running with default credentials:

```
⚠️  Using default DEV_TOKEN='devtoken'. Set DEV_TOKEN environment variable for production!
```

These warnings indicate security issues that should be addressed before production deployment.

Limited Functionality

1. **JSON Schema Conversion**: CMFTool v1.0 has a bug that prevents JSON Schema generation for certain NIEM 3.0 schemas (e.g., NEICE IEPD). This affects JSON file schema validation but can still ingestion JSON instance data against graph mapping. See [docs/KNOWN_ISSUES.md](docs/KNOWN_ISSUES.md) for details and workarounds.

## License

This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.

Copyright 2025 Christopher Jackson

### Third-Party Licenses

This project includes third-party software components:

- **NIEM CMF Tool** ([niemopen/cmftool](https://github.com/niemopen/cmftool)) - Apache License 2.0
- **NIEM Naming Design Rules** ([niemopen/niem-naming-design-rules](https://github.com/niemopen/niem-naming-design-rules)) - Creative Commons Attribution 4.0 International
See the [NOTICE](NOTICE) file for complete attribution details.






