# Schema Browser - API Documentation

## Overview

This document describes the REST API endpoint used by the Schema Browser for retrieving graph data from NIEM CMF schemas.

**Base URL**: `http://localhost:8000/api` (development)

**Authentication**: Bearer token required in `Authorization` header

---

## Endpoint: Get Schema Graph

Retrieves the parsed graph structure for a given schema ID.

### Request

**Method**: `GET`

**Path**: `/schema/{schema_id}/graph`

**Headers**:
```
Authorization: Bearer {token}
Content-Type: application/json
```

**Path Parameters**:
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `schema_id` | string | Yes | Unique schema identifier (SHA-256 hash) |

**Query Parameters**: None

### Response

**Success Response (200 OK)**:

```json
{
  "nodes": [
    {
      "id": "nc.PersonType",
      "label": "PersonType",
      "namespace": "nc",
      "namespaceURI": "https://docs.oasis-open.org/niemopen/ns/model/niem-core/6.0/",
      "namespaceCategory": "CORE",
      "nodeType": "class",
      "documentation": "A data type for a human being.",
      "hasChildren": true,
      "depth": 0,
      "metadata": {
        "abstract": false,
        "baseType": null,
        "augmentable": true,
        "file": "niem/niem-core.xsd",
        "propertyCount": 12,
        "usageCount": 47
      }
    },
    {
      "id": "nc.PersonName",
      "label": "PersonName",
      "namespace": "nc",
      "namespaceURI": "https://docs.oasis-open.org/niemopen/ns/model/niem-core/6.0/",
      "namespaceCategory": "CORE",
      "nodeType": "property",
      "documentation": "A name of a person.",
      "hasChildren": true,
      "depth": 1,
      "metadata": {
        "typeRef": "nc.PersonNameType",
        "cardinality": "[1..1]",
        "file": "niem/niem-core.xsd"
      }
    }
  ],
  "edges": [
    {
      "id": "edge_nc.PersonType_nc.PersonName",
      "source": "nc.PersonType",
      "target": "nc.PersonNameType",
      "label": "PersonName",
      "edgeType": "property",
      "cardinality": "[1..1]",
      "documentation": "A name of a person."
    },
    {
      "id": "assoc_j.CrashDriver",
      "source": "j.CrashType",
      "target": "nc.PersonType",
      "label": "CrashDriver",
      "edgeType": "association",
      "cardinality": "[1..unbounded]",
      "documentation": "A relationship between a crash and a driver."
    }
  ],
  "namespaces": [
    {
      "id": "nc",
      "prefix": "nc",
      "uri": "https://docs.oasis-open.org/niemopen/ns/model/niem-core/6.0/",
      "category": "CORE",
      "label": "NIEM Core",
      "documentation": "NIEM Core namespace containing fundamental types.",
      "classCount": 423,
      "propertyCount": 1243
    },
    {
      "id": "j",
      "prefix": "j",
      "uri": "https://docs.oasis-open.org/niemopen/ns/model/domains/justice/6.0/",
      "category": "DOMAIN",
      "label": "Justice Domain",
      "documentation": "Justice domain types for law enforcement and legal proceedings.",
      "classCount": 156,
      "propertyCount": 487
    },
    {
      "id": "exch",
      "prefix": "exch",
      "uri": "http://example.com/CrashDriver/1.2/",
      "category": "EXTENSION",
      "label": "CrashDriver Extension",
      "documentation": "Custom extension for CrashDriver IEPD.",
      "classCount": 12,
      "propertyCount": 34
    }
  ],
  "metadata": {
    "schemaId": "abc123def456...",
    "totalNodes": 1666,
    "totalEdges": 3421,
    "namespaceCount": 3,
    "parseDate": "2025-01-07T12:34:56Z",
    "cmfVersion": "1.0"
  }
}
```

**Error Responses**:

**404 Not Found** - Schema does not exist:
```json
{
  "detail": "Schema not found"
}
```

**500 Internal Server Error** - CMF parse failure:
```json
{
  "detail": "Failed to parse CMF: Invalid XML structure at line 42"
}
```

**401 Unauthorized** - Missing or invalid token:
```json
{
  "detail": "Not authenticated"
}
```

**503 Service Unavailable** - MinIO unavailable:
```json
{
  "detail": "Storage service temporarily unavailable"
}
```

---

## Data Models

### Node Object

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | Yes | Unique node identifier (format: `{prefix}.{localName}`) |
| `label` | string | Yes | Display name (localName only, without prefix) |
| `namespace` | string | Yes | Namespace prefix (e.g., "nc", "j", "exch") |
| `namespaceURI` | string | Yes | Full namespace URI |
| `namespaceCategory` | string | Yes | Category from CMF (e.g., "CORE", "DOMAIN", "EXTENSION", "OTHERNIEM", "EXTERNAL") - values passed through from CMF |
| `nodeType` | string | Yes | Type derived from CMF structure (e.g., "class", "property", "association", "augmentation") - frontend should handle any value |
| `documentation` | string | No | Definition text from CMF (may be null) |
| `hasChildren` | boolean | Yes | True if node has outgoing edges |
| `depth` | integer | Yes | Hierarchical depth (0 = root, increases with nesting) |
| `metadata` | object | Yes | Type-specific metadata (see below) |

