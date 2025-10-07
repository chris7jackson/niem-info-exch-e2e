# CMF Parser Design Specification

## Overview

The CMF Parser is a Python module that parses NIEM Common Model Format (CMF) XML files and transforms them into a graph data structure suitable for interactive visualization.

## Purpose

Convert NIEM CMF XML schemas stored in MinIO into a standardized JSON graph format that can be consumed by frontend visualization libraries (Cytoscape.js).

## Input

### Source Data
- **Location**: MinIO bucket `niem-schemas` at path `{schema_id}/schema.cmf`
- **Format**: CMF XML conforming to OASIS NIEM CMF 1.0 specification
- **Namespace**: `https://docs.oasis-open.org/niemopen/ns/specification/cmf/1.0/`
- **Size**: Typically 100KB - 10MB (500-5000 element schemas)

### CMF Structure Elements
The parser processes these CMF XML elements:

1. **`<Namespace>`** - Namespace declarations
   - Attributes: `structures:id` (unique namespace identifier)
   - Children: `<NamespaceURI>`, `<NamespacePrefixText>`, `<NamespaceCategoryCode>`, `<DocumentationText>`

2. **`<Class>`** - Type definitions (ObjectType, AssociationType, etc.)
   - Attributes: `structures:id` (unique class identifier)
   - Children: `<Name>`, `<Namespace>`, `<DefinitionText>`, `<AbstractIndicator>`, `<HasProperty>`, `<HasSubClass>`, `<AugmentableIndicator>`

3. **`<Property>`** - Data and object properties
   - Attributes: `structures:id` (unique property identifier)
   - Children: `<Name>`, `<Namespace>`, `<Class>` (ref to type), `<DefinitionText>`

4. **`<HasProperty>`** - Property membership in classes
   - Attributes: `structures:ref` (references Property)
   - Children: `<MinOccursQuantity>`, `<MaxOccursQuantity>`

5. **`<Association>`** - Relationship types
   - Children: `<SourceClass>`, `<TargetClass>`, `<DefinitionText>`

6. **`<AugmentationRecord>`** - NIEM augmentations
   - Children: `<Class>` (target class), `<DataProperty>` (added property), `<MinOccursQuantity>`, `<MaxOccursQuantity>`

## Output

### JSON Graph Structure

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
      "documentation": "A data type for a human being",
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
      "documentation": "A name of a person",
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
      "documentation": "A name of a person"
    },
    {
      "id": "edge_j.CrashType_nc.PersonType",
      "source": "j.CrashType",
      "target": "nc.PersonType",
      "label": "CrashDriver",
      "edgeType": "association",
      "cardinality": "[1..unbounded]",
      "documentation": "A relationship between a crash and a driver"
    }
  ],
  "namespaces": [
    {
      "id": "nc",
      "prefix": "nc",
      "uri": "https://docs.oasis-open.org/niemopen/ns/model/niem-core/6.0/",
      "category": "CORE",
      "label": "NIEM Core",
      "documentation": "NIEM Core namespace",
      "classCount": 423,
      "propertyCount": 1243
    }
  ],
  "metadata": {
    "schemaId": "abc123...",
    "totalNodes": 1666,
    "totalEdges": 3421,
    "namespaceCount": 4,
    "parseDate": "2025-01-07T12:00:00Z",
    "cmfVersion": "1.0"
  }
}
```

### Node Schema

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | Yes | Unique identifier (format: `{prefix}.{localName}`) |
| `label` | string | Yes | Display name (localName only) |
| `namespace` | string | Yes | Namespace prefix |
| `namespaceURI` | string | Yes | Full namespace URI |
| `namespaceCategory` | string | Yes | Category from CMF `NamespaceCategoryCode` (e.g., "CORE", "DOMAIN", "EXTENSION") |
| `nodeType` | string | Yes | Derived from CMF structure (e.g., "class", "property", "association", "augmentation") |
| `documentation` | string | No | Definition text from CMF |
| `hasChildren` | boolean | Yes | True if node has outgoing edges (for expand/collapse) |
| `depth` | integer | Yes | Hierarchical depth (0 = root) |
| `metadata` | object | Yes | Type-specific metadata |

**Note**: `namespaceCategory` and `nodeType` values are extracted directly from CMF and passed through without validation. The frontend should handle any category/type value dynamically.

### Edge Schema

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | Yes | Unique edge identifier |
| `source` | string | Yes | Source node ID |
| `target` | string | Yes | Target node ID |
| `label` | string | Yes | Property or relationship name |
| `edgeType` | string | Yes | Relationship type from CMF (e.g., "property", "association", "augmentation", "extends") |
| `cardinality` | string | No | Format: `[min..max]` (e.g., `[0..unbounded]`) |
| `documentation` | string | No | Relationship definition |

**Note**: `edgeType` values are derived from CMF structure analysis. Frontend should handle any edge type value dynamically.

### Namespace Schema

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | Yes | Namespace prefix |
| `prefix` | string | Yes | Namespace prefix (same as id) |
| `uri` | string | Yes | Full namespace URI |
| `category` | string | Yes | Category from CMF `NamespaceCategoryCode` (passed through as-is) |
| `label` | string | Yes | Human-readable name (generated from prefix or documentation) |
| `documentation` | string | No | Namespace documentation from CMF |
| `classCount` | integer | Yes | Number of classes in this namespace |
| `propertyCount` | integer | Yes | Number of properties in this namespace |

**Note**: All category values come directly from CMF without hardcoded mappings. The frontend should provide appropriate visualizations based on the actual category values present in the data.

## Parsing Algorithm

### Phase 1: Parse Namespaces

```python
def parse_namespaces(cmf_root):
    """Extract all namespace declarations."""
    namespaces = {}

    for ns_elem in cmf_root.findall('.//cmf:Namespace', NAMESPACES):
        ns_id = ns_elem.get('{' + STRUCT_NS + '}id')

        namespace = {
            'id': extract_text(ns_elem, './/cmf:NamespacePrefixText'),
            'prefix': extract_text(ns_elem, './/cmf:NamespacePrefixText'),
            'uri': extract_text(ns_elem, './/cmf:NamespaceURI'),
            'category': extract_text(ns_elem, './/cmf:NamespaceCategoryCode'),
            'label': generate_label_from_prefix(...),
            'documentation': extract_text(ns_elem, './/cmf:DocumentationText'),
            'classCount': 0,  # Calculated later
            'propertyCount': 0  # Calculated later
        }

        namespaces[ns_id] = namespace

    return namespaces
