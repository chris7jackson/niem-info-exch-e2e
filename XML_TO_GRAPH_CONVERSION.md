# XML to Graph Conversion Documentation

## Overview

This document explains how NIEM XML files are converted into a Neo4j graph database, creating nodes and relationships that preserve the structure and semantics of the XML while enabling graph-based querying and analysis.

## File-Scoped Entity Isolation

### Problem
When multiple XML files are uploaded, they may use the same `structures:id` values (e.g., `CH01`, `P01`). Without file isolation, these would collide in the graph database, merging entities from different files.

### Solution
Every node ID is prefixed with a unique **file-specific identifier**:

```python
# Generate 8-character hash from filename + timestamp
file_prefix = hashlib.sha1(f"{filename}_{time.time()}".encode()).hexdigest()[:8]

# Example: "abc12345"
```

**Effect**:
- `CrashDriver1.xml` with `structures:id="CH01"` → Node ID: `abc12345_CH01`
- `CrashDriver2.xml` with `structures:id="CH01"` → Node ID: `def67890_CH01`

This ensures complete isolation between files while maintaining referential integrity within each file.

## Node Creation

### Node ID Generation

Nodes are created from XML elements using three strategies:

#### 1. Explicit `structures:id`
When an element has a `structures:id` attribute, it becomes a node with that ID (prefixed):

```xml
<j:Charge structures:id="CH01">...</j:Charge>
```
→ Node ID: `{file_prefix}_CH01`, Label: `j_Charge`

#### 2. Referenced via `structures:uri`
Elements with `structures:uri` create a reference to an existing node:

```xml
<nc:RoleOfPerson structures:uri="#P01" />
```
→ Creates relationship to existing node `{file_prefix}_P01`

#### 3. Synthetic IDs
Elements without explicit IDs get a generated synthetic ID:

```python
def synth_id(parent_id: str, elem_qn: str, ordinal_path: str, file_prefix: str) -> str:
    basis = f"{parent_id}|{elem_qn}|{ordinal_path}"
    synth = "syn_" + hashlib.sha1(basis.encode()).hexdigest()[:16]
    return f"{file_prefix}_{synth}"
```

**Example**: `abc12345_syn_11d60c25b66b1fcc`

### Node Labels

Node labels are derived from the XML qualified name (qname) with colon replaced by underscore:

```xml
<j:Charge> → Label: j_Charge
<nc:Person> → Label: nc_Person
<priv:PrivacyMetadata> → Label: priv_PrivacyMetadata
```

### Node Properties

Each node stores:
- `id`: Unique identifier (with file prefix)
- `qname`: Original XML qualified name (e.g., `j:Charge`)
- `sourceDoc`: Originating filename
- Additional scalar properties from mapping configuration

## Relationship Creation

The system creates three types of relationships:

### 1. Containment Relationships (Structural Hierarchy)

**Purpose**: Represent the parent-child structure of the XML document.

**Pattern**: `Parent --[HAS_CHILDNAME]--> Child`

**Naming Convention**:
```python
rel = "HAS_" + re.sub(r'[^A-Za-z0-9]', '_', local_from_qname(elem_qn)).upper()
```

**Examples**:
```xml
<exch:CrashDriverInfo>
  <j:Charge structures:id="CH01">...</j:Charge>
  <nc:Metadata structures:id="JMD01">...</nc:Metadata>
  <priv:PrivacyMetadata structures:id="PMD01">...</priv:PrivacyMetadata>
</exch:CrashDriverInfo>
```

Creates relationships:
- `exch:CrashDriverInfo --[HAS_CHARGE]--> j:Charge`
- `exch:CrashDriverInfo --[HAS_METADATA]--> nc:Metadata`
- `exch:CrashDriverInfo --[HAS_PRIVACYMETADATA]--> priv:PrivacyMetadata`

**Key Point**: Containment edges capture the XML tree structure. The relationship name indicates the type of child element.

