# Schema Browser - Technical Architecture

## Document Information
- **Version**: 1.0
- **Date**: January 7, 2025
- **Author**: Engineering Team

---

## 1. System Overview

The Schema Browser is a full-stack graph visualization system for NIEM CMF schemas, consisting of:
- **Backend**: Python FastAPI service that parses CMF and serves graph data
- **Frontend**: React + TypeScript UI with Cytoscape.js for visualization
- **Storage**: MinIO S3-compatible object storage for CMF files

### High-Level Architecture

```
┌─────────────┐
│   Browser   │
│   (User)    │
└──────┬──────┘
       │ HTTP/JSON
       │
┌──────▼──────────────────────────────────────────┐
│           Frontend (React + TypeScript)         │
│  ┌──────────────────────────────────────────┐  │
│  │  Pages                                    │  │
│  │  └─ schema-browser.tsx                   │  │
│  ├──────────────────────────────────────────┤  │
│  │  Components                               │  │
│  │  ├─ SchemaGraph.tsx (Cytoscape.js)       │  │
│  │  ├─ SchemaDetailPanel.tsx                │  │
│  │  └─ SchemaFilters.tsx                     │  │
│  ├──────────────────────────────────────────┤  │
│  │  API Client (api.ts)                      │  │
│  └──────────────────────────────────────────┘  │
└─────────────────┬───────────────────────────────┘
                  │ REST API
                  │ GET /api/schema/{id}/graph
┌─────────────────▼───────────────────────────────┐
│        Backend (Python + FastAPI)               │
│  ┌──────────────────────────────────────────┐  │
│  │  Handlers                                 │  │
│  │  └─ schema.py                            │  │
│  │      └─ get_schema_graph()               │  │
│  ├──────────────────────────────────────────┤  │
│  │  Services                                 │  │
│  │  └─ cmf_parser.py                        │  │
│  │      └─ CMFParser.parse()                │  │
│  ├──────────────────────────────────────────┤  │
│  │  Clients                                  │  │
│  │  └─ s3_client.py                         │  │
│  └──────────────────────────────────────────┘  │
└─────────────────┬───────────────────────────────┘
                  │ S3 Protocol
┌─────────────────▼───────────────────────────────┐
│        Storage (MinIO)                           │
│  niem-schemas/                                   │
│    {schema_id}/                                  │
│      ├─ schema.cmf          (CMF XML)          │
│      ├─ metadata.json       (Schema info)       │
│      └─ source/             (Original XSD)      │
└──────────────────────────────────────────────────┘
```

---

## 2. Data Flow

### Complete Request Flow

```
1. User selects schema
   ↓
2. Frontend calls GET /api/schema/{schema_id}/graph
   ↓
3. Backend handler retrieves CMF from MinIO
   ↓
4. CMF Parser extracts nodes and edges
   ↓
5. Graph JSON returned to frontend
   ↓
6. Cytoscape.js renders graph
   ↓
7. User interacts (expand, filter, search)
   ↓
8. Frontend updates graph (client-side, no server call)
```

### Detailed Data Transformation