```

### Phase 2: Parse Classes (Nodes)

```python
def parse_classes(cmf_root, namespaces):
    """Extract all class definitions as nodes."""
    nodes = []

    for class_elem in cmf_root.findall('.//cmf:Class', NAMESPACES):
        class_id = class_elem.get('{' + STRUCT_NS + '}id')
        class_name = extract_text(class_elem, './/cmf:Name')
        ns_ref = class_elem.find('.//cmf:Namespace', NAMESPACES).get('{' + STRUCT_NS + '}ref')

        namespace = namespaces[ns_ref]

        node = {
            'id': class_id,
            'label': class_name,
            'namespace': namespace['prefix'],
            'namespaceURI': namespace['uri'],
            'namespaceCategory': namespace['category'],
            'nodeType': 'class',
            'documentation': extract_text(class_elem, './/cmf:DefinitionText'),
            'hasChildren': len(class_elem.findall('.//cmf:HasProperty', NAMESPACES)) > 0,
            'depth': 0,  # Calculated in Phase 4
            'metadata': {
                'abstract': extract_bool(class_elem, './/cmf:AbstractIndicator'),
                'baseType': extract_base_type(class_elem),
                'augmentable': extract_bool(class_elem, './/cmf:AugmentableIndicator'),
                'file': namespace.get('file', ''),
                'propertyCount': len(class_elem.findall('.//cmf:HasProperty', NAMESPACES)),
                'usageCount': 0  # Calculated later
            }
        }

        nodes.append(node)
        namespace['classCount'] += 1

    return nodes
```

### Phase 3: Parse Properties and Build Edges

```python
def parse_properties_and_edges(cmf_root, namespaces, class_nodes):
    """Extract properties and create edges."""
    edges = []
    property_nodes = []

    for class_elem in cmf_root.findall('.//cmf:Class', NAMESPACES):
        class_id = class_elem.get('{' + STRUCT_NS + '}id')

        for has_prop in class_elem.findall('.//cmf:HasProperty', NAMESPACES):
            prop_ref = has_prop.get('{' + STRUCT_NS + '}ref')

            # Find property definition
            prop_elem = cmf_root.find(f".//cmf:Property[@structures:id='{prop_ref}']", NAMESPACES)
            if not prop_elem:
                continue

            prop_name = extract_text(prop_elem, './/cmf:Name')
            prop_type_ref = prop_elem.find('.//cmf:Class', NAMESPACES).get('{' + STRUCT_NS + '}ref')

            # Get cardinality
            min_occurs = extract_text(has_prop, './/cmf:MinOccursQuantity') or '1'
            max_occurs = extract_text(has_prop, './/cmf:MaxOccursQuantity') or '1'
            cardinality = f"[{min_occurs}..{max_occurs}]"

            # Create edge
            edge = {
                'id': f"edge_{class_id}_{prop_ref}",
                'source': class_id,
                'target': prop_type_ref,
                'label': prop_name,
                'edgeType': 'property',
                'cardinality': cardinality,
                'documentation': extract_text(prop_elem, './/cmf:DefinitionText')
            }

            edges.append(edge)

    return property_nodes, edges