### 2. Reference Relationships (Cross-References)

**Purpose**: Link elements that reference other elements by ID, even when they're not parent-child.

**Pattern for `xsi:nil` + `structures:ref`**:

```xml
<j:PersonChargeAssociation>
  <j:Person structures:ref="P01" xsi:nil="true" />
  <j:Charge structures:ref="CH01" xsi:nil="true" />
</j:PersonChargeAssociation>
```

Creates containment relationships (NOT new nodes):
- `j:PersonChargeAssociation --[HAS_PERSON]--> {file_prefix}_P01`
- `j:PersonChargeAssociation --[HAS_CHARGE]--> {file_prefix}_CH01`

**Important**: When `xsi:nil="true"` + `structures:ref` are both present, NO new node is created. Instead, a containment relationship points to the existing referenced node.

### 3. Semantic Relationships (Role-Based Associations)

**Purpose**: Express NIEM role-based patterns where a role element represents a person.

**Pattern**: `Role --[REPRESENTS_PERSON]--> Person`

**Example**:
```xml
<j:CrashDriver structures:uri="#P01">
  <!-- Driver role properties -->
</j:CrashDriver>

<nc:Person structures:id="P01">
  <!-- Person details -->
</nc:Person>
```

Creates:
- Node: `j:CrashDriver` (the role)
- Node: `nc:Person` (the person)
- Edge: `j:CrashDriver --[REPRESENTS_PERSON]--> nc:Person`

This pattern allows roles (Driver, Victim, Witness) to have role-specific properties while sharing the same underlying Person entity.

## Metadata Handling

### NIEM Metadata Pattern

NIEM uses `nc:metadataRef` and `priv:privacyMetadataRef` attributes to link elements to metadata:

```xml
<j:Charge structures:id="CH01" nc:metadataRef="JMD01">...</j:Charge>
<nc:Metadata structures:id="JMD01">...</nc:Metadata>
```

### Current Implementation

**Metadata reference attributes are detected but NOT converted to separate edges.**

**Rationale**: The containment relationship already captures the metadata association:
- `Parent --[HAS_METADATA]--> nc:Metadata` (structural containment)

Creating additional metadata reference edges would be redundant:
- ❌ `j:Charge --[HAS_METADATA]--> nc:Metadata` (redundant)

### Future Consideration

If metadata nodes exist elsewhere in the tree (not as direct children), metadata reference edges could be created for cross-referencing. Currently, the containment structure is sufficient.

## Cypher Generation

The conversion process generates Cypher statements in this order:

### 1. Node Creation
```cypher
MERGE (n:`j_Charge` {id:'abc12345_CH01'})
  ON CREATE SET n.qname='j:Charge', n.sourceDoc='CrashDriver1.xml';
```

### 2. Containment Edges
```cypher
MATCH (p:`exch_CrashDriverInfo` {id:'abc12345_syn_11d60c25b66b1fcc'}),
      (c:`j_Charge` {id:'abc12345_CH01'})
MERGE (p)-[:HAS_CHARGE]->(c);
```

### 3. Reference/Association Edges
```cypher
MATCH (a:`j_CrashDriver` {id:'abc12345_syn_aaa46226424de2e7'}),
      (b:`nc_Person` {id:'abc12345_P01'})
MERGE (a)-[:REPRESENTS_PERSON]->(b);
```

## Edge Cases and Special Handling

### 1. Reference Elements with `xsi:nil="true"`

When an element has both `structures:ref` (or `structures:uri`) AND `xsi:nil="true"`:

```xml
<nc:Person structures:ref="P01" xsi:nil="true" />
```

**Behavior**:
- ✅ Create containment relationship to referenced node
- ❌ Do NOT create a new node
- Effect: Links to existing node without duplication

### 2. Association Elements

NIEM associations can act as both edges and nodes:

