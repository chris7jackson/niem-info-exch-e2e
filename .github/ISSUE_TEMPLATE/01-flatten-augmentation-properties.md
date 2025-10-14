---
name: Flatten augmentation properties to parent nodes
about: Remove augmentation wrapper nodes and move properties to parents
title: 'Flatten augmentation properties to parent nodes in graph ingestion'
labels: enhancement, graph, refactor
assignees: ''
---

## Problem Statement

Currently, NIEM augmentation elements create separate nodes in the Neo4j graph, which adds unnecessary complexity and violates the principle that augmentations are not separate entities but extended properties of their parent elements.

For example:
```xml
<j:PersonAugmentation>
  <j:PersonAdultIndicator>true</j:PersonAdultIndicator>
</j:PersonAugmentation>
```

Creates a separate `PersonAugmentation` node instead of adding `PersonAdultIndicator` directly to the Person node.

## User Value

- **Simplified graph structure**: Fewer nodes, clearer relationships
- **Better queryability**: Properties accessible directly on parent nodes
- **NIEM semantic correctness**: Augmentations are extensions, not separate entities
- **Improved performance**: Fewer nodes and relationships to traverse

## Current Behavior

1. Augmentation elements create separate nodes with label based on element name
2. Properties within augmentations are stored on the augmentation node
3. Parent connects to augmentation via containment edge (e.g., `HAS_PERSONAUGMENTATION`)

## Desired Behavior

1. Augmentation elements do NOT create separate nodes
2. Properties within augmentations are flattened and added to parent node with appropriate prefixes
3. No containment edges for augmentation elements
4. Clear indication in property names that they came from augmentation (e.g., `aug_PersonAdultIndicator`)

## Acceptance Criteria

- [ ] XML ingestion: Augmentation properties are added to parent nodes
- [ ] JSON ingestion: Augmentation properties are added to parent nodes
- [ ] Property naming includes `aug_` prefix to indicate augmentation source
- [ ] No separate augmentation nodes created in Neo4j
- [ ] Complex nested augmentations are handled correctly (nested objects/arrays)
- [ ] Existing augmentation detection logic in `extract_unmapped_properties()` is updated
- [ ] Both simple text properties and complex structures are supported
- [ ] Graph queries for augmented properties work correctly
- [ ] Tests added for augmentation flattening logic

## Technical Context

**Files to modify:**
- `api/src/niem_api/services/domain/xml_to_graph/converter.py`
  - Function: `extract_unmapped_properties()` (lines 182-243)
  - Function: `handle_complex_augmentation()` (lines 132-180)
  - Function: `generate_for_xml_content()` (traversal logic)
- `api/src/niem_api/services/domain/json_to_graph/converter.py`
  - Similar augmentation handling for JSON-LD

**Current augmentation detection:**
```python
def is_augmentation(qname: str, cmf_element_index: Dict[str, Any]) -> bool:
    """Check if element is an augmentation (not mapped in CMF)"""
    return qname not in cmf_element_index
```

**References:**
- CMF element index (`cmf_element_index`) determines what's mapped vs augmentation
- Augmentation properties currently collected in `aug_props` dict
- See `_extract_all_properties_recursive()` for property extraction pattern

## Implementation Notes

1. **Property Flattening Strategy:**
   - Simple text values: Add directly to parent with `aug_` prefix
   - Complex structures: Serialize as JSON or create nested property keys
   - Arrays: Store as JSON array string or create multiple properties

2. **Backward Compatibility:**
   - Existing graphs will have old structure
   - Consider migration script or document breaking change

3. **Testing Strategy:**
   - Unit tests with sample XML/JSON containing augmentations
   - Integration test comparing old vs new graph structure
   - Use CrashDriver sample data (has PersonAugmentation)

## Related Issues

- Depends on: None
- Blocks: #3 (associations as enriched edges)
- Related to: #2 (root node and orphan prevention)

## Priority

**Medium** - Improves graph quality but not blocking core functionality

## Estimated Effort

**Large (L)** - ~8-16 hours
- Requires changes to both XML and JSON converters
- Complex logic for nested structures
- Extensive testing needed
- Potential migration considerations

## Additional Context

NIEM 6.0 Specification on Augmentations:
> Augmentations are a mechanism for adding content to pre-defined types. An augmentation is not a separate entity but additional properties on the augmented type.

Current graph structure violates this by creating separate nodes.
