---
name: Convert associations to enriched relationship edges
about: Transform NIEM association nodes into rich edges with properties
title: 'Convert NIEM associations to enriched relationship edges'
labels: enhancement, graph, niem
assignees: ''
---

## Problem Statement

NIEM associations (e.g., `PersonChargeAssociation`) are currently represented as nodes in the graph, but they're semantically relationships between entities. This creates:
- Unnecessary intermediate nodes
- Extra traversals needed to query relationships
- Graph pattern that doesn't match NIEM's intent

Associations should be **edges** (relationships) with properties, not nodes.

## User Value

- **Intuitive graph model**: Associations are relationships, not entities
- **Simpler queries**: Direct edge traversal instead of node-edge-node
- **Better performance**: Fewer hops, native relationship properties
- **NIEM semantic accuracy**: Matches NIEM specification intent

## Current Behavior

```cypher
// Current: Association as node
(Person)-[:HAS_PERSONCHARGEASSOCIATION]->(PersonChargeAssociation)-[:HAS_CHARGE]->(Charge)

// Query requires two hops:
MATCH (p:Person)-[:HAS_PERSONCHARGEASSOCIATION]->(pca)-[:HAS_CHARGE]->(c:Charge)
RETURN p, pca, c
```

## Desired Behavior

```cypher
// Proposed: Association as enriched edge
(Person)-[:CHARGED_WITH {juvenileAsAdult: false, metadata: "JMD01"}]->(Charge)

// Query is direct:
MATCH (p:Person)-[rel:CHARGED_WITH]->(c:Charge)
RETURN p, rel, c
```

## Acceptance Criteria

- [ ] Association elements identified from `mapping.yaml` associations list
- [ ] Association nodes converted to edges during graph generation
- [ ] Edge type derived from association name (e.g., `PersonChargeAssociation` → `CHARGED_WITH`)
- [ ] Association properties stored as edge properties (not node properties)
- [ ] Reference relationships extracted (e.g., `nc:Person`, `j:Charge` refs)
- [ ] Edge direction determined from association semantics or configurable
- [ ] Both XML and JSON ingestion handle associations correctly
- [ ] Mapping format updated to support association metadata (cardinality, direction)
- [ ] Tests verify association edge creation and property storage
- [ ] Documentation explains association mapping syntax

## Technical Context

**Files to modify:**
- `api/src/niem_api/services/domain/xml_to_graph/converter.py`
  - Add association detection logic
  - Transform association traversal to edge creation
  - Extract reference elements as edge endpoints
- `api/src/niem_api/services/domain/json_to_graph/converter.py`
  - Similar association handling
- `api/src/niem_api/services/domain/schema/mapping.py`
  - Extend `mapping.yaml` format to include association metadata

**Current mapping.yaml structure:**
```yaml
associations:
  - owner: "j:PersonChargeAssociation"
    target: "j:Charge"
    ref_property: "j:Charge"
    edge_label: "CHARGED_WITH"
```

**Proposed enhancement:**
```yaml
associations:
  - owner: "j:PersonChargeAssociation"
    source_ref: "nc:Person"        # NEW: explicit source
    target_ref: "j:Charge"
    edge_label: "CHARGED_WITH"
    direction: "outgoing"          # NEW: edge direction
    properties:                     # NEW: properties to extract
      - "j:JuvenileAsAdultIndicator"
      - "nc:metadata"
```

**Association Detection Strategy:**
```python
def is_association(qname: str, mapping_associations: List[Dict]) -> Optional[Dict]:
    """Check if element is an association from mapping"""
    return next((a for a in mapping_associations if a['owner'] == qname), None)
```

## Implementation Notes

1. **Association Identification:**
   - Parse `mapping.yaml` associations list
   - During traversal, detect association elements
   - Extract reference elements (elements with `structures:uri` or explicit refs)

2. **Edge Creation Logic:**
   - Find source node (parent or referenced entity)
   - Find target node (referenced entity from association)
   - Create edge with properties from association element
   - Use edge label from mapping or derive from association name

3. **Property Extraction:**
   - Scalar properties on association → edge properties
   - Metadata references → edge properties
   - Complex properties → serialize as JSON or nested keys

4. **Edge Direction:**
   - Configurable in mapping (source → target)
   - Default: Derive from association name semantics
   - Example: `PersonChargeAssociation` → Person CHARGED_WITH Charge

5. **Backward Compatibility:**
   - Breaking change for existing graphs
   - Document migration strategy
   - Consider dual mode (nodes + edges) during transition

## Test Cases

```xml
<!-- Input: PersonChargeAssociation -->
<j:PersonChargeAssociation>
  <nc:metadata structures:uri="#JMD01"/>
  <nc:Person structures:uri="#P01"/>
  <j:Charge structures:uri="CH01"/>
  <j:JuvenileAsAdultIndicator>false</j:JuvenileAsAdultIndicator>
</j:PersonChargeAssociation>
```

```cypher
-- Expected Output:
MATCH (p:Person {id: 'file_P01'})
MATCH (c:Charge {id: 'file_CH01'})
CREATE (p)-[:CHARGED_WITH {
  juvenileAsAdult: false,
  metadata: 'file_JMD01'
}]->(c)
```

## Related Issues

- Depends on: #1 (augmentation flattening) - cleaner property extraction
- Blocks: #7 (data import wizard) - wizard should show associations as edges
- Related to: NIEM specification on associations

## Priority

**Medium** - Improves graph quality, but not critical for basic functionality

## Estimated Effort

**Extra Large (XL)** - ~16-24 hours
- Complex logic to extract refs and determine endpoints
- Mapping format changes
- Extensive testing for various association patterns
- Documentation and migration guide
- Both XML and JSON converters

## Additional Context

**NIEM Specification on Associations:**
> An association is a relationship between objects. It is not an object itself. Associations should be represented as relationships in graph models.

**Example NIEM Associations:**
- `j:PersonChargeAssociation` - Person charged with Crime
- `nc:PersonContactInformationAssociation` - Person has ContactInfo
- `j:CaseAugmentation` - (Not an association, but shows pattern)

**Neo4j Best Practice:**
- Use rich relationships with properties
- Avoid intermediate "relationship nodes"
- See: https://neo4j.com/developer/guide-data-modeling/

**Migration Considerations:**
- Existing graphs have association nodes
- Provide Cypher migration script
- Document in release notes as breaking change
- Consider versioning graph schema