```xml
<j:PersonChargeAssociation structures:id="PCA01" nc:metadataRef="JMD01">
  <j:Person structures:ref="P01" xsi:nil="true" />
  <j:Charge structures:ref="CH01" xsi:nil="true" />
</j:PersonChargeAssociation>
```

**Creates**:
1. **Node**: `j:PersonChargeAssociation` (because it has `structures:id` and metadata refs)
2. **Containment edges**:
   - `Parent --[HAS_PERSONCHARGEASSOCIATION]--> j:PersonChargeAssociation`
   - `j:PersonChargeAssociation --[HAS_PERSON]--> nc:Person`
   - `j:PersonChargeAssociation --[HAS_CHARGE]--> j:Charge`

This allows associations to have their own properties and metadata while connecting other entities.

### 3. Root Element Skipping

The root wrapper element (e.g., `<exch:CrashDriverInfo>`) is typically a container without semantic meaning.

**Behavior**:
- If root has NO `structures:id` and is NOT in the mapping → Skip it, process children directly
- If root has `structures:id` or IS mapped → Create it as a node

This prevents redundant wrapper nodes in the graph.

## Relationship Type Naming Rules

### Containment: `HAS_{LOCALNAME}`

Format: `HAS_` + uppercase local name with non-alphanumeric characters replaced by underscores

Examples:
- `j:Charge` → `HAS_CHARGE`
- `nc:Person` → `HAS_PERSON`
- `priv:PrivacyMetadata` → `HAS_PRIVACYMETADATA`
- `j:CrashPersonInjury` → `HAS_CRASHPERSONINJURY`

### Semantic: Fixed Names

- `REPRESENTS_PERSON` - Role to person relationship
- (Other semantic relationships defined by mapping)

### ❌ Incorrect Pattern (Avoided)

Do NOT use full qualified names as relationship types:
- ❌ `J_CHARGE` (this is a node label, not a relationship type)
- ❌ `NC_METADATA` (this is a node label, not a relationship type)

## Example: Complete Conversion

### Input XML
```xml
<exch:CrashDriverInfo xmlns:exch="http://example.com/CrashDriver/1.2/"
                       xmlns:j="http://release.niem.gov/niem/domains/jxdm/6.2/"
                       xmlns:nc="http://release.niem.gov/niem/niem-core/4.0/">
  <j:Charge structures:id="CH01" nc:metadataRef="JMD01">
    <j:ChargeDescriptionText>Speeding</j:ChargeDescriptionText>
  </j:Charge>

  <j:PersonChargeAssociation structures:id="PCA01">
    <j:Person structures:ref="P01" xsi:nil="true" />
    <j:Charge structures:ref="CH01" xsi:nil="true" />
  </j:PersonChargeAssociation>

  <j:CrashDriver structures:uri="#P01">
    <j:DriverLicense>
      <j:DriverLicenseCardIdentification>
        <nc:IdentificationID>DL12345</nc:IdentificationID>
      </j:DriverLicenseCardIdentification>
    </j:DriverLicense>
  </j:CrashDriver>

  <nc:Person structures:id="P01">
    <nc:PersonName>
      <nc:PersonFullName>John Doe</nc:PersonFullName>
    </nc:PersonName>
  </nc:Person>

  <nc:Metadata structures:id="JMD01">
    <nc:ReportingOrganizationText>Police Dept</nc:ReportingOrganizationText>
  </nc:Metadata>
</exch:CrashDriverInfo>
```

### Output Graph (with `file_prefix = "abc12345"`)

**Nodes**:
1. `abc12345_syn_11d60c25b66b1fcc` - `exch_CrashDriverInfo`
2. `abc12345_CH01` - `j_Charge`
3. `abc12345_PCA01` - `j_PersonChargeAssociation`
4. `abc12345_syn_aaa46226424de2e7` - `j_CrashDriver`
5. `abc12345_P01` - `nc_Person`
6. `abc12345_JMD01` - `nc_Metadata`
7. `abc12345_syn_xxx...` - `j_DriverLicense`
8. `abc12345_syn_yyy...` - `j_DriverLicenseCardIdentification`
9. `abc12345_syn_zzz...` - `nc_PersonName`

