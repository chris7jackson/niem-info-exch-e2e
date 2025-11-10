# System Workflows

## Table of Contents

- [Overview](#overview)
- [Workflow 1: Schema Upload](#workflow-1-schema-upload)
- [Workflow 2: XML/JSON Ingestion](#workflow-2-xmljson-ingestion)
- [Workflow 3: Entity Resolution](#workflow-3-entity-resolution)
- [Workflow 4: Schema Designer](#workflow-4-schema-designer)
- [Error Handling Flows](#error-handling-flows)

## Overview

This document provides **sequence diagrams** for the four critical workflows in the NIEM Information Exchange system. These diagrams show the end-to-end flow of data and control through the system components.

### Workflow Summary

| Workflow | Purpose | Key Components | Duration |
|----------|---------|----------------|----------|
| **Schema Upload** | Validate and store NIEM XSD schemas | UI → API → CMFTool → MinIO | 5-30 seconds |
| **Data Ingestion** | Convert XML/JSON to Neo4j graph | UI → API → Converter → Neo4j | 1-60 seconds per file |
| **Entity Resolution** | Find and link duplicate entities | UI → API → Senzing → Neo4j | 10-300 seconds |
| **Schema Designer** | Customize graph structure | UI → API → Element Tree → Mapping | 2-10 seconds |

---

## Workflow 1: Schema Upload

### Purpose

Upload NIEM XSD schema files, validate them using CMFTool and NDR rules, generate Common Model Format (CMF), create default mapping.yaml, and store all artifacts.

### Sequence Diagram

```mermaid
sequenceDiagram
    actor User
    participant UI as Web UI<br/>(Next.js)
    participant API as API Service<br/>(FastAPI)
    participant CMF as CMFTool<br/>(Subprocess)
    participant MinIO as MinIO<br/>(Object Storage)

    User->>UI: 1. Select XSD files<br/>(crashdriver.xsd, etc.)
    User->>UI: 2. Click "Upload Schema"

    UI->>API: POST /api/schema/xsd<br/>FormData: files[], skip_niem_ndr
    activate API

    Note over API: handler: handle_schema_upload()

    API->>MinIO: 3. Create bucket<br/>create_bucket('niem-schemas')
    MinIO-->>API: Bucket created

    loop For each XSD file
        API->>API: 4. Generate schema_id<br/>(timestamp + hash)

        API->>MinIO: 5. Upload XSD<br/>put_object(schema_id/crashdriver.xsd)
        MinIO-->>API: File stored

        alt NDR Validation Enabled
            API->>CMF: 6. Validate NDR rules<br/>cmftool validate-ndr(xsd)
            CMF-->>API: Validation result
            alt Validation failed
                API-->>UI: Error: NDR validation failed
                UI-->>User: Show validation errors
            end
        end

        API->>CMF: 7. Generate CMF<br/>cmftool xsd-to-cmf(xsd)
        CMF-->>API: CMF file content

        API->>MinIO: 8. Upload CMF<br/>put_object(schema_id/schema.cmf)
        MinIO-->>API: CMF stored

        API->>API: 9. Generate mapping.yaml<br/>create_default_mapping(cmf)

        API->>MinIO: 10. Upload mapping<br/>put_object(schema_id/mapping.yaml)
        MinIO-->>API: Mapping stored

        API->>MinIO: 11. Store metadata<br/>put_object(schema_id/metadata.json)
        MinIO-->>API: Metadata stored
    end

    API-->>UI: 12. Success response<br/>{schema_id, files_processed}
    deactivate API

    UI-->>User: 13. Show success<br/>"Schema uploaded successfully"
```

### Key Steps Explained

**Step 4**: Schema ID generation uses timestamp + file hash for uniqueness
```python
schema_id = f"{timestamp}_{file_hash[:8]}"
```

**Step 6**: NDR validation checks NIEM naming and design rules (optional, can be skipped for extensions)

**Step 7**: CMF (Common Model Format) generation converts XSD to intermediate format
- Easier to parse than raw XSD
- Normalizes schema representation

**Step 9**: Default mapping.yaml generation
- Extracts all complex types from CMF
- Marks all as selected by default
- Creates flattened property paths
- Identifies associations

**Step 11**: Metadata includes schema info, upload timestamp, file list

### Error Scenarios

```mermaid
sequenceDiagram
    actor User
    participant UI
    participant API
    participant CMF

    User->>UI: Upload invalid XSD

    UI->>API: POST /api/schema/xsd
    API->>CMF: Validate XSD

    alt Invalid XML Format
        CMF-->>API: Parse error
        API-->>UI: 400 Bad Request<br/>"Invalid XML format"
        UI-->>User: Show error
    else Invalid NIEM NDR
        CMF-->>API: NDR violations
        API-->>UI: 400 Bad Request<br/>"NDR validation failed"
        UI-->>User: Show violations
    else CMFTool Not Available
        API-->>UI: 503 Service Unavailable<br/>"CMFTool not configured"
        UI-->>User: Show error
    end
```

---

## Workflow 2: XML/JSON Ingestion

### Purpose

Validate XML/JSON files against schema, convert to Cypher statements using dual-mode converter, execute in Neo4j to create graph, and store source files.

### Sequence Diagram

```mermaid
sequenceDiagram
    actor User
    participant UI as Web UI
    participant API as API Service
    participant MinIO as MinIO Storage
    participant Conv as Converter<br/>(XML/JSON to Graph)
    participant Neo4j as Neo4j Database

    User->>UI: 1. Select files<br/>(crash01.xml, etc.)
    User->>UI: 2. Click "Ingest"

    UI->>API: POST /api/ingest/xml<br/>FormData: files[]
    activate API

    Note over API: handler: handle_xml_ingest()

    API->>MinIO: 3. Get active schema<br/>get_object(schema_id/mapping.yaml)
    MinIO-->>API: mapping.yaml content

    API->>MinIO: 4. Get CMF<br/>get_object(schema_id/schema.cmf)
    MinIO-->>API: schema.cmf content

    API->>API: 5. Check mode<br/>selections.json exists?

    alt Mapping Mode (selections exist)
        API->>MinIO: Get selections.json
        MinIO-->>API: Custom selections
        Note over API: Create nodes ONLY<br/>for selected elements
    else Dynamic Mode (no selections)
        Note over API: Create nodes for ALL<br/>complex elements
    end

    loop For each XML/JSON file
        API->>API: 6. Parse file<br/>ET.parse(xml) or json.loads()

        alt XML Validation
            API->>API: 7. Validate against XSD<br/>(using lxml)
            alt Validation failed
                API-->>UI: Error: Invalid XML
            end
        end

        API->>Conv: 8. Convert to Cypher<br/>XMLToGraphConverter(mapping)
        activate Conv

        Conv->>Conv: 9. Generate file hash<br/>(for ID prefixing)

        loop For each element
            Conv->>Conv: 10. Determine if node<br/>(complex element check)

            alt Create Node
                Conv->>Conv: 11. Extract properties<br/>(flatten nested values)
                Conv->>Conv: 12. Generate Cypher<br/>CREATE (n:label {props})
            else Flatten Property
                Conv->>Conv: 13. Add to parent props<br/>(nc_PersonName_nc_PersonGivenName)
            end

            Conv->>Conv: 14. Create relationships<br/>(HAS_*, references, REPRESENTS)
        end

        Conv-->>API: 15. Return Cypher statements
        deactivate Conv

        API->>Neo4j: 16. Execute Cypher<br/>(batch execution)
        activate Neo4j
        Neo4j-->>API: Nodes/edges created counts
        deactivate Neo4j

        API->>MinIO: 17. Store source file<br/>put_object(uploads/file.xml)
        MinIO-->>API: File stored

        API->>API: 18. Track upload<br/>(upload_id, schema_id)
    end

    API-->>UI: 19. Success response<br/>{nodes_created, relationships_created}
    deactivate API

    UI-->>User: 20. Show results<br/>"Ingested 3 files, 150 nodes, 200 edges"
```

### Key Steps Explained

**Step 5**: Mode detection determines graph structure
- **Mapping Mode**: Only create nodes listed in selections.json
- **Dynamic Mode**: Create nodes for all complex elements (including extensions)

**Step 9**: File hash prefixing prevents ID collisions
```python
file_hash = hashlib.sha256(file_content).hexdigest()[:12]
prefixed_id = f"{file_hash}_{original_id}"
```

**Step 10**: Complex element detection (Dynamic Mode)
```python
is_complex_element = (
    element.has_attribute('structures:id') or
    element.has_attribute('structures:uri') or
    len(element.child_elements) > 0 or
    len(element.attributes) > 1  # More than just xsi:type
)
```

**Step 12**: Property flattening example
```xml
<nc:PersonName>
  <nc:PersonGivenName>John</nc:PersonGivenName>
</nc:PersonName>
```
Becomes: `nc_PersonName_nc_PersonGivenName: 'John'`

**Step 14**: Relationship creation
- HAS_* for containment
- Named references from mapping.yaml
- REPRESENTS for structures:uri links

**Step 16**: Batch Cypher execution (performance optimization)
```python
# Execute in batches of 1000 statements
for batch in chunks(cypher_statements, 1000):
    neo4j.execute_batch(batch)
```

### Dual-Mode Converter Behavior

```mermaid
graph TD
    A[Start Ingestion] --> B{selections.json<br/>exists?}

    B -->|Yes| C[Mapping Mode]
    B -->|No| D[Dynamic Mode]

    C --> E[Load selections.json]
    E --> F[Create nodes ONLY<br/>for selected elements]
    F --> G[Flatten unselected<br/>complex types]

    D --> H[Analyze all elements]
    H --> I[Create nodes for ALL<br/>complex elements]
    I --> J[Include extension<br/>namespaces]

    G --> K[Generate Cypher]
    J --> K
    K --> L[Execute in Neo4j]
```

---

## Workflow 3: Entity Resolution

### Purpose

Extract entities from Neo4j graph, detect duplicates using Senzing SDK or text-based matching, create ResolvedEntity cluster nodes, and link duplicates with RESOLVED_TO relationships.

### Sequence Diagram

```mermaid
sequenceDiagram
    actor User
    participant UI as Web UI
    participant API as API Service
    participant Neo4j as Neo4j Database
    participant Senzing as Senzing SDK<br/>(Optional)

    User->>UI: 1. Open Entity Resolution panel
    UI->>API: GET /api/entity-resolution/node-types
    activate API

    API->>Neo4j: 2. Query available node types<br/>MATCH (n) RETURN DISTINCT n.qname
    Neo4j-->>API: List of node types

    API->>API: 3. Count entities per type<br/>categorize by domain

    API-->>UI: 4. Node types with counts<br/>[{qname, count, category}]
    deactivate API

    UI-->>User: 5. Show selectable types<br/>(nc:Person: 50, j:CrashDriver: 25, etc.)

    User->>UI: 6. Select node types<br/>(e.g., nc:Person, j:CrashDriver)
    User->>UI: 7. Click "Run Entity Resolution"

    UI->>API: POST /api/entity-resolution/run<br/>{selectedNodeTypes: ['nc:Person']}
    activate API

    Note over API: handler: handle_entity_resolution()

    API->>Neo4j: 8. Extract entities<br/>MATCH (n) WHERE n.qname IN $types
    Neo4j-->>API: List of entity nodes with properties

    API->>API: 9. Check Senzing license

    alt Senzing Available
        Note over API: Using Senzing SDK

        loop For each entity
            API->>Senzing: 10. Add record<br/>add_record(data_source, record_id, json)
            Senzing-->>API: Record added
        end

        loop For each entity
            API->>Senzing: 11. Get entity<br/>get_entity_by_record_id(record_id)
            Senzing-->>API: Resolved entity data<br/>{ENTITY_ID, RECORDS[], MATCH_KEY}

            API->>API: 12. Group by Senzing ENTITY_ID<br/>(duplicates have same ENTITY_ID)
        end

        API->>API: 13. Extract match details<br/>(confidence, match_keys, feature_scores)

    else Senzing Not Available
        Note over API: Using text-based matching

        API->>API: 14. Extract names<br/>(PersonGivenName, PersonSurName, etc.)

        API->>API: 15. Normalize names<br/>(lowercase, remove punctuation)

        API->>API: 16. Group by normalized name<br/>(create_match_key)
    end

    API->>API: 17. Identify duplicate groups<br/>(groups with 2+ entities)

    loop For each duplicate group
        API->>Neo4j: 18. Create ResolvedEntity<br/>CREATE (re:ResolvedEntity {props})
        Neo4j-->>API: ResolvedEntity created

        loop For each entity in group
            API->>Neo4j: 19. Create RESOLVED_TO edge<br/>MATCH (e), (re) CREATE (e)-[:RESOLVED_TO {props}]->(re)
            Neo4j-->>API: Relationship created
        end
    end

    API->>Neo4j: 20. Create relationships<br/>between ResolvedEntity nodes
    Neo4j-->>API: Relationships created

    API-->>UI: 21. Success response<br/>{resolvedEntitiesCreated, matchDetails}
    deactivate API

    UI-->>User: 22. Show results<br/>"Found 15 duplicates, created 5 clusters"
    User->>UI: 23. Expand "Match Details"
    UI-->>User: 24. Show match transparency<br/>(match quality, attributes used, rules)
```

### Key Steps Explained

**Step 8**: Entity extraction query
```cypher
MATCH (entity)
WHERE entity.qname IN $selectedNodeTypes
  AND entity._upload_id IS NOT NULL
RETURN entity
```

**Step 10-11**: Senzing integration (if licensed)
- Converts each entity to Senzing JSON format
- Adds to Senzing engine
- Retrieves resolution results with match details

**Step 12**: Grouping by Senzing ENTITY_ID
```python
resolved_entities = {}
for result in senzing_results:
    senzing_entity_id = result['ENTITY_ID']
    if senzing_entity_id not in resolved_entities:
        resolved_entities[senzing_entity_id] = []
    resolved_entities[senzing_entity_id].append(entity)
```

**Step 14-16**: Text-based fallback (no license)
```python
match_key = f"{given_name.lower()}_{surname.lower()}"
entity_groups[match_key].append(entity)
```

**Step 18**: ResolvedEntity creation
```cypher
CREATE (re:ResolvedEntity {
  entity_id: $entity_id,
  name: $name,
  resolved_count: $count,
  resolution_method: 'senzing',
  confidence: $confidence,
  _upload_ids: $upload_ids,
  _schema_ids: $schema_ids
})
```

**Step 21**: Match details include
- Match quality distribution (high/medium/low confidence)
- Common match keys (which attributes were used)
- Feature scores (attribute quality)
- Resolution rules applied

### Entity Resolution Decision Flow

```mermaid
graph TD
    A[Start Entity Resolution] --> B{Senzing<br/>Available?}

    B -->|Yes| C[Use Senzing SDK]
    B -->|No| D[Use Text-Based Matching]

    C --> E[Convert entities to Senzing format]
    E --> F[Add records to Senzing engine]
    F --> G[Get resolution results]
    G --> H[Extract match details]
    H --> I[Group by ENTITY_ID]

    D --> J[Extract name fields]
    J --> K[Normalize names]
    K --> L[Group by match key]

    I --> M[Create ResolvedEntity nodes]
    L --> M

    M --> N[Create RESOLVED_TO edges]
    N --> O[Return results + match details]
```

---

## Workflow 4: Schema Designer

### Purpose

Load schema element tree, allow user to select which elements become nodes, generate customized mapping.yaml with flattening rules, and enable mapping mode for subsequent ingestion.

### Sequence Diagram

```mermaid
sequenceDiagram
    actor User
    participant UI as Web UI<br/>(Schema Designer)
    participant API as API Service
    participant MinIO as MinIO Storage
    participant Designer as Schema Designer Service

    User->>UI: 1. Navigate to Schema Designer<br/>(select schema)

    UI->>API: GET /api/schema/{schema_id}/element-tree
    activate API

    API->>MinIO: 2. Get CMF file<br/>get_object(schema_id/schema.cmf)
    MinIO-->>API: CMF content

    API->>Designer: 3. Parse CMF<br/>build_element_tree(cmf)
    activate Designer

    Designer->>Designer: 4. Traverse schema<br/>(depth-first traversal)

    loop For each element
        Designer->>Designer: 5. Analyze element<br/>(type, cardinality, properties)

        Designer->>Designer: 6. Determine node type<br/>(object/association/augmentation/property)

        Designer->>Designer: 7. Count nested objects/properties

        Designer->>Designer: 8. Generate warnings<br/>(complex augmentations, deep nesting)
    end

    Designer->>Designer: 9. Build tree structure<br/>(parent-child relationships)

    Designer-->>API: 10. Element tree<br/>[{qname, node_type, children, ...}]
    deactivate Designer

    API->>MinIO: 11. Check for saved selections<br/>get_object(schema_id/selections.json)

    alt Selections exist
        MinIO-->>API: selections.json
        API->>API: 12. Apply saved selections
    else No selections
        MinIO-->>API: 404 Not Found
        API->>API: 13. Use default selections<br/>(all selected)
    end

    API-->>UI: 14. Element tree + selections<br/>{nodes, selected}
    deactivate API

    UI-->>User: 15. Show element tree<br/>(expandable hierarchy)

    User->>UI: 16. Customize selections<br/>(check/uncheck elements)
    User->>UI: 17. Expand/collapse nodes

    Note over User,UI: User iterates until satisfied

    User->>UI: 18. Click "Apply Design"

    UI->>API: POST /api/schema/{schema_id}/apply-design<br/>{selections: {qname: true/false}}
    activate API

    API->>API: 19. Validate selections<br/>(check associations have endpoints)

    alt Validation failed
        API-->>UI: 400 Bad Request<br/>"Association missing endpoints"
        UI-->>User: Show validation errors
    else Validation passed
        API->>MinIO: 20. Save selections<br/>put_object(schema_id/selections.json)
        MinIO-->>API: Selections saved

        API->>Designer: 21. Regenerate mapping.yaml<br/>with flattening rules
        activate Designer

        Designer->>Designer: 22. Build mapping<br/>(only selected elements)

        Designer->>Designer: 23. Generate flattened paths<br/>(unselected → property paths)

        Designer->>Designer: 24. Create references list

        Designer-->>API: 25. New mapping.yaml
        deactivate Designer

        API->>MinIO: 26. Save mapping<br/>put_object(schema_id/mapping.yaml)
        MinIO-->>API: Mapping saved

        API-->>UI: 27. Success response<br/>{selected_nodes, mapping_filename}
        deactivate API

        UI-->>User: 28. Show confirmation<br/>"Design applied successfully"

        Note over UI,User: Future ingestion uses<br/>customized mapping
    end
```

### Key Steps Explained

**Step 4**: Element tree traversal algorithm
```python
def traverse(element, depth=0):
    node = {
        'qname': element.qname,
        'depth': depth,
        'children': []
    }

    for child in element.children:
        child_node = traverse(child, depth + 1)
        node['children'].append(child_node)

    return node
```

**Step 6**: Node type determination
- **object**: Extends structures:ObjectType (can have structures:id)
- **association**: Extends structures:AssociationType
- **augmentation**: Augmentation point elements
- **property**: Simple property wrappers

**Step 12**: Apply saved selections
```python
for node in element_tree:
    node['selected'] = selections.get(node['qname'], True)
```

**Step 19**: Validation rules
- Associations must have at least 2 endpoints selected
- At least 1 element must be selected
- Circular references detected and allowed

**Step 23**: Flattening path generation
```python
# If PersonName NOT selected → flatten
unselected_complex_type = 'nc:PersonName'
parent_path = 'nc:Person'

# Generate flattened path
flattened_properties = [
    f"{parent_path}_nc_PersonGivenName",
    f"{parent_path}_nc_PersonSurName"
]
```

### Schema Designer State Machine

```mermaid
stateDiagram-v2
    [*] --> AutoGenerated: Schema uploaded

    AutoGenerated --> Customizing: User opens designer
    AutoGenerated: All elements selected<br/>mapping.yaml auto-generated

    Customizing --> Customizing: User toggles selections
    Customizing: Element tree loaded<br/>User makes changes

    Customizing --> Validating: User clicks "Apply Design"

    Validating --> ValidationFailed: Validation errors
    Validating --> Applied: Validation passes
    ValidationFailed --> Customizing: Fix selections

    Applied --> Customizing: User makes more changes
    Applied: selections.json saved<br/>mapping.yaml regenerated<br/>Mapping Mode enabled

    Applied --> [*]: Design complete
```

---

## Workflow 5: Graph Query and Visualization

### Purpose

Execute Cypher queries against Neo4j, retrieve graph data, and render interactive visualization.

### Sequence Diagram

```mermaid
sequenceDiagram
    actor User
    participant UI as Graph Viewer<br/>(Cytoscape.js)
    participant API as API Service
    participant Neo4j as Neo4j Database

    User->>UI: 1. Navigate to Graph page

    UI->>API: GET /api/entity-resolution/status
    API->>Neo4j: Query resolution stats
    Neo4j-->>API: Stats
    API-->>UI: Resolution status

    User->>UI: 2. Click "Load Graph"

    UI->>API: POST /api/graph/query<br/>{cypher: "MATCH (n)-[r]-(m) RETURN ...", limit: 100}
    activate API

    API->>Neo4j: 3. Execute Cypher<br/>(with parameters)
    activate Neo4j

    Neo4j-->>API: 4. Result set<br/>(nodes and relationships)
    deactivate Neo4j

    API->>API: 5. Format for Cytoscape<br/>(convert to graph JSON)

    API-->>UI: 6. Graph data<br/>{nodes: [...], edges: [...]}
    deactivate API

    UI->>UI: 7. Render graph<br/>(Cytoscape layout)

    UI-->>User: 8. Show interactive graph

    User->>UI: 9. Click node

    UI->>UI: 10. Show node inspector<br/>(properties, relationships)

    alt User wants details
        UI->>API: GET /api/graph/node/{id}
        API->>Neo4j: MATCH (n {id: $id})
        Neo4j-->>API: Node details
        API-->>UI: Full node data
        UI-->>User: Show in side panel
    end
```

---

## Error Handling Flows

### General Error Handling Pattern

```mermaid
sequenceDiagram
    participant UI
    participant API
    participant Service as External Service

    UI->>API: Request

    alt Happy Path
        API->>Service: Process
        Service-->>API: Success
        API-->>UI: 200 OK
    else Service Error
        API->>Service: Process
        Service-->>API: Error
        API->>API: Log error
        API-->>UI: 500/503 Error<br/>{message, details}
        UI->>UI: Show error toast
    else Validation Error
        API->>API: Validate input
        API-->>UI: 400 Bad Request<br/>{validation_errors}
        UI->>UI: Highlight fields
    else Not Found
        API->>Service: Query
        Service-->>API: Not found
        API-->>UI: 404 Not Found
        UI->>UI: Show "not found" message
    end
```

### Retry Logic

For transient failures (Neo4j connection, MinIO timeout):

```mermaid
graph TD
    A[API Call] --> B[Try Operation]
    B --> C{Success?}

    C -->|Yes| D[Return Result]
    C -->|No| E{Retryable<br/>Error?}

    E -->|No| F[Return Error]
    E -->|Yes| G{Retry<br/>Count < 3?}

    G -->|No| F
    G -->|Yes| H[Wait exponential<br/>backoff]
    H --> B
```

---

## Related Documentation

- **[ARCHITECTURE.md](../ARCHITECTURE.md)** - System architecture overview
- **[GRAPH_SCHEMA.md](GRAPH_SCHEMA.md)** - Neo4j data model and patterns
- **[API_ARCHITECTURE.md](API_ARCHITECTURE.md)** - Detailed API layer design
- **[INGESTION_AND_MAPPING.md](INGESTION_AND_MAPPING.md)** - Data transformation details
- **[schema_designer.md](schema_designer.md)** - Schema designer architecture
- **[senzing-integration.md](senzing-integration.md)** - Entity resolution setup

---

**Last Updated**: 2024-11-08
**Documentation Version**: 1.0