```

### Phase 4: Parse Associations

```python
def parse_associations(cmf_root, namespaces):
    """Extract association types as special edges."""
    association_edges = []

    for assoc_elem in cmf_root.findall('.//cmf:Association', NAMESPACES):
        assoc_id = assoc_elem.get('{' + STRUCT_NS + '}id')
        assoc_name = extract_text(assoc_elem, './/cmf:Name')

        source_ref = assoc_elem.find('.//cmf:SourceClass', NAMESPACES).get('{' + STRUCT_NS + '}ref')
        target_ref = assoc_elem.find('.//cmf:TargetClass', NAMESPACES).get('{' + STRUCT_NS + '}ref')

        edge = {
            'id': f"assoc_{assoc_id}",
            'source': source_ref,
            'target': target_ref,
            'label': assoc_name,
            'edgeType': 'association',
            'cardinality': extract_cardinality(assoc_elem),
            'documentation': extract_text(assoc_elem, './/cmf:DefinitionText')
        }

        association_edges.append(edge)

    return association_edges
```

### Phase 5: Parse Augmentations

```python
def parse_augmentations(cmf_root):
    """Extract augmentation records as edges."""
    augmentation_edges = []

    for aug_elem in cmf_root.findall('.//cmf:AugmentationRecord', NAMESPACES):
        target_class_ref = aug_elem.find('.//cmf:Class', NAMESPACES).get('{' + STRUCT_NS + '}ref')
        prop_ref = aug_elem.find('.//cmf:DataProperty', NAMESPACES).get('{' + STRUCT_NS + '}ref')

        # Find the property's type
        prop_elem = cmf_root.find(f".//cmf:Property[@structures:id='{prop_ref}']", NAMESPACES)
        if not prop_elem:
            continue

        prop_name = extract_text(prop_elem, './/cmf:Name')
        prop_type_ref = prop_elem.find('.//cmf:Class', NAMESPACES).get('{' + STRUCT_NS + '}ref')

        edge = {
            'id': f"aug_{target_class_ref}_{prop_ref}",
            'source': prop_type_ref,  # Source is the augmentation type
            'target': target_class_ref,  # Target is the augmented class
            'label': prop_name,
            'edgeType': 'augmentation',
            'cardinality': extract_cardinality(aug_elem),
            'documentation': f"Augments {target_class_ref} with {prop_name}"
        }

        augmentation_edges.append(edge)

    return augmentation_edges
```

### Phase 6: Calculate Depth and Usage Counts

```python
def calculate_hierarchy_depth(nodes, edges):
    """Calculate hierarchical depth for each node using BFS."""
    # Build adjacency list
    graph = defaultdict(list)
    for edge in edges:
        if edge['edgeType'] in ['property', 'extends']:
            graph[edge['source']].append(edge['target'])

    # Find root nodes (nodes with no incoming edges of type property/extends)
    incoming = set(edge['target'] for edge in edges if edge['edgeType'] in ['property', 'extends'])
    roots = [node['id'] for node in nodes if node['id'] not in incoming]

    # BFS to calculate depth
    depths = {}
    queue = [(root, 0) for root in roots]

    while queue:
        node_id, depth = queue.pop(0)
        if node_id not in depths or depth < depths[node_id]:
            depths[node_id] = depth
            for child in graph[node_id]:
                queue.append((child, depth + 1))

    # Update node depths
    for node in nodes:
        node['depth'] = depths.get(node['id'], 0)

    return nodes

def calculate_usage_counts(nodes, edges):
    """Calculate how many times each type is referenced."""
    usage = defaultdict(int)
    for edge in edges:
        usage[edge['target']] += 1

    for node in nodes:
        node['metadata']['usageCount'] = usage[node['id']]

    return nodes
```

## Error Handling

### Malformed CMF
```python
try:
    tree = ET.parse(cmf_file)
    root = tree.getroot()
except ET.ParseError as e:
    raise CMFParseError(f"Invalid XML: {str(e)}")

if root.tag != '{https://docs.oasis-open.org/niemopen/ns/specification/cmf/1.0/}Model':
    raise CMFParseError("Root element is not CMF Model")
