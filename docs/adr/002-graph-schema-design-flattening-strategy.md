# ADR-002: Graph Schema Design Flattening Strategy

## Status
Accepted

## Context

The NIEM Information Exchange system automatically converts XSD schemas to Neo4j graph schemas via the CMF (Common Model Format) intermediate representation. However, NIEM XML/JSON schemas are highly nested and hierarchical, often containing:

- **Deep nesting**: Element hierarchies 5-10 levels deep (e.g., `Person → PersonName → PersonGivenName → PersonNamePrefixText`)
- **Wrapper elements**: Structural containers with single scalar properties
- **Contextual associations**: Associations nested within entities that represent internal structure rather than top-level relationships
- **Verbose property paths**: Complex XPath-like paths (`nc:PersonName/nc:PersonGivenName`) that become unwieldy Neo4j properties

**Problem for Analytics Use Cases:**

Direct 1:1 conversion of nested XSD structures to Neo4j results in:
- Over-normalized graph schemas with excessive relationship hops
- Poor query performance (5+ relationship traversals for simple property access)
- Unclear entity boundaries (what is a "real" entity vs. structural grouping?)
- Difficult pattern matching and graph algorithms
- Sparse connectivity with many single-relationship nodes

**Example Problem:**
```xml
<j:CrashDriver>
  <nc:RoleOfPerson>
    <nc:Person>
      <nc:PersonName>
        <nc:PersonGivenName>John</nc:PersonGivenName>
        <nc:PersonSurName>Doe</nc:PersonSurName>
      </nc:PersonName>
      <nc:PersonBirthDate>1990-01-01</nc:PersonBirthDate>
    </nc:Person>
  </nc:RoleOfPerson>
</j:CrashDriver>
```

**Current auto-generated mapping creates 5 nodes:**
- `j:CrashDriver` → `nc:RoleOfPerson` → `nc:Person` → `nc:PersonName` → scalars

**Desired for analytics: 1-2 nodes:**
- `j:CrashDriver` with flattened properties: `person_given_name`, `person_surname`, `person_birth_date`
- OR `j:CrashDriver` → `nc:Person` (if Person is reusable entity)

**User Need:**

Users performing analytics on NIEM data need the ability to:
1. Select which XSD elements become Neo4j nodes (entities of analytical interest)
2. Flatten unselected elements as properties on selected nodes
3. Preserve critical relationships between analytically-relevant entities
4. Balance normalization (reusable entities) vs. denormalization (query performance)

## Decision

Implement an **optional graph schema designer UI** that allows users to refine the auto-generated mapping by selecting which XSD elements become Neo4j nodes. Unselected elements are **flattened into their nearest selected ancestor** as scalar properties.

### Core Principles

**1. Flattening Strategy**

- **Selected nodes** → Create Neo4j nodes with labels
- **Unselected nodes** → Flatten as properties on nearest selected ancestor
- **Property path generation**: Concatenate nested paths (e.g., `nc:Person/nc:PersonName/nc:PersonGivenName` → `nc_person_name_given_name`)

**2. Reference Handling (Binary Relationships)**

| Scenario | Action | Rationale |
|----------|--------|-----------|
| Source selected, target selected | Create Neo4j relationship | Standard graph edge |
| Source selected, target NOT selected | Flatten target data as properties on source | Target is contextual data, not independent entity |
| Source NOT selected, target selected | Allow (target may be orphaned) | Analytics often query specific entity types independently. Show warning. |

**Example:**
```yaml
# j:CrashDriver selected, nc:Person NOT selected
# Reference: j:CrashDriver → nc:Person (unselected)

# Result: Flatten Person data into CrashDriver
objects:
  - qname: "j:CrashDriver"
    label: "j_CrashDriver"
    scalar_props:
      - neo4j_property: "nc_person_given_name"  # Flattened from nc:Person
      - neo4j_property: "nc_person_surname"
      - neo4j_property: "nc_person_birth_date"
```

**3. Association Handling (N-ary Relationships)**

Associations are handled differently based on **context**:

**Scenario A: Nested Association**
- Association is nested under a selected node
- **Action**: Flatten association data as properties on the parent node
- **Rationale**: Nested associations represent internal structure, not top-level relationships

```xml
<j:Crash>
  <j:CrashVehicleAssociation>  <!-- NESTED -->
    <j:CrashVehicle>ABC123</j:CrashVehicle>
    <nc:RoleOfPerson>Driver1</nc:RoleOfPerson>
  </j:CrashVehicleAssociation>
</j:Crash>
```
→ Flatten: `j:Crash.crash_vehicle_id = "ABC123"`, `j:Crash.role_of_person = "Driver1"`

**Scenario B: Top-Level Association**
- Association is a sibling to major entities (not nested)
- **Action depends on selected endpoints**:

| Selected Endpoints | Action | Example |
|--------------------|--------|---------|
| 3+ endpoints | Create n-ary association node | `Crash-[IN_ASSOC]→Association←[IN_ASSOC]-Vehicle` |
| 2 endpoints | Create n-ary association OR offer binary reference option | `Crash-[HAS_VEHICLE]→Vehicle` (user choice) |
| 1 endpoint | Flatten association data into that endpoint | `Crash.vehicle_id, Crash.driver_name` |
| 0 endpoints | Omit entirely | Not relevant to selected schema |

**Example:**
```yaml
# Top-level j:CrashVehicleAssociation with 3 selected endpoints
associations:
  - qname: "j:CrashVehicleAssociation"
    rel_type: "J_CRASH_VEHICLE_ASSOCIATION"
    endpoints:
      - role_qname: "j:Crash"
        maps_to_label: "j_Crash"
        direction: "source"
      - role_qname: "j:CrashVehicle"
        maps_to_label: "j_CrashVehicle"
        direction: "source"
      - role_qname: "j:CrashDriver"
        maps_to_label: "j_CrashDriver"
        direction: "source"
```

**Mixed Endpoints (some selected, some not)**:
- If 2+ endpoints selected: Create association with selected endpoints
- Flatten unselected endpoint data as properties on the association node
- Show warning: "Association missing endpoint X (will be flattened as properties)"

**4. Orphaned Target Nodes Policy**

**Decision**: Allow target nodes to exist even if source nodes are unselected (with warning)

**Rationale for Analytics**:
- Analytics queries often focus on specific entity types independently
- Example: Analyze all `Person` demographics without parent `Crash` context
- Example: Query all `Vehicle` nodes for fleet analysis
- Requiring all sources creates unnecessary complexity and storage overhead

**Warning Message**: "Node X may have sparse connectivity - some references point here from unselected nodes"

**5. UI Integration**

- **Location**: Modal/panel shown after successful XSD upload in SchemaManager
- **Trigger**: Optional refinement step (users can skip and use auto-generated mapping)
- **Controls**:
  - Skip button → Use auto-generated mapping
  - Apply Design button → Regenerate mapping.yaml with selections

### Best Practice Detection & Warnings

The UI will provide intelligent suggestions:

**1. Deep Nesting Warning (>3 levels)**
- **Detection**: Element depth > 3 from root
- **Warning**: "Consider selecting intermediate nodes to reduce property path complexity"
- **Icon**: ⚠️ Yellow warning

**2. Association Candidate Highlighting**
- **Detection**:
  - Element name contains "Association" OR
  - Element has 2+ role references
- **Highlight**: 🔗 Badge "Potential n-ary relationship"
- **Suggestion**: "May be better as relationship node if endpoints are selected"

**3. Sparse Connectivity Warning**
- **Detection**: Selected node is target of references from unselected sources
- **Warning**: "This node may have sparse connectivity. Some incoming references are from unselected nodes."
- **Icon**: 🔴 Red warning

**4. Insufficient Association Endpoints**
- **Detection**: Top-level association with <2 selected endpoints
- **Warning**: "Association requires at least 2 selected endpoints to create relationship"
- **Action**: Association will be flattened if user proceeds

### Implementation Pattern

**Backend Service (`services/domain/schema/element_tree.py`)**:
```python
class ElementTreeNode:
    qname: str                      # e.g., "j:CrashDriver"
    label: str                      # Neo4j label "j_CrashDriver"
    node_type: str                  # "object", "association", or "reference"
    depth: int                      # Distance from root
    property_count: int             # Number of scalar properties
    relationship_count: int         # Number of references/endpoints
    parent_qname: Optional[str]     # Parent in hierarchy
    children: List[ElementTreeNode] # Child elements
    warnings: List[str]             # ["deep_nesting", "sparse_connectivity"]
    suggestions: List[str]          # ["association_candidate"]
    selected: bool                  # User selection state

def build_element_tree(cmf: str) -> ElementTreeNode:
    """Parse CMF XML into hierarchical tree with metadata"""
    # Parse CMF XML
    # Calculate depth, counts, detect patterns
    # Apply best practice detection
    # Pre-populate selections from auto-generated mapping
    # Return root node
```

**Backend Flattening Logic (`services/domain/schema/mapping.py`)**:
```python
def apply_schema_design(
    cmf: str,
    selections: Dict[str, bool]  # {qname: selected}
) -> str:  # Returns mapping.yaml
    """Apply user selections and regenerate mapping"""

    # 1. Parse CMF
    # 2. Identify selected nodes → create in objects/associations
    # 3. For unselected nodes:
    #    - Find nearest selected ancestor
    #    - Flatten properties: concatenate paths
    # 4. Handle references:
    #    - Both selected: create reference
    #    - Target unselected: flatten target properties into source
    # 5. Handle associations:
    #    - Check if nested or top-level
    #    - Count selected endpoints
    #    - Apply rules from decision matrix
    # 6. Generate mapping.yaml
```