```
┌─────────────────────────────────────────────────────────┐
│ Step 1: CMF XML (in MinIO)                             │
├─────────────────────────────────────────────────────────┤
│ <Model>                                                 │
│   <Namespace id="nc">                                   │
│     <Class id="nc.PersonType">                         │
│       <Name>PersonType</Name>                          │
│       <HasProperty ref="nc.PersonName"/>               │
│     </Class>                                            │
│   </Namespace>                                          │
│ </Model>                                                │
└─────────────────────────────────────────────────────────┘
                         │
                         ▼ CMFParser.parse()
┌─────────────────────────────────────────────────────────┐
│ Step 2: Graph JSON (from backend)                      │
├─────────────────────────────────────────────────────────┤
│ {                                                        │
│   "nodes": [                                            │
│     {                                                    │
│       "id": "nc.PersonType",                           │
│       "label": "PersonType",                           │
│       "namespace": "nc",                                │
│       "nodeType": "class",                             │
│       "hasChildren": true                               │
│     }                                                    │
│   ],                                                     │
│   "edges": [                                            │
│     {                                                    │
│       "source": "nc.PersonType",                       │
│       "target": "nc.PersonNameType",                   │
│       "label": "PersonName",                           │
│       "edgeType": "property"                           │
│     }                                                    │
│   ]                                                      │
│ }                                                        │
└─────────────────────────────────────────────────────────┘
                         │
                         ▼ Cytoscape.js format conversion
┌─────────────────────────────────────────────────────────┐
│ Step 3: Cytoscape Elements (frontend)                  │
├─────────────────────────────────────────────────────────┤
│ {                                                        │
│   nodes: [                                              │
│     {                                                    │
│       data: {                                           │
│         id: 'nc.PersonType',                           │
│         label: 'PersonType',                           │
│         color: '#3182ce',  // Blue for CORE            │
│         shape: 'roundrectangle'                        │
│       }                                                  │
│     }                                                    │
│   ],                                                     │
│   edges: [                                              │
│     {                                                    │
│       data: {                                           │
│         source: 'nc.PersonType',                       │
│         target: 'nc.PersonNameType',                   │
│         label: 'PersonName'                            │
│       }                                                  │
│     }                                                    │
│   ]                                                      │
│ }                                                        │
└─────────────────────────────────────────────────────────┘
```

---

## 3. Component Architecture

### Backend Components

#### 3.1 CMF Parser (`cmf_parser.py`)

**Responsibility**: Parse CMF XML into graph structure

**Key Methods**:
```python
class CMFParser:
    def parse(self, cmf_content: str) -> Dict[str, Any]:
        """Main parsing entry point."""

    def _parse_namespaces(self, root: Element) -> List[Dict]:
        """Extract namespace declarations."""

    def _parse_classes(self, root: Element) -> List[Dict]:
        """Extract class definitions as nodes."""

    def _parse_properties_and_edges(self, root: Element) -> Tuple[List, List]:
        """Extract properties and create edges."""

    def _parse_associations(self, root: Element) -> List[Dict]:
        """Extract association types."""

    def _parse_augmentations(self, root: Element) -> List[Dict]:
        """Extract augmentation records."""

    def _calculate_depth(self, nodes: List, edges: List) -> List:
        """Calculate hierarchical depth using BFS."""
```

**Dependencies**:
- `xml.etree.ElementTree` - XML parsing
- `collections.defaultdict` - Graph structures
- `logging` - Error logging

**Input**: CMF XML string
**Output**: Graph JSON dictionary

#### 3.2 Schema Handler (`schema.py`)

**Responsibility**: HTTP request handling and orchestration

**Key Functions**:
```python
def get_schema_graph(s3: Minio, schema_id: str) -> Dict[str, Any]:
    """Retrieve and parse schema graph.

    Steps:
    1. Fetch schema metadata from MinIO
    2. Retrieve CMF file from MinIO
    3. Parse CMF to graph
    4. Return graph JSON
    """
```

**Dependencies**:
- `cmf_parser.CMFParser` - CMF parsing
- `s3_client` - MinIO access
- `HTTPException` - Error responses

**Route**: `GET /api/schema/{schema_id}/graph`

#### 3.3 S3 Client (`s3_client.py`)

**Responsibility**: MinIO object storage access

**Used Methods**:
```python
def get_object(bucket: str, object_path: str) -> bytes:
    """Retrieve object from MinIO."""
```

**MinIO Paths**:
- Schema CMF: `niem-schemas/{schema_id}/schema.cmf`
- Metadata: `niem-schemas/{schema_id}/metadata.json`

### Frontend Components

#### 3.4 Schema Browser Page (`schema-browser.tsx`)

**Responsibility**: Top-level page component, state management