**Relationships**:

Containment (structural):
- `exch:CrashDriverInfo --[HAS_CHARGE]--> j:Charge`
- `exch:CrashDriverInfo --[HAS_PERSONCHARGEASSOCIATION]--> j:PersonChargeAssociation`
- `exch:CrashDriverInfo --[HAS_CRASHDRIVER]--> j:CrashDriver`
- `exch:CrashDriverInfo --[HAS_PERSON]--> nc:Person`
- `exch:CrashDriverInfo --[HAS_METADATA]--> nc:Metadata`
- `j:PersonChargeAssociation --[HAS_PERSON]--> nc:Person` (reference)
- `j:PersonChargeAssociation --[HAS_CHARGE]--> j:Charge` (reference)
- `j:CrashDriver --[HAS_DRIVERLICENSE]--> j:DriverLicense`
- `j:DriverLicense --[HAS_DRIVERLICENSECARDIDENTIFICATION]--> j:DriverLicenseCardIdentification`
- `nc:Person --[HAS_PERSONNAME]--> nc:PersonName`

Semantic (role-based):
- `j:CrashDriver --[REPRESENTS_PERSON]--> nc:Person`

## Graph Query Examples

### Find all charges and their metadata
```cypher
MATCH (charge:j_Charge)-[:HAS_METADATA]->(metadata:nc_Metadata)
RETURN charge, metadata
```

### Find person roles and the person they represent
```cypher
MATCH (role)-[:REPRESENTS_PERSON]->(person:nc_Person)
RETURN role, person
```

### Find all entities from a specific file
```cypher
MATCH (n)
WHERE n.sourceDoc = 'CrashDriver1.xml'
RETURN n
```

### Traverse from crash driver to their charges
```cypher
MATCH path = (driver:j_CrashDriver)-[:REPRESENTS_PERSON]->(:nc_Person)
             <-[:HAS_PERSON]-(:j_PersonChargeAssociation)
             -[:HAS_CHARGE]->(charge:j_Charge)
RETURN path
```

## Configuration: Mapping YAML

The conversion can be customized via a mapping YAML file:

```yaml
namespaces:
  j: http://release.niem.gov/niem/domains/jxdm/6.2/
  nc: http://release.niem.gov/niem/niem-core/4.0/
  exch: http://example.com/CrashDriver/1.2/

objects:
  - qname: exch:CrashDriverInfo
    label: exch_CrashDriverInfo
    carries_structures_id: true
    scalar_props:
      - key: description
        path: nc:Description

associations:
  - qname: j:PersonChargeAssociation
    rel_type: CHARGED_WITH
    endpoints:
      - role_qname: j:Person
        maps_to_label: nc_Person
      - role_qname: j:Charge
        maps_to_label: j_Charge

references:
  - owner_object: j:CrashDriver
    field_qname: nc:RoleOfPerson
    target_label: nc_Person
    rel_type: REPRESENTS_PERSON
```

**Note**: Currently, the mapping is minimal. Most conversion is done dynamically based on XML structure.

## Design Principles

1. **File Isolation**: Every file's entities are completely separate
2. **Structure Preservation**: XML hierarchy → containment edges
3. **Semantic Enhancement**: NIEM patterns → meaningful relationships
4. **No Redundancy**: Avoid duplicate edges for the same relationship
5. **Label Clarity**: Relationship names indicate their purpose
6. **Queryability**: Graph structure enables powerful traversals

## Future Enhancements

1. **Mapping-Driven Conversion**: Use mapping to define custom node/edge types
2. **Cross-File References**: Optionally merge entities across files by business keys
3. **Metadata Relationships**: Create metadata reference edges for cross-tree references
4. **Property Extraction**: More sophisticated property mapping from XML to graph
5. **Validation**: Ensure graph structure matches NIEM conformance rules