**Frontend Component (`components/GraphSchemaDesigner.tsx`)**:
```typescript
interface GraphSchemaDesignerProps {
  schemaId: string;
  onComplete: () => void;  // Continue to activation
  onSkip: () => void;      // Use auto-generated mapping
}

// Layout:
// +------------------+------------------+
// | Tree View        | Node Inspector   |
// | (checkboxes)     | (properties)     |
// +------------------+------------------+
// |  [Skip] [Apply Design]              |
// +-------------------------------------+
```

### Data Flow

1. User uploads XSD files via SchemaManager
2. System validates, converts to CMF, auto-generates mapping.yaml
3. **NEW**: System shows GraphSchemaDesigner modal
4. **NEW**: User reviews tree, selects nodes, sees warnings
5. **NEW**: User clicks "Apply Design" or "Skip"
   - Skip → Continue with auto-generated mapping
   - Apply → Regenerate mapping.yaml with selections
6. User activates schema (existing flow)
7. User ingests data using the mapping (existing flow)

## Consequences

### Positive

✅ **Performance Optimization**: Flattening reduces relationship hops (5+ hops → 0-2 hops), dramatically improving query performance

✅ **Clearer Entity Boundaries**: Users explicitly define what constitutes an analytically-relevant entity vs. supporting data

✅ **Flexibility**: Optional refinement step allows quick start (auto-generated) or optimized schema (custom design)

✅ **Analytics-Friendly**: Denormalized structure better suited for graph algorithms (centrality, community detection, path finding)

✅ **Preserves Relationships**: Critical entity-to-entity relationships maintained while flattening contextual data

✅ **Progressive Disclosure**: Auto-generated mapping works out-of-box; designer available when optimization needed

✅ **Best Practice Guidance**: Warnings and suggestions help users make informed schema design decisions

### Negative

❌ **Learning Curve**: Users need to understand graph schema design principles (node selection, flattening implications)

❌ **Mapping Complexity**: Generated mapping.yaml becomes more complex with custom property paths

❌ **Data Duplication**: Flattening can duplicate data if the same unselected element appears in multiple contexts

❌ **Irreversible Flattening**: Once data ingested with flattened schema, structural information is lost (cannot reconstruct original hierarchy)

### Mitigation Strategies

- **Learning Curve**: Provide inline help, tooltips, warnings with explanations
- **Mapping Complexity**: Designer generates mapping automatically; users don't write YAML
- **Data Duplication**: Acceptable trade-off for analytics performance; storage is cheap
- **Irreversible Flattening**: Keep original XML/JSON instances in MinIO for audit/reconstruction if needed

## Alternatives Considered

### Alternative 1: Always Flatten Everything (No Selection)

**Approach**: Automatically flatten all nested elements beyond depth 1

**Pros**:
- Simplest implementation
- Maximum query performance
- No user decisions needed

**Cons**:
- Loses all relationships between entities
- Creates monolithic node types (Crash with 100+ properties)
- Cannot represent shared entities (Person in multiple contexts)

**Verdict**: ❌ Rejected - Too rigid, loses graph structure benefits

### Alternative 2: Explicit Flattening Rules in Configuration

**Approach**: Define flattening rules in YAML config file

```yaml
flattening_rules:
  - element: "nc:PersonName"
    action: "flatten"
  - element: "j:CrashDriver"
    action: "create_node"
```

**Pros**:
- Version controlled, repeatable
- Programmatic application

**Cons**:
- Requires understanding YAML rule syntax
- No visual feedback of impact
- Difficult to see hierarchical relationships
- Error-prone for complex schemas

**Verdict**: ❌ Rejected - Harder to use than visual designer, but could be future enhancement for automation

### Alternative 3: Post-Ingestion Schema Refactoring

**Approach**: Ingest with 1:1 mapping, then refactor graph using Cypher queries

**Pros**:
- Preserves original structure initially
- Can experiment with different flattening strategies

**Cons**:
- Requires writing complex Cypher refactoring queries
- Two-step process (ingest → refactor)
- Data migration complexity
- Performance overhead of refactoring large graphs

**Verdict**: ❌ Rejected - More complex than pre-ingestion design, but pattern could be used for schema evolution

## References

- [Neo4j Data Modeling Guidelines](https://neo4j.com/developer/guide-data-modeling/)
- [Graph Schema Design Best Practices](https://neo4j.com/docs/getting-started/data-modeling/guide-data-modeling/)
- NIEM Naming and Design Rules (NDR) Specification
- Existing entity resolution UI pattern: `ui/src/components/EntityResolutionPanel.tsx`
- CMF mapping generation: `api/src/niem_api/services/domain/schema/mapping.py`

## Related Decisions

- ADR-001: Batch Processing Architecture - Designer integrates into existing schema upload flow
- Future ADR: Schema versioning and migration strategy for evolving mappings