**State**:
```typescript
const [schemas, setSchemas] = useState<Schema[]>([]);
const [selectedSchemaId, setSelectedSchemaId] = useState<string>('');
const [graphData, setGraphData] = useState<GraphData | null>(null);
const [viewMode, setViewMode] = useState<'tree' | 'network'>('tree');
const [filters, setFilters] = useState<Filters>({
  namespaces: new Set(['nc', 'j', 'exch']),
  types: new Set(['class', 'association', 'property']),
  searchQuery: '',
  maxDepth: 10
});
const [selectedNodes, setSelectedNodes] = useState<Set<string>>(new Set());
```

**Key Methods**:
```typescript
const loadSchemas = async () => {
  // Fetch schema list from API
};

const loadGraph = async (schemaId: string) => {
  // Fetch graph data for selected schema
};

const handleFilterChange = (filterType: string, value: any) => {
  // Update filter state and trigger re-render
};

const handleNodeSelect = (nodeId: string) => {
  // Handle node selection, show detail panel
};
```

**Child Components**:
- `SchemaFilters` - Left sidebar
- `SchemaGraph` - Center canvas
- `SchemaDetailPanel` - Right sidebar

#### 3.5 Schema Graph Component (`SchemaGraph.tsx`)

**Responsibility**: Cytoscape.js graph rendering and interaction

**Props**:
```typescript
interface SchemaGraphProps {
  data: GraphData;  // Nodes and edges
  mode: 'tree' | 'network';  // Layout mode
  filters: Filters;  // Active filters
  onNodeClick: (nodeId: string) => void;
  onNodeDoubleClick: (nodeId: string) => void;
  selectedNodes: Set<string>;
}
```

**State**:
```typescript
const [cy, setCy] = useState<Core | null>(null);  // Cytoscape instance
const [layout, setLayout] = useState<'dagre' | 'cose' | 'concentric'>('dagre');
const [expandedNodes, setExpandedNodes] = useState<Set<string>>(new Set());
```

**Key Methods**:
```typescript
const initCytoscape = (elements: ElementsDefinition) => {
  // Initialize Cytoscape instance with nodes/edges
};

const handleExpand = (nodeId: string) => {
  // Add child nodes to graph, run layout
};

const handleCollapse = (nodeId: string) => {
  // Remove child nodes from graph
};

const applyFilters = (filters: Filters) => {
  // Show/hide nodes based on filters
};

const exportPNG = () => {
  // Generate PNG image from current view
};
```

**Cytoscape Configuration**:
```typescript
const cytoscapeConfig = {
  elements: graphElements,
  style: cytoscapeStylesheet,
  layout: { name: 'dagre' },
  minZoom: 0.1,
  maxZoom: 5.0,
  wheelSensitivity: 0.2
};
```

#### 3.6 Schema Detail Panel Component (`SchemaDetailPanel.tsx`)

**Responsibility**: Display selected node details

**Props**:
```typescript
interface SchemaDetailPanelProps {
  node: GraphNode | null;  // Selected node data
  graphData: GraphData;  // Full graph for lookups
  onClose: () => void;
  onNavigate: (nodeId: string) => void;  // Navigate to related node
}
```

**Displayed Information**:
- Qualified name
- Namespace (name, URI, category)
- Node type
- Documentation
- Properties list
- Usage count and list
- Augmentations
- Base type

#### 3.7 Schema Filters Component (`SchemaFilters.tsx`)

**Responsibility**: Filter controls UI

**Props**:
```typescript
interface SchemaFiltersProps {
  filters: Filters;
  namespaces: Namespace[];  // Available namespaces
  onChange: (filters: Filters) => void;
}
```

**Controls**:
- Search input
- Namespace checkboxes (dynamic based on schema)
- Type checkboxes (Classes, Associations, Properties)
- Depth range slider
- Clear filters button

---

## 4. State Management

### State Location Strategy

| State | Location | Reason |
|-------|----------|--------|
| Schema list | Page component | Loaded once, shared across views |
| Selected schema ID | Page component | Drives graph loading |
| Graph data (nodes/edges) | Page component | Source of truth |
| Filters | Page component | Affects multiple components |
| Selected nodes | Page component | Shared between graph and detail panel |
| Cytoscape instance | SchemaGraph component | Internal graph state |
| Expanded nodes | SchemaGraph component | UI state specific to graph |
| Detail panel open | Page component | Controls panel visibility |