```

### Missing Elements
```python
def extract_text(element, xpath, default=''):
    """Safely extract text from XML element."""
    found = element.find(xpath, NAMESPACES)
    return found.text.strip() if found is not None and found.text else default

def extract_ref(element, xpath, required=True):
    """Safely extract structure reference."""
    found = element.find(xpath, NAMESPACES)
    if found is None:
        if required:
            raise CMFParseError(f"Required reference not found: {xpath}")
        return None
    return found.get('{' + STRUCT_NS + '}ref')
```

### Unresolved References
```python
def validate_references(nodes, edges):
    """Ensure all edge references point to existing nodes."""
    node_ids = set(node['id'] for node in nodes)

    invalid_edges = []
    for edge in edges:
        if edge['source'] not in node_ids:
            invalid_edges.append(edge)
            logging.warning(f"Edge {edge['id']} references non-existent source: {edge['source']}")
        if edge['target'] not in node_ids:
            invalid_edges.append(edge)
            logging.warning(f"Edge {edge['id']} references non-existent target: {edge['target']}")

    # Remove invalid edges
    valid_edges = [e for e in edges if e not in invalid_edges]
    return valid_edges
```

## Performance Considerations

### Expected Parse Times
- Small schema (< 100 types): < 100ms
- Medium schema (100-500 types): 100-500ms
- Large schema (500-2000 types): 500ms - 2s
- Very large schema (2000-5000 types): 2-5s

### Optimization Strategies

1. **Use ElementTree iterparse for large files** (> 5MB)
2. **Build lookup dictionaries** for O(1) reference resolution
3. **Single-pass parsing** where possible
4. **Lazy loading** - don't expand all relationships immediately
5. **Caching** - cache parsed results in memory for session

## Testing Strategy

### Unit Tests

1. **test_parse_namespaces()**
   - Input: CMF with 3 namespaces (CORE, DOMAIN, EXTENSION)
   - Expected: 3 namespace objects with correct prefixes and categories

2. **test_parse_classes()**
   - Input: CMF with 5 classes
   - Expected: 5 node objects with correct IDs, labels, and metadata

3. **test_parse_properties_and_edges()**
   - Input: CMF with PersonType having 3 properties
   - Expected: 3 edges from PersonType to property types

4. **test_parse_associations()**
   - Input: CMF with CrashDriverAssociation
   - Expected: Association edge from CrashType to PersonType

5. **test_parse_augmentations()**
   - Input: CMF with PersonAugmentation
   - Expected: Augmentation edge to PersonType

6. **test_calculate_depth()**
   - Input: Graph with 3-level hierarchy
   - Expected: Root depth=0, children depth=1, grandchildren depth=2

7. **test_error_handling_invalid_xml()**
   - Input: Malformed XML
   - Expected: CMFParseError raised

8. **test_error_handling_missing_reference()**
   - Input: CMF with dangling reference
   - Expected: Warning logged, invalid edge removed

### Integration Tests

1. **test_parse_crashdriver_cmf()**
   - Input: Real CrashDriver CMF file
   - Expected: Complete graph with all NIEM Core + Justice + Extension types

2. **test_parse_large_schema()**
   - Input: Full NIEM 6.0 Core (1000+ types)
   - Expected: Parse completes in < 3s, all types present

## Dependencies

- `xml.etree.ElementTree` - XML parsing (Python stdlib)
- `collections.defaultdict` - Graph building (Python stdlib)
- `logging` - Error reporting (Python stdlib)

## Module Interface

```python
class CMFParser:
    """Parse CMF XML into graph structure."""

    def __init__(self):
        self.namespaces = {}
        self.nodes = []
        self.edges = []

    def parse(self, cmf_content: str) -> Dict[str, Any]:
        """Parse CMF XML and return graph structure.

        Args:
            cmf_content: CMF XML as string

        Returns:
            Dictionary with keys: nodes, edges, namespaces, metadata

        Raises:
            CMFParseError: If CMF is malformed or invalid
        """
        pass

    def parse_file(self, cmf_file_path: str) -> Dict[str, Any]:
        """Parse CMF from file path.

        Args:
            cmf_file_path: Path to CMF XML file

        Returns:
            Dictionary with keys: nodes, edges, namespaces, metadata
        """
        pass


class CMFParseError(Exception):
    """Raised when CMF parsing fails."""
    pass
```

## Future Enhancements

1. **Incremental parsing** for very large schemas (> 10MB)
2. **Parallel processing** of namespace sections
3. **Graph simplification** - merge trivial intermediate nodes
4. **Cycle detection** in type hierarchies
5. **Support for CMF 2.0** when specification is released