**Metadata for `nodeType: "class"`**:
```json
{
  "abstract": false,          // Is this an abstract type?
  "baseType": "nc.ObjectType", // Base type if extends (null if none)
  "augmentable": true,         // Can this type be augmented?
  "file": "niem/niem-core.xsd", // Source file location
  "propertyCount": 12,         // Number of properties
  "usageCount": 47             // How many other types reference this
}
```

**Metadata for `nodeType: "property"`**:
```json
{
  "typeRef": "nc.TextType",   // Type this property references
  "cardinality": "[1..1]",    // Occurrence constraint
  "file": "niem/niem-core.xsd"
}
```

**Metadata for `nodeType: "association"`**:
```json
{
  "sourceType": "j.CrashType",   // Source class
  "targetType": "nc.PersonType", // Target class
  "file": "niem/domains/justice.xsd"
}
```

### Edge Object

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | Yes | Unique edge identifier |
| `source` | string | Yes | Source node ID (must match a node.id) |
| `target` | string | Yes | Target node ID (must match a node.id) |
| `label` | string | Yes | Property or relationship name |
| `edgeType` | string | Yes | Relationship type from CMF (e.g., "property", "association", "augmentation", "extends") - frontend should handle dynamically |
| `cardinality` | string | No | Occurrence constraint (e.g., `[0..unbounded]`) |
| `documentation` | string | No | Relationship definition |

**Common Edge Type Examples** (not exhaustive):
- `property`: Class has a property of this type
- `association`: Explicit association relationship
- `augmentation`: Type is augmented with additional property
- `extends`: Type extends/inherits from base type

**Note**: The actual edge types present depend on the CMF structure. The frontend should handle any edge type value and provide reasonable defaults for visualization.

### Namespace Object

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | Yes | Namespace identifier (same as prefix) |
| `prefix` | string | Yes | Namespace prefix used in qualified names |
| `uri` | string | Yes | Full namespace URI |
| `category` | string | Yes | Category from CMF `NamespaceCategoryCode` (passed through as-is) |
| `label` | string | Yes | Human-readable name |
| `documentation` | string | No | Namespace description |
| `classCount` | integer | Yes | Number of classes in this namespace |
| `propertyCount` | integer | Yes | Number of properties in this namespace |

**Common Namespace Categories** (examples from NIEM, not exhaustive):
- `CORE`: NIEM Core namespace (typically nc)
- `DOMAIN`: NIEM domain namespace (e.g., j, hs, em)
- `EXTENSION`: Custom IEPD extension namespace
- `OTHERNIEM`: Other NIEM namespace (e.g., adapters, codes)
- `EXTERNAL`: External standard (e.g., GML, ISO)

**Note**: Categories come directly from CMF `NamespaceCategoryCode`. The frontend should handle any category value and provide reasonable defaults for unknown categories (e.g., use a neutral color/icon).

### Metadata Object

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `schemaId` | string | Yes | Schema identifier (same as path parameter) |
| `totalNodes` | integer | Yes | Total number of nodes in graph |
| `totalEdges` | integer | Yes | Total number of edges in graph |
| `namespaceCount` | integer | Yes | Number of namespaces |
| `parseDate` | string (ISO 8601) | Yes | When CMF was parsed |
| `cmfVersion` | string | Yes | CMF specification version (e.g., "1.0") |

---

## Example Requests

### cURL Example

```bash
curl -X GET \
  'http://localhost:8000/api/schema/abc123def456.../graph' \
  -H 'Authorization: Bearer devtoken' \
  -H 'Content-Type: application/json'
```

### JavaScript (Fetch API) Example

```javascript
const schemaId = 'abc123def456...';

const response = await fetch(
  `http://localhost:8000/api/schema/${schemaId}/graph`,
  {
    method: 'GET',
    headers: {
      'Authorization': 'Bearer devtoken',
      'Content-Type': 'application/json'
    }
  }
);

if (!response.ok) {
  throw new Error(`HTTP ${response.status}: ${response.statusText}`);
}

const graphData = await response.json();
console.log(`Loaded ${graphData.nodes.length} nodes`);
```

### Python (requests) Example

```python
import requests

schema_id = 'abc123def456...'
url = f'http://localhost:8000/api/schema/{schema_id}/graph'
headers = {
    'Authorization': 'Bearer devtoken',
    'Content-Type': 'application/json'
}

response = requests.get(url, headers=headers)
response.raise_for_status()