### Data Flow Pattern

```
Page Component (State Owner)
    │
    ├─> SchemaFilters
    │   │
    │   └─> onChange() → Updates page state
    │
    ├─> SchemaGraph
    │   │
    │   ├─> Receives: data, filters, selectedNodes
    │   └─> Emits: onNodeClick, onNodeDoubleClick
    │
    └─> SchemaDetailPanel
        │
        ├─> Receives: selectedNode data
        └─> Emits: onNavigate, onClose
```

---

## 5. Performance Optimizations

### 5.1 Backend Optimizations

**CMF Parsing**:
- Single-pass parsing where possible
- Use dictionaries for O(1) lookups
- Lazy evaluation of complex properties
- **Target**: Parse 2000-type schema in < 2 seconds

**API Response**:
- Return minimal data (no redundant fields)
- Use gzip compression
- **Target response size**: < 500KB for 1000-node graph

### 5.2 Frontend Optimizations

**Initial Render**:
- Load only root nodes initially (depth = 0)
- Expand on demand via double-click
- **Target**: First paint < 1 second

**Graph Rendering**:
- Use Cytoscape.js viewport rendering (only visible nodes)
- Limit concurrent animations
- Debounce filter updates (300ms)
- **Target**: 60 FPS during interactions

**Memory Management**:
- Remove collapsed nodes from DOM
- Limit expanded depth (default max = 3)
- Clear unused Cytoscape instances

**React Optimizations**:
```typescript
// Memoize expensive computations
const filteredNodes = useMemo(() => {
  return filterNodes(graphData.nodes, filters);
}, [graphData.nodes, filters]);

// Prevent unnecessary re-renders
const SchemaGraph = React.memo(SchemaGraphComponent);
```

### 5.3 Caching Strategy

**Backend**:
- No server-side caching (CMF may update)
- Rely on browser HTTP cache (Cache-Control headers)

**Frontend**:
- Cache graph data in component state
- Only re-fetch on schema ID change
- Cache Cytoscape instance between layout changes

---

## 6. Error Handling

### 6.1 Backend Error Scenarios

| Error | HTTP Code | Response | User Experience |
|-------|-----------|----------|-----------------|
| Schema not found | 404 | `{"detail": "Schema not found"}` | "Schema does not exist" message |
| CMF parse error | 500 | `{"detail": "Failed to parse CMF: ..."}` | "Unable to load schema" message |
| MinIO unavailable | 503 | `{"detail": "Storage unavailable"}` | "Service temporarily unavailable" |
| Invalid CMF format | 400 | `{"detail": "Invalid CMF structure"}` | "Schema file is corrupted" |

### 6.2 Frontend Error Handling

**API Errors**:
```typescript
try {
  const graph = await apiClient.getSchemaGraph(schemaId);
  setGraphData(graph);
} catch (err: any) {
  if (err.response?.status === 404) {
    setError('Schema not found. It may have been deleted.');
  } else if (err.response?.status === 500) {
    setError('Unable to load schema. Please try again later.');
  } else {
    setError('An unexpected error occurred.');
  }
  console.error('Graph load error:', err);
}
```

**Rendering Errors**:
```typescript
// Error boundary for Cytoscape component
class GraphErrorBoundary extends React.Component {
  componentDidCatch(error, errorInfo) {
    console.error('Graph rendering error:', error, errorInfo);
    this.setState({ hasError: true });
  }

  render() {
    if (this.state.hasError) {
      return <div>Unable to render graph. Please refresh the page.</div>;
    }
    return this.props.children;
  }
}
```

---

## 7. Security Considerations

### 7.1 Backend Security

**Authentication**:
- API requires bearer token (existing auth mechanism)
- Schema access controlled by token permissions

