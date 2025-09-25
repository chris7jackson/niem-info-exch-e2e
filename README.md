# NIEM Information Exchange - Proof of Concept

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

## Quick Start

### Prerequisites

- Docker Desktop installed and running
- Docker Compose (included with Docker Desktop)
- 8GB+ RAM recommended
- Ports 3000, 7474, 7687, 8000, 9000, 9001 available

### 1. Start the System

```bash
# Clone and enter directory
git clone <repository-url>
cd niem-info-exch-e2e

# Copy environment configuration
cp .env.example .env

# Start all services
docker compose up -d

# Wait for services to be healthy (2-3 minutes)
docker compose ps
```

### 2. Access the Web Interface

Open http://localhost:3000 in your browser

## Complete Walkthrough: CrashDriver Sample Data

This section provides a comprehensive walkthrough using the included CrashDriver sample data, which demonstrates a NIEM information exchange for crash incident reporting with driver and legal charge information.

### Step 1: Upload the CrashDriver Schema

1. Navigate to the **"Schemas"** tab in the web interface
2. Click the upload area or drag and drop the schema file:
   ```
   samples/CrashDriver-cmf/CrashDriver.xsd
   ```
3. The system will:
   - Validate the XSD against NIEM NDR (National Data Representation) rules
   - Use the CMF (Common Model Format) tool for validation
   - Display any validation errors with expandable details if issues are found
   - Store the schema in MinIO object storage upon successful validation

**Expected Result**: The schema should upload successfully and appear in the schemas list. Click **"Activate"** to make it the active schema for data ingestion.

### Step 2: Understanding the CrashDriver Schema

The CrashDriver schema (`CrashDriver.xsd`) defines:

- **CrashDriverInfoType**: Main container for crash driver information
- **Core Elements**:
  - `j:Crash` - Crash incident details (date, location, vehicles)
  - `j:Charge` - Legal charges associated with the incident
  - `j:PersonChargeAssociation` - Links between persons and charges
  - `nc:PersonUnionAssociation` - Person relationship associations
  - `nc:Metadata` and `priv:PrivacyMetadata` - Metadata and privacy controls

**Namespaces Used**:
- `nc:` - NIEM Core (common data elements)
- `j:` - Justice domain (crash, charges, legal concepts)
- `hs:` - Human Services domain (family relationships)
- `priv:` - Privacy metadata extension
- `structures:` - NIEM structural elements (references, IDs)

### Step 3: Upload Sample XML Data

Navigate to the **"Upload Data"** tab and select the **XML Files** sub-tab:

1. **Upload CrashDriver1.xml**:
   ```
   samples/CrashDriver-cmf/CrashDriver1.xml
   ```
   This file contains:
   - Crash incident from 1907-05-04 at coordinates (51.87, -1.28)
   - Driver: Peter Death Bredon Wimsey (fictional character)
   - Driver details: Birth date, license ID, adult status
   - Injury information with privacy metadata references

2. **Upload CrashDriver2.xml**:
   ```
   samples/CrashDriver-cmf/CrashDriver2.xml
   ```
   Contains additional crash incident data with different persons and charges

3. **Optional - Test Invalid Data**:
   ```
   samples/CrashDriver-cmf/CrashDriverInvalid.xml
   ```
   This will demonstrate XSD validation failure with detailed error messages

**Processing Flow**:
- Files undergo validation against the active XSD schema using the CMF tool
- Valid XML is parsed into a graph structure
- Each XML element becomes a Neo4j node with element tag as label
- XML containment hierarchy becomes CONTAINS relationships
- Text content and attributes are preserved as node properties

### Step 4: Upload Sample JSON Data

Switch to the **JSON Files** sub-tab and upload:

1. **CrashDriver1.json** and **CrashDriver2.json**:
   ```
   samples/CrashDriver-cmf/CrashDriver1.json
   samples/CrashDriver-cmf/CrashDriver2.json
   ```

**JSON Processing**:
- JSON objects become container nodes with sanitized key names as labels
- Arrays become container nodes with indexed child nodes
- Primitive values become leaf nodes with content
- `@id` and `@context` JSON-LD elements are handled appropriately

### Step 5: Verify Data Ingestion

**Check Upload Results**:
- Review the ingestion results displayed after each upload
- Look for successful node and relationship creation counts
- Check the "Uploaded Files" section to see processed files

**Expected Ingestion Results**:
- Each CrashDriver XML/JSON file should create 50-100+ nodes
- Relationships should reflect XML hierarchy and JSON nesting
- No validation errors for valid files

### Step 6: Explore the Graph in Neo4j

Open the Neo4j Browser at http://localhost:7474 (username: `neo4j`, password: `password`)

**Basic Graph Exploration**:

1. **View all data**:
   ```cypher
   MATCH (n) RETURN n LIMIT 25
   ```

2. **See node types created**:
   ```cypher
   MATCH (n) RETURN DISTINCT labels(n), count(n) ORDER BY count(n) DESC
   ```

3. **View relationship types**:
   ```cypher
   MATCH ()-[r]->() RETURN type(r), count(r) ORDER BY count(r) DESC
   ```

### Step 7: Data Storage Verification

**MinIO Object Storage** (http://localhost:9001, user: `minio`, password: `minio123`):
- Check `niem-schemas` bucket for the uploaded XSD schema
- Check `niem-data` bucket for the ingested XML/JSON files
- Files are stored with timestamps and hash prefixes for uniqueness


### Step 8: Test Error Handling

**Upload Invalid Data**:
1. Try uploading `CrashDriverInvalid.xml` to see XSD validation errors
2. The expandable error component will show detailed validation failures
3. Try uploading files without an active schema to see validation requirements

**Expected Error Types**:
- Schema validation failures for files that don't conform to the active XSD schema (via CMF tool)
- Missing active schema errors
- File format validation errors

### Step 9: System Administration

**View System Status**:
- Go to the **"Admin"** tab to see Neo4j statistics
- Check node counts, relationship counts, and graph health

**Reset System** (if needed):
```bash
curl -X POST http://localhost:8000/api/admin/reset \
  -H "Authorization: Bearer devtoken" \
  -H "Content-Type: application/json" \
  -d '{"neo4j":true,"minio":true,"dry_run":false}'
```

## Key Features Demonstrated

This walkthrough demonstrates:

1. **NIEM Compliance**: Full NDR validation and CMF tool integration
2. **Multi-format Support**: Both XML and JSON ingestion from the same schema
3. **Graph Modeling**: Hierarchical XML/JSON structures as connected graph data
4. **Privacy Controls**: Privacy metadata handling and references
5. **Error Handling**: Comprehensive validation with user-friendly error display
6. **Real-time Processing**: Immediate graph creation from uploaded data
7. **Data Provenance**: Source file tracking in all generated nodes

## Next Steps

- Experiment with other NIEM-compliant XSD schemas
- Try different XML/JSON data structures


TODO LIST:
1. Determing way to flatten graph creation to specified entities so that it's not a deep graph where every element attribute becomes a node. Current view is difficult to read and parse.
2. Graph visualization is limited and needs a better implementation of fetching and showing graph data on UI. 
3. Graph generation process and pipeline needs review. 
4. Design documentation needs to be updated to reflect current architecture and components. 