graph_data = response.json()
print(f"Loaded {len(graph_data['nodes'])} nodes")
```

### TypeScript (with type safety) Example

```typescript
interface GraphData {
  nodes: GraphNode[];
  edges: GraphEdge[];
  namespaces: Namespace[];
  metadata: GraphMetadata;
}

async function getSchemaGraph(schemaId: string): Promise<GraphData> {
  const response = await fetch(
    `http://localhost:8000/api/schema/${schemaId}/graph`,
    {
      headers: {
        'Authorization': 'Bearer devtoken',
        'Content-Type': 'application/json'
      }
    }
  );

  if (!response.ok) {
    throw new Error(`Failed to load schema: ${response.statusText}`);
  }

  return await response.json();
}

// Usage
const graph = await getSchemaGraph('abc123...');
console.log(`Namespaces: ${graph.namespaces.map(ns => ns.prefix).join(', ')}`);
```

---

## Performance Characteristics

### Response Time Targets

| Schema Size | Expected Response Time | Notes |
|-------------|------------------------|-------|
| Small (< 100 types) | < 200ms | Typical IEPD extension |
| Medium (100-500 types) | < 500ms | Single NIEM domain |
| Large (500-2000 types) | < 2s | Full NIEM Core |
| Very Large (2000-5000 types) | < 5s | Multiple NIEM domains |

### Response Size

| Schema Size | Typical Response Size (gzipped) |
|-------------|--------------------------------|
| Small (< 100 types) | ~20-50 KB |
| Medium (100-500 types) | ~100-200 KB |
| Large (500-2000 types) | ~300-500 KB |
| Very Large (2000-5000 types) | ~800KB - 1.5MB |

### Caching

**Server-Side**: No caching (CMF may be updated)

**Client-Side**: Browsers should cache based on `Cache-Control` headers
```
Cache-Control: private, max-age=300
```

---

## Error Handling Best Practices

### Handling 404 Errors

```typescript
try {
  const graph = await getSchemaGraph(schemaId);
} catch (err: any) {
  if (err.response?.status === 404) {
    // Schema doesn't exist - show friendly message
    showError('Schema not found. It may have been deleted.');
    // Redirect to schema list
    navigate('/schemas');
  }
}
```

### Handling 500 Errors

```typescript
try {
  const graph = await getSchemaGraph(schemaId);
} catch (err: any) {
  if (err.response?.status === 500) {
    // CMF parse error - show error with retry option
    showError('Unable to load schema. The schema file may be corrupted.');
    showRetryButton();
  }
}
```

### Handling Network Errors

```typescript
try {
  const graph = await getSchemaGraph(schemaId);
} catch (err: any) {
  if (!err.response) {
    // Network error (no response received)
    showError('Network error. Please check your connection and try again.');
  }
}
```

### Retry Logic

```typescript
async function getSchemaGraphWithRetry(
  schemaId: string,
  maxRetries: number = 3
): Promise<GraphData> {
  let lastError: Error;

  for (let attempt = 1; attempt <= maxRetries; attempt++) {
    try {
      return await getSchemaGraph(schemaId);
    } catch (err: any) {
      lastError = err;

      // Don't retry 4xx errors (client errors)
      if (err.response?.status >= 400 && err.response?.status < 500) {
        throw err;
      }

      // Wait before retrying (exponential backoff)
      if (attempt < maxRetries) {
        await new Promise(resolve => setTimeout(resolve, 1000 * attempt));
      }
    }
  }

  throw lastError!;
}
```

---

## Rate Limiting

**Current Implementation**: None

**Future**: May implement rate limiting (e.g., 100 requests/minute per user)

**Headers** (when implemented):
```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1704643200
```

---

## API Versioning

**Current Version**: v1 (implicit)

**URL Structure**: `/api/schema/{id}/graph`

**Future Versioning**: Will use URL versioning when breaking changes are introduced
- v2 would be: `/api/v2/schema/{id}/graph`
- v1 will remain supported for 6 months after v2 release

---

## Change Log

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2025-01-07 | Initial API release - CMF graph endpoint |

---

## Related Endpoints

### Get All Schemas

**Endpoint**: `GET /api/schema`

**Description**: Returns list of all uploaded schemas

**Response**:
```json
[
  {
    "schema_id": "abc123...",
    "primary_filename": "CrashDriver.xsd",
    "all_filenames": ["CrashDriver.xsd", "niem/niem-core.xsd"],
    "uploaded_at": "2025-01-07T12:00:00Z",
    "active": true
  }
]
```

### Get Schema Metadata

**Endpoint**: `GET /api/schema/{schema_id}/metadata`

**Description**: Returns schema metadata without parsing full graph

**Note**: Use this for lightweight metadata queries. Use `/graph` only when visualization is needed.

---

## Support

For API issues or questions:
- Check application logs: `docker logs niem-info-exch-e2e-api-1`
- File bug report with example request/response
- Contact: System Administrator

---

**End of API Documentation**