**Input Validation**:
```python
def get_schema_graph(s3: Minio, schema_id: str):
    # Validate schema_id format (prevent path traversal)
    if not re.match(r'^[a-f0-9]{64}$', schema_id):
        raise HTTPException(status_code=400, detail="Invalid schema ID")
```

**CMF Parsing**:
- Use safe XML parser (ElementTree)
- Limit CMF file size (max 50MB)
- Timeout parsing after 30 seconds

### 7.2 Frontend Security

**XSS Prevention**:
- React auto-escapes text content
- Sanitize documentation text before rendering
- No `dangerouslySetInnerHTML` usage

**CSRF Protection**:
- API uses bearer tokens (not cookies)
- No CSRF vulnerability

---

## 8. Testing Strategy

### 8.1 Backend Tests

**Unit Tests** (`test_cmf_parser.py`):
```python
def test_parse_simple_schema():
    parser = CMFParser()
    result = parser.parse(SIMPLE_CMF_XML)
    assert len(result['nodes']) == 5
    assert len(result['edges']) == 3

def test_parse_associations():
    # Test association edge creation

def test_parse_augmentations():
    # Test augmentation edge creation

def test_error_handling_malformed_xml():
    # Test graceful failure
```

**Integration Tests**:
```python
def test_api_endpoint_success():
    response = client.get('/api/schema/abc123.../graph')
    assert response.status_code == 200
    assert 'nodes' in response.json()

def test_api_endpoint_not_found():
    response = client.get('/api/schema/invalid/graph')
    assert response.status_code == 404
```

### 8.2 Frontend Tests

**Component Tests** (Jest + React Testing Library):
```typescript
test('SchemaGraph renders nodes', () => {
  render(<SchemaGraph data={mockGraphData} mode="tree" />);
  expect(screen.getByText('PersonType')).toBeInTheDocument();
});

test('Filter updates graph', () => {
  const { rerender } = render(<SchemaGraph data={mockGraphData} filters={filters1} />);
  rerender(<SchemaGraph data={mockGraphData} filters={filters2} />);
  // Assert nodes filtered
});
```

**E2E Tests** (Cypress):
```typescript
it('User can expand and collapse nodes', () => {
  cy.visit('/schema-browser');
  cy.get('[data-testid="schema-select"]').select('CrashDriver');
  cy.get('[data-node-id="nc.PersonType"]').dblclick();
  cy.get('[data-node-id="nc.PersonName"]').should('be.visible');
  cy.get('[data-node-id="nc.PersonType"]').dblclick();
  cy.get('[data-node-id="nc.PersonName"]').should('not.exist');
});
```

---

## 9. Deployment Architecture

```
┌─────────────────────────────────────────────────┐
│  Docker Compose / Kubernetes                    │
├─────────────────────────────────────────────────┤
│                                                 │
│  ┌─────────────┐  ┌─────────────┐  ┌────────┐ │
│  │  UI         │  │  API        │  │ MinIO  │ │
│  │  (Node20)   │  │  (Python)   │  │ (S3)   │ │
│  │  Port 3000  │  │  Port 8000  │  │ 9000   │ │
│  └─────────────┘  └─────────────┘  └────────┘ │
│         │               │               │      │
└─────────┼───────────────┼───────────────┼──────┘
          │               │               │
          └───────────────┴───────────────┘
                      Network
```

**Container Details**:
- **UI**: Next.js production build, served by Node.js
- **API**: FastAPI with uvicorn, Python 3.12
- **MinIO**: S3-compatible storage

**Build Process**:
```bash
# Build API image
docker build -t niem-api -f api/Dockerfile .

# Build UI image
docker build -t niem-ui -f ui/Dockerfile .

# Deploy with compose
docker compose up -d --build
```

---

## 10. Future Enhancements

### 10.1 Planned Features (v2.0)

**Schema Comparison**:
- Load two schemas side-by-side
- Diff visualization (added/removed/changed types)
- Migration path highlighting

**Collaborative Features**:
- Annotations/comments on nodes
- Share views with team members
- Export annotated diagrams

