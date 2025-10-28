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

To enable Senzing SDK mode:

1. **Option A: Place license file directly**
   ```bash
   mkdir -p api/secrets/senzing
   cp /path/to/g2.lic api/secrets/senzing/g2.lic
   ```

2. **Option B: Use base64 encoded license**
   ```bash
   # In .env file
   SENZING_LICENSE_BASE64=<base64-encoded-content>
   ```

The system will automatically decode base64 licenses on startup.

## Troubleshooting

### Senzing Not Available

If Senzing is not available, check:
1. License file exists at `SENZING_LICENSE_PATH`
2. Senzing Python SDK is installed: `pip install senzing`
3. Check logs for initialization errors

### Database Connection Issues

For SQLite:
- Ensure data directory exists and is writable
- Check file permissions on database file

For PostgreSQL/MySQL:
- Verify connection string format
- Test connection with database client
- Ensure database exists and user has permissions

### Field Mapping Issues

If entities are not matching correctly:
1. Check `api/config/niem_senzing_mappings.yaml`
2. Verify entity fields in Neo4j match mapping configuration
3. Check logs for mapping warnings

## Text-Based Entity Matching Mode

When Senzing is not available, the system uses text-based entity matching that:
- Matches entities by exact name comparison
- Supports basic fuzzy matching (case-insensitive, punctuation removal)
- Creates ResolvedEntity nodes similar to Senzing output

This allows development and testing without a Senzing license.