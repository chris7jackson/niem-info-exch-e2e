---
name: Ensure root node inclusion and prevent orphaned nodes
about: Always include document root in graph and validate no orphaned nodes exist
title: 'Ensure root node inclusion and prevent orphaned nodes in graph'
labels: enhancement, graph, bug
assignees: ''
---

## Problem Statement

The current graph generation logic may skip document root elements (like `NEICETransmittalDocument`) if they're not explicitly mapped in `mapping.yaml`, potentially creating disconnected subgraphs or orphaned nodes.

Document roots are semantically important as they:
- Define the message/exchange type
- Provide context for all child elements
- Serve as entry points for graph traversal

## User Value

- **Complete graph structure**: All documents start with identifiable root node
- **Better queryability**: Can find all documents of a specific type (e.g., all CrashDriver exchanges)
- **No data loss**: All nodes reachable from root
- **Validation confidence**: Detect structural issues early

## Current Behavior

1. Root elements without mapping or `structures:id` may be skipped
2. Traversal starts from children, potentially creating forest instead of tree
3. No validation for orphaned nodes after ingestion
4. Root node treatment is inconsistent between XML and JSON ingestion

## Desired Behavior

1. **Always create root node**, even if not explicitly mapped
2. **Use document element name** as node label if no mapping exists
3. **Validate no orphaned nodes** exist after graph generation
4. **Add metadata** to root node indicating it's a document root (`isDocumentRoot: true`)
5. **Consistent behavior** across XML and JSON ingestion

## Acceptance Criteria

- [ ] Document root node always created in graph
- [ ] Root node has label derived from element name (e.g., `NEICETransmittalDocument`)
- [ ] Root node has `isDocumentRoot: true` property
- [ ] Root node has `sourceDoc` property linking back to original file
- [ ] Orphan detection validation runs after graph generation
- [ ] Validation fails/warns if orphaned nodes detected
- [ ] Works for both XML and JSON ingestion
- [ ] All child elements connected through root via containment edges
- [ ] Tests verify root node presence and no orphans

## Technical Context

**Files to modify:**
- `api/src/niem_api/services/domain/xml_to_graph/converter.py`
  - Function: `generate_for_xml_content()` - Root traversal logic (line ~636)
  - Current code skips unmapped roots
- `api/src/niem_api/services/domain/json_to_graph/converter.py`
  - Similar root handling needed

**Current problematic code:**
```python
# Skip root element and process children if not mapped
if root_qn not in obj_rules and not root_has_id:
    for child in list(root):
        traverse(child, None, [])
else:
    traverse(root, None, [])
```

**Proposed fix:**
```python
# Always process root element
traverse(root, None, [])
```

**Orphan detection:**
```python
def detect_orphaned_nodes(nodes, contains, edges):
    """Detect nodes not reachable from root"""
    # Build reachability graph
    # DFS/BFS from root
    # Report unreachable nodes
```

## Implementation Notes

1. **Root Node Creation:**
   - Always call `traverse()` on root element
   - Generate synthetic ID if no `structures:id`
   - Use format: `{file_prefix}_root_{element_name}`

2. **Orphan Detection Algorithm:**
   - After graph generation, build adjacency list from edges
   - Find root nodes (`isDocumentRoot: true`)
   - Perform graph traversal from each root
   - Mark visited nodes
   - Report any unvisited nodes as orphans

3. **Validation Strategy:**
   - Add optional validation mode (default: warn)
   - Return validation results in response
   - Log orphaned nodes for debugging
   - Consider optional strict mode (fail on orphans)

4. **Backward Compatibility:**
   - Existing graphs may have implicit roots
   - Migration script to add `isDocumentRoot` property
   - Document behavior change in release notes

## Test Cases

```python
# Test Case 1: Unmapped root element
xml_content = """
<custom:DocumentRoot>
  <nc:Person>...</nc:Person>
</custom:DocumentRoot>
"""
# Expected: DocumentRoot node created with isDocumentRoot=true

# Test Case 2: Orphan detection
# Create graph with intentionally disconnected node
# Expected: Validation detects orphan

# Test Case 3: Multiple roots (batch upload)
# Expected: Each document has its own root node
```

## Related Issues

- Related to: #1 (augmentation flattening)
- Blocks: None
- Impacts: All graph queries and visualization

## Priority

**High** - Data integrity issue, affects all ingestion

## Estimated Effort

**Medium (M)** - ~4-8 hours
- Root node logic is straightforward
- Orphan detection adds complexity
- Testing across XML/JSON converters
- Validation integration

## Additional Context

**NIEM Best Practices:**
- Information Exchange Package Documentation (IEPD) always has a root element
- Root element defines the exchange message type
- Example: `j:Crash`, `nc:Case`, `custom:NEICETransmittalDocument`

**Example Query Enabled:**
```cypher
// Find all CrashDriver exchanges
MATCH (root:NEICETransmittalDocument {isDocumentRoot: true})
RETURN root, root.sourceDoc

// Find documents with orphaned data
MATCH (n)
WHERE NOT ()--(n) AND NOT n.isDocumentRoot
RETURN n // Should return empty set
```
