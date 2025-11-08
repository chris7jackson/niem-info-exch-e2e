# Senzing Entity Resolution Integration

This document describes the Senzing SDK integration for dynamic entity resolution in the NIEM GraphRAG system.

## Overview

The system supports two modes of entity resolution:
1. **Senzing SDK** - ML-based entity resolution using the Senzing engine (requires license)
2. **Text-Based Entity Matching** - Simple name-matching fallback when Senzing is not available

## Configuration

### Environment Variables

All Senzing configuration is managed through environment variables. See `.env.example` for full documentation.

Key variables:
- `SENZING_LICENSE_PATH` - Path to Senzing license file (required for Senzing mode)
- `SENZING_DATABASE_URL` - Full database connection string (recommended)
- `SENZING_DB_TYPE` - Database type if not using full URL (sqlite, postgresql, mysql)

### Database Support

The system supports three database backends for Senzing:

1. **SQLite** (default for development)
   ```bash
   SENZING_DB_TYPE=sqlite
   # or
   SENZING_DATABASE_URL=sqlite3://na:na@/data/senzing/sqlite/g2.db
   ```

2. **PostgreSQL** (recommended for production)
   ```bash
   SENZING_DATABASE_URL=postgresql://user:password@host:port/database
   ```

3. **MySQL**
   ```bash
   SENZING_DATABASE_URL=mysql://user:password@host:port/database
   ```

## Field Mappings

NIEM-to-Senzing field mappings are configured in `api/config/niem_senzing_mappings.yaml`. This file defines:
- How NIEM entity fields map to Senzing features
- Entity type categorization (PERSON, ORGANIZATION, LOCATION, etc.)
- Recommended entity types for resolution

## Testing the Integration

### 1. Check Senzing Availability

```bash
# Check if Senzing is available
curl http://localhost:8000/api/entity-resolution/status \
  -H "Authorization: Bearer devtoken"
```

Response will indicate if Senzing SDK is available:
```json
{
  "senzing_available": false,
  "mode": "text_based",
  "message": "Using text-based entity matching (Senzing not available)"
}
```

### 2. Get Available Node Types

```bash
# Get node types that can be resolved
curl http://localhost:8000/api/entity-resolution/node-types \
  -H "Authorization: Bearer devtoken"
```

### 3. Run Entity Resolution

```bash
# Run resolution on selected node types
curl -X POST http://localhost:8000/api/entity-resolution/run \
  -H "Authorization: Bearer devtoken" \
  -H "Content-Type: application/json" \
  -d '{
    "selectedNodeTypes": ["nc:PersonType", "nc:OrganizationType"]
  }'
```

### 4. View Results in UI

1. Navigate to the Graph page: http://localhost:3000/graph
2. Click "Entity Resolution" in the sidebar
3. Select node types to resolve
4. Click "Run Entity Resolution"
5. View resolved entities in the graph

## Senzing License Setup

The system supports three methods for installing a Senzing license:

### Method A: License Folder Auto-Detection (Recommended)

This is the **easiest method** - the system automatically detects and decodes your license!

```bash
# 1. Unzip your license folder into the api/ directory
unzip g2license_20251201-120000.zip -d api/

# 2. Verify the structure
ls api/g2license_20251201-120000/g2.lic_base64
# Should show: api/g2license_20251201-120000/g2.lic_base64

# 3. Restart the API container
docker compose restart api

# 4. Check logs to confirm
docker compose logs api | grep -i senzing
# Should show: "✅ Senzing license decoded successfully"
```

**What the system expects:**
- Folder name pattern: `g2license_*` (e.g., `g2license_20251201-120000`)
- File inside folder: `g2.lic_base64` (base64-encoded license)
- Location: `api/g2license_*/g2.lic_base64`

The system automatically:
1. Searches for `g2license_*` folders in `api/` directory on startup
2. Finds the `*.lic_base64` file inside
3. Decodes it and saves to `api/secrets/senzing/g2.lic`
4. Initializes Senzing with the decoded license

**Note**: If you have multiple license folders, the system uses the most recent one (sorted by folder name).

### Method B: Direct File Placement (Advanced)

If you already have a decoded `g2.lic` file (not base64-encoded):

```bash
# Copy your decoded license file to the secrets directory
mkdir -p api/secrets/senzing
cp /path/to/your/g2.lic api/secrets/senzing/g2.lic

# Restart the API container
docker compose restart api
```

