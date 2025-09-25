# Graph Creation Process Documentation

## Overview

This document provides a comprehensive technical overview of how data is ingested and converted into a Neo4j graph database within the NIEM Information Exchange system. The process involves multiple stages from file upload through graph storage, with different pathways for XML and JSON data.

## Architecture Overview

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   File Upload   │───▶│  Data Ingestion  │───▶│ Graph Creation  │
│  (XML/JSON)     │    │   & Parsing      │    │   (Neo4j)       │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                │
                                ▼
                       ┌──────────────────┐
                       │ Schema Mapping   │
                       │   & Validation   │
                       └──────────────────┘
```

## Core Components

### 1. Entry Points (`/Users/cjackson/Workspace/GraphRAG/niem-info-exch-e2e/api/src/niem_api/handlers/ingest.py`)

#### XML Ingestion: `handle_xml_ingestion()`
- **Purpose**: Process uploaded XML files and convert to graph
- **Input**: List of `UploadFile` objects, S3 client
- **Process**:
  1. File validation and reading
  2. Schema mapping retrieval
  3. XML parsing to graph data
  4. Neo4j node/relationship creation
  5. File storage in MinIO (post-success)

#### JSON Ingestion: `handle_json_ingestion()`
- **Purpose**: Process uploaded JSON files and convert to graph
- **Input**: List of `UploadFile` objects, S3 client
- **Process**:
  1. File validation and JSON parsing
  2. Schema mapping retrieval
  3. JSON parsing to graph data
  4. Neo4j node/relationship creation
  5. File storage in MinIO (post-success)

### 2. Graph Data Parsers

#### XML Parser: `_parse_xml_to_graph_data_comprehensive()`
**Location**: Lines ~279-450 in ingest.py

**Purpose**: Convert XML structure to graph nodes and relationships based on element hierarchy

**Algorithm**:
```python
def _parse_xml_to_graph_data_comprehensive(xml_content, mapping, filename):
    """
    Structure-based XML parsing that creates nodes from XML elements
    and relationships from element containment hierarchy
    """
    # 1. Initialize tracking
    root = ET.fromstring(xml_content)
    nodes = []
    relationships = []
    node_counter = 0
    file_hash = hashlib.md5(filename.encode()).hexdigest()[:8]

    # 2. Helper functions
    def _get_clean_tag_name(element):
        # Remove namespace prefixes: {namespace}tag -> tag

    def _extract_text_content(element):
        # Get direct text content (not from children)

    def _extract_attributes(element):
        # Extract all XML attributes as properties

    # 3. Recursive element processing
    def _process_element(element, parent_node_id=None, level=0):
        # Generate unique node ID
        node_id = f"{file_hash}_node_{node_counter}"

        # Create node with tag name as label
        node_data = {
            "label": tag_name,
            "properties": {
                "node_id": node_id,
                "xml_tag": tag_name,
                "level": level,
                "source_file": filename,
                "content": text_content,  # Direct text between tags
                "type": "leaf|mixed|container|empty"
            }
        }

        # Create parent-child relationship
        if parent_node_id:
            relationship = {
                "type": "CONTAINS",
                "from_id": parent_node_id,
                "to_id": node_id,
                "properties": {"xml_relationship": "parent_child"}
            }

        # Process all child elements recursively
        for child in element:
            _process_element(child, node_id, level + 1)

    # 4. Schema-derived relationships (XSD-based)
    # Create additional relationships based on XSD patterns