**Advanced Analytics**:
- Centrality analysis (find most important types)
- Clustering detection
- Dependency analysis

### 10.2 Technical Debt

**Known Limitations**:
- No server-side pagination (assumes schemas < 5000 types)
- No real-time updates (requires manual refresh)
- Limited mobile support (desktop-only UI)

**Refactoring Opportunities**:
- Extract Cytoscape config to separate file
- Create reusable graph utilities library
- Improve TypeScript type coverage (currently ~80%)

---

## 11. Monitoring & Observability

### 11.1 Metrics to Track

**Backend**:
- CMF parse time (p50, p95, p99)
- API response time
- Error rate by endpoint
- CMF file size distribution

**Frontend**:
- Page load time
- Time to interactive
- Graph render time
- Error rate (JavaScript exceptions)
- User actions (expand, filter, export)

### 11.2 Logging

**Backend Logging**:
```python
logger.info(f"Parsing CMF for schema {schema_id}")
logger.info(f"Parsed {len(nodes)} nodes, {len(edges)} edges in {duration}ms")
logger.error(f"CMF parse failed: {error}", exc_info=True)
```

**Frontend Logging**:
```typescript
console.log('[SchemaGraph] Rendering', nodes.length, 'nodes');
console.error('[SchemaGraph] Cytoscape init failed:', error);
```

---

## 12. Technology Stack

| Layer | Technology | Version | Purpose |
|-------|------------|---------|---------|
| **Backend** | Python | 3.12 | API implementation |
| | FastAPI | 0.100+ | Web framework |
| | Pydantic | 2.0+ | Data validation |
| **Storage** | MinIO | Latest | S3-compatible storage |
| **Frontend** | React | 18+ | UI framework |
| | TypeScript | 5+ | Type safety |
| | Next.js | 14+ | React framework |
| | Cytoscape.js | 3.28+ | Graph visualization |
| | Tailwind CSS | 3+ | Styling |
| **Deployment** | Docker | 24+ | Containerization |
| | Docker Compose | 2+ | Orchestration |

---

## Appendix: Key Algorithms

### A. Depth Calculation (BFS)

```python
def calculate_depth(nodes: List[Dict], edges: List[Dict]) -> List[Dict]:
    """Breadth-first search to calculate node depth."""
    # Build adjacency list
    graph = defaultdict(list)
    for edge in edges:
        if edge['edgeType'] in ['property', 'extends']:
            graph[edge['source']].append(edge['target'])

    # Find roots (no incoming edges)
    incoming = {e['target'] for e in edges if e['edgeType'] in ['property', 'extends']}
    roots = [n['id'] for n in nodes if n['id'] not in incoming]

    # BFS
    depths = {}
    queue = deque([(root, 0) for root in roots])
    while queue:
        node_id, depth = queue.popleft()
        if node_id not in depths:
            depths[node_id] = depth
            for child in graph[node_id]:
                queue.append((child, depth + 1))

    # Update nodes
    for node in nodes:
        node['depth'] = depths.get(node['id'], 0)

    return nodes
```

### B. Path Finding (Dijkstra)

```typescript
function findShortestPath(
  graph: GraphData,
  sourceId: string,
  targetId: string
): string[] | null {
  // Build adjacency list
  const adj = new Map<string, string[]>();
  graph.edges.forEach(edge => {
    if (!adj.has(edge.source)) adj.set(edge.source, []);
    adj.get(edge.source)!.push(edge.target);
  });

  // BFS for shortest path
  const queue: [string, string[]][] = [[sourceId, [sourceId]]];
  const visited = new Set<string>();

  while (queue.length > 0) {
    const [node, path] = queue.shift()!;
    if (node === targetId) return path;

    if (!visited.has(node)) {
      visited.add(node);
      const neighbors = adj.get(node) || [];
      neighbors.forEach(neighbor => {
        queue.push([neighbor, [...path, neighbor]]);
      });
    }
  }

  return null;  // No path found
}
```

---

**End of Architecture Documentation**