### Method C: Environment Variable (Docker Services Only)

This method is for configuring separate Docker services (senzing-grpc, senzing-init), not the main API:

```bash
# Encode your license file
base64 < /path/to/your/g2.lic > license_base64.txt

# Add to .env file
echo "SENZING_LICENSE_BASE64=$(cat license_base64.txt)" >> .env

# Restart services
docker compose down
docker compose up -d
```

**Note**: The API service uses Method A (g2license_* folder), not this environment variable.

## Troubleshooting

### License Not Detected

**If using Method A (g2license_* folder):**
```bash
# 1. Check if the license folder exists with correct structure
ls -la api/g2license_*/
# Should show a folder with g2.lic_base64 file inside

# 2. Check if the file has correct naming pattern
ls api/g2license_*/g2.lic_base64
# Should show the base64 encoded license file

# 3. Check API logs for license detection
docker compose logs api | grep -i license
# Look for: "Searching for Senzing license in..." and "✅ Senzing license decoded successfully"

# 4. Verify decoded license was created
ls -la api/secrets/senzing/g2.lic
# Should show the decoded license file (created automatically)

# 5. Check folder permissions (must be readable by Docker)
chmod -R 755 api/g2license_*/
```

**If the license folder pattern doesn't match:**
- Ensure folder name starts with `g2license_`
- License file inside must be named `g2.lic_base64` or end with `.lic_base64`
- If you have a different structure, use Method B (direct file placement) instead

**If using Method B (direct file placement):**
```bash
# Check file permissions
ls -la api/secrets/senzing/
# g2.lic should exist and be readable

# Verify file is a valid license (not base64)
file api/secrets/senzing/g2.lic
# Should NOT say "ASCII text" (that would be base64-encoded)
```

### Senzing SDK Not Found

- In Docker: Should be installed automatically via requirements.txt
- Local dev: Run `pip install senzing-grpc` (for SDK v4 with gRPC)
- Check logs: `docker compose logs api | grep -i "senzing.*import"`

### Database Connection Issues

**For SQLite (default):**
- Ensure data directory exists and is writable
- Check write permissions on `/data/senzing` volume
- Verify database file: `ls -la /data/senzing/sqlite/g2.db` (inside container)

**For PostgreSQL (production):**
- Verify `SENZING_DATABASE_URL` format: `postgresql://user:password@host:port/database`
- Check `SENZING_DB_PASSWORD` is set in `.env` and matches docker-compose.yml
- Test connection: `docker compose logs senzing-postgres`
- Ensure database exists and user has permissions

**For MySQL:**
- Verify connection string format: `mysql://user:password@host:port/database`
- Test connection with database client
- Ensure database exists and user has permissions

### License File Format Issues

```bash
# If you have a base64-encoded license but not in g2license_* folder:
# Option 1: Create the expected folder structure
mkdir -p api/g2license_manual
cp your-license.lic_base64 api/g2license_manual/g2.lic_base64

# Option 2: Decode it manually and use Method B
base64 -d < your-license.lic_base64 > api/secrets/senzing/g2.lic
```

### Field Mapping Issues

If entities are not matching correctly:
1. Check `api/config/niem_senzing_mappings.yaml`
2. Verify entity fields in Neo4j match mapping configuration
3. Check logs for mapping warnings: `docker compose logs api | grep -i mapping`
4. Test with known duplicate data to verify mappings are working

### Complete Startup Sequence Verification

Check the complete startup sequence to identify issues:

```bash
# View full API logs
docker compose logs api

# Look for these key messages in order:
# 1. "Searching for Senzing license in /app/licenses/g2license_*"
# 2. "Found license file: /app/licenses/g2license_.../g2.lic_base64"
# 3. "✅ Senzing license decoded successfully to /app/secrets/senzing/g2.lic"
# 4. "Senzing client initialized successfully"

# If you see errors, they will indicate the specific issue
```

### Debug Senzing-Specific Logs

To view only Senzing-related log messages:

```bash
# Filter for Senzing debug messages
docker compose logs api -f | grep SENZING_DEBUG

# Or view all Senzing-related logs
docker compose logs api | grep -i senzing
```

## Text-Based Entity Matching Mode

When Senzing is not available, the system uses text-based entity matching that:
- Matches entities by exact name comparison
- Supports basic fuzzy matching (case-insensitive, punctuation removal)
- Creates ResolvedEntity nodes similar to Senzing output

This allows development and testing without a Senzing license.