```

**Key Features**:
- **Content Capture**: Direct text between XML tags stored as `content` property
- **Hierarchy Preservation**: XML element containment becomes `CONTAINS` relationships
- **Namespace Handling**: Strips namespace prefixes for clean labels
- **Attribute Preservation**: All XML attributes become node properties
- **File Uniqueness**: Uses filename hash to ensure unique node IDs across files

#### JSON Parser: `_parse_json_to_graph_data_comprehensive()`
**Location**: Lines ~800-986 in ingest.py

**Purpose**: Convert JSON object structure to graph nodes and relationships

**Algorithm**:
```python
def _parse_json_to_graph_data_comprehensive(json_data, mapping, filename):
    """
    Structure-based JSON parsing that creates nodes from JSON objects/arrays/values
    and relationships from containment hierarchy
    """
    # 1. Label sanitization for Neo4j compatibility
    def sanitize_label(label):
        # Handle @context -> AT_context
        # Remove invalid characters
        # Ensure valid Neo4j label format

    # 2. Recursive JSON processing
    def create_nodes_from_json(obj, parent_id=None, level=0, key_name="root"):
        # Generate unique node ID
        current_node_id = f"{file_hash}_node_{node_counter}"

        if isinstance(obj, dict):
            # Dictionary becomes container node
            # Add simple properties directly to node
            # Recursively process nested objects/arrays

        elif isinstance(obj, list):
            # Array becomes container node
            # Process each item as child node

        else:
            # Primitive values become leaf nodes with content
            node_data = {
                "properties": {
                    "content": str(obj),  # The actual JSON value
                    "type": "leaf",
                    "data_type": type(obj).__name__
                }
            }
```

**Key Features**:
- **Content Capture**: Primitive JSON values stored as `content` property
- **Type Preservation**: JSON data types preserved in `data_type` property
- **Label Sanitization**: Converts JSON keys to valid Neo4j labels (@context → AT_context)
- **Hierarchy Mapping**: JSON nesting becomes `CONTAINS` relationships

### 3. Neo4j Integration

#### Node Creation: `_create_node()`
```python
def _create_node(session, node_data):
    """
    Create a node in Neo4j with dynamic label and properties
    """
    label = node_data["label"]
    properties = node_data["properties"]

    # Dynamic Cypher query construction
    cypher = f"MERGE (n:{label} {{node_id: $node_id}}) SET n += $props"

    # Execute with parameters to prevent injection
    session.run(cypher, node_id=properties.get("node_id"), props=properties)
```

#### Relationship Creation: `_create_relationship()`
```python
def _create_relationship(session, rel_data):
    """
    Create a relationship between nodes using node_id matching
    """
    cypher = """
    MATCH (from_node {node_id: $from_id})
    MATCH (to_node {node_id: $to_id})
    MERGE (from_node)-[r:%s]->(to_node)
    SET r += $props
    """ % rel_data["type"]

    session.run(cypher,
                from_id=rel_data["from_id"],
                to_id=rel_data["to_id"],
                props=rel_data["properties"])
```

### 4. Schema Mapping System

#### Mapping Retrieval: `get_active_schema_mapping()`
- Retrieves active XSD schema from MinIO
- Generates graph mapping specification from XSD
- Provides node/relationship templates (currently used for reference)

#### Mapping Generation: `generate_mapping_spec_from_xsd()`
**Location**: `/Users/cjackson/Workspace/GraphRAG/niem-info-exch-e2e/api/src/niem_api/handlers/schema.py`

**Purpose**: Analyze XSD schema and generate graph structure mapping

## Data Flow Diagrams

### XML Processing Flow
```
XML File Upload
      ↓
File Validation
      ↓
Schema Mapping Retrieval
      ↓
XML Parsing (ET.fromstring)
      ↓
Element Tree Traversal
      ↓
Node Creation (per element)
   ↓              ↓
Tag→Label    Text→Content
   ↓              ↓
Attribute Extraction
      ↓
Relationship Creation (parent-child)
      ↓
Neo4j Storage
      ↓
File Storage (MinIO)
```

### JSON Processing Flow
```
JSON File Upload
      ↓
File Validation & JSON Parse
      ↓
Schema Mapping Retrieval
      ↓
Recursive Object Traversal
      ↓
Node Creation (per key/value)
   ↓              ↓
Key→Label   Value→Content
   ↓              ↓
Type Classification
      ↓
Relationship Creation (containment)
      ↓
Neo4j Storage
      ↓
File Storage (MinIO)
```

## Node Types and Properties

### Common Node Properties
```javascript
{
  "node_id": "abc123_node_1",      // Unique identifier
  "source_file": "crash_data.xml", // Source filename
  "level": 2,                      // Depth in hierarchy
  "content": "Peter",              // Actual data content
  "type": "leaf|container|mixed"   // Content type classification
}
```

### XML-Specific Properties
```javascript
{
  "xml_tag": "PersonGivenName",    // Original XML tag
  "uri": "#P01",                   // structures:uri attribute
  "ref": "CH01",                   // structures:ref attribute
  // ... all other XML attributes
}
```

### JSON-Specific Properties
```javascript
{
  "json_key": "PersonGivenName",   // Original JSON key
  "data_type": "str",              // Python type name
  "array_length": 3                // For array nodes
}
```

## Relationship Types

### Primary Relationships
- **CONTAINS**: Parent-child containment (XML elements, JSON objects)
- **REFERS_TO_ENTITY**: Reference relationships (structures:ref)
- **HAS_METADATA**: Metadata associations
- **HAS_PRIVACY_METADATA**: Privacy metadata links

### Relationship Properties
```javascript
{
  "xml_relationship": "parent_child",
  "level_difference": 1,
  "child_key": "PersonName"  // For JSON containment
}
```

## Error Handling and Resilience

### File Processing Errors
1. **Validation Failures**: Invalid XML/JSON format
2. **Schema Issues**: Missing or invalid XSD schema
3. **Neo4j Errors**: Connection issues, constraint violations
4. **Storage Errors**: MinIO upload failures

### Error Recovery Strategy
- **Atomic Operations**: File only stored after successful graph creation
- **Transaction Management**: Neo4j session transactions for consistency
- **Detailed Logging**: Comprehensive error reporting for debugging
- **Graceful Degradation**: Individual file failures don't stop batch processing

## Performance Considerations

### Node Creation Optimization
- **MERGE operations**: Prevent duplicate nodes using node_id
- **Batch processing**: Process files sequentially but efficiently
- **Property indexing**: Create indexes on frequently queried properties

### Memory Management
- **Streaming parsing**: Process large files without loading entirely into memory
- **Session management**: Proper Neo4j session lifecycle
- **Resource cleanup**: Ensure connections are closed properly

## Configuration and Customization

### Parsing Behavior
- **Content extraction rules**: Configurable text content handling
- **Relationship creation**: Customizable relationship type mapping
- **Label generation**: Flexible node label strategies

### Schema Integration
- **XSD-driven mapping**: Schema-aware relationship creation
- **Validation levels**: Configurable validation strictness
- **Namespace handling**: Flexible namespace prefix strategies

## Debugging and Monitoring

### Logging Levels
```python
logger.info(f"Created node: {tag_name}({node_id}) with content: {text_content}")
logger.debug(f"Created CONTAINS relationship: {parent_node_id} -> {node_id}")
logger.error(f"Failed to create node: {e}")
```

### Metrics Tracking
- Nodes created per file
- Relationships created per file
- Processing time per file
- Error rates and types

## Future Improvement Areas

### Performance Optimization
1. **Bulk Operations**: Use Neo4j batch operations for large datasets
2. **Parallel Processing**: Multi-threaded file processing
3. **Caching**: Cache frequently used schema mappings

### Feature Enhancements
1. **Relationship Intelligence**: Smarter relationship detection from data patterns
2. **Content Analysis**: Enhanced text content processing and indexing
3. **Schema Evolution**: Support for schema versioning and migration
4. **Query Optimization**: Pre-computed graph statistics and indexes

### Monitoring and Observability
1. **Performance Metrics**: Detailed timing and resource usage tracking
2. **Data Quality**: Validation and quality metrics for ingested data
3. **Process Visualization**: Real-time monitoring of ingestion pipeline

## Testing Strategy

### Unit Tests
- Individual parser function testing
- Node/relationship creation validation
- Schema mapping accuracy

### Integration Tests
- End-to-end file processing
- Neo4j integration validation
- Error handling verification

### Performance Tests
- Large file processing benchmarks
- Memory usage profiling
- Concurrent processing validation