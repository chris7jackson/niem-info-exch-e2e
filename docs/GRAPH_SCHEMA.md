# Neo4j Graph Schema Documentation

## Table of Contents

- [Overview](#overview)
- [Node Types](#node-types)
- [Relationship Types](#relationship-types)
- [Property Patterns](#property-patterns)
- [Graph Structure Patterns](#graph-structure-patterns)
- [Example: CrashDriver Graph](#example-crashdriver-graph)
- [Common Query Patterns](#common-query-patterns)
- [Schema Design Decisions](#schema-design-decisions)

## Overview

The Neo4j graph schema represents **NIEM (National Information Exchange Model) documents as semantic property graphs**. The schema preserves complete document structure while enabling flexible semantic queries across interconnected entities.

### Design Goals

1. **Complete Fidelity**: No data loss from XML/JSON source
2. **Semantic Richness**: Meaningful relationships beyond document structure
3. **Provenance Tracking**: Know exactly where each piece of data came from
4. **Multi-File Support**: Isolated graphs per file/upload/schema
5. **Extension Support**: Handle custom namespaces and augmentations
6. **Entity Resolution**: Link duplicate entities across documents

## Node Types

### Entity Relationship Diagram (Conceptual View)

```
┌──────────────────────────────────────────────────────────────────────┐
│                         Core Entity Layer                             │
│                                                                       │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐          │
│  │  nc_Person   │    │nc_Organization│   │ nc_Location  │          │
│  │              │    │              │    │              │          │
│  │ Properties:  │    │ Properties:  │    │ Properties:  │          │
│  │ - GivenName  │    │ - OrgName    │    │ - Address    │          │
│  │ - SurName    │    │ - OrgID      │    │ - Lat/Lon    │          │
│  │ - BirthDate  │    │              │    │              │          │
│  │ - SSN        │    │              │    │              │          │
│  └──────┬───────┘    └──────────────┘    └──────────────┘          │
│         │                                                            │
│         │ REPRESENTS                                                │
│         │                                                            │
└─────────┼────────────────────────────────────────────────────────────┘
          │
┌─────────┼────────────────────────────────────────────────────────────┐
│         │                 Role Layer                                 │
│         │                                                            │
│  ┌──────▼───────┐    ┌──────────────┐    ┌──────────────┐          │
│  │j_CrashDriver │    │j_CrashPerson │    │  j_Victim    │          │
│  │              │    │              │    │              │          │
│  │ Properties:  │    │ Properties:  │    │ Properties:  │          │
│  │ - uri: #P01  │    │ - uri: #P01  │    │ - uri: #P01  │          │
│  │ - PersonName │    │ - PersonName │    │ - PersonName │          │
│  └──────────────┘    └──────────────┘    └──────────────┘          │
│         │                    │                                       │
└─────────┼────────────────────┼───────────────────────────────────────┘
          │                    │
┌─────────┼────────────────────┼───────────────────────────────────────┐
│         │   HAS_CRASHDRIVER  │  HAS_CRASHPERSON                      │
│         │                    │                                       │
│  ┌──────▼────────┐    ┌──────▼──────┐       ┌──────────────┐       │
│  │j_CrashVehicle │    │  j_Crash    │       │  j_Charge    │       │
│  │              │    │              │       │              │       │
│  └──────────────┘    └──────────────┘       └──────────────┘       │
│                             │                       │               │
│                             │  HAS_CRASHVEHICLE     │               │
│                             │                       │               │
└─────────────────────────────┼───────────────────────┼───────────────┘
                              │                       │
┌─────────────────────────────┼───────────────────────┼───────────────┐
│                             │                       │               │
│            Association Layer (Hypergraph Pattern)   │               │
│                                                     │               │
│                  ┌──────────────────────────┐       │               │
│                  │j_PersonChargeAssociation │       │               │
│                  │        (Orange)          │       │               │
│                  │ Properties:              │       │               │
│                  │ - _isAssociation: true   │       │               │
│                  └────┬───────────────┬─────┘       │               │
│                       │               │             │               │
│              ASSOCIATED_WITH   ASSOCIATED_WITH      │               │
│              {role: Person}    {role: Charge}       │               │
│                       │               │             │               │
│                  nc_Person ──────────┘──────────────┘               │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────┐
│                    Entity Resolution Layer                            │
│                                                                       │
│  ┌──────────────┐           ┌──────────────┐                        │
│  │  nc_Person   │           │  nc_Person   │                        │
│  │ (from file1) │           │ (from file2) │                        │
│  └──────┬───────┘           └──────┬───────┘                        │
│         │                          │                                │
│         └──────RESOLVED_TO─────────┘                                │
│         {confidence: 0.95}  {confidence: 0.95}                      │
│                     │                                                │
│               ┌─────▼──────┐                                        │
│               │ResolvedEntity│                                       │
│               │  (Magenta)   │                                       │
│               │ entity_id    │                                       │
│               │ name         │                                       │
│               │ resolved_count│                                      │
│               └──────────────┘                                       │
└──────────────────────────────────────────────────────────────────────┘
```

### NIEM Object Nodes

**Purpose**: Represent NIEM complex elements as graph nodes

**Node Label Pattern**: `{namespace}_{elementName}` (e.g., `nc_Person`, `j_Crash`)

**Common Core Nodes (nc: namespace)**:
- `nc_Person` - Person entities
- `nc_Organization` - Organization entities
- `nc_Location` - Location/address entities
- `nc_Vehicle` - Vehicle entities
- `nc_PersonName` - Name structures (if selected in schema designer)
- `nc_ActivityDate` - Date structures
- `nc_Metadata` - NIEM metadata containers

**Justice Domain Nodes (j: namespace)**:
- `j_Crash` - Traffic crash events
- `j_CrashDriver` - Driver role in crash
- `j_CrashPerson` - Person role in crash (e.g., injured party)
- `j_CrashVehicle` - Vehicle involved in crash
- `j_Charge` - Criminal charges
- `j_DriverLicense` - License information
- `j_DriverLicenseCardIdentification` - License ID card details
- `j_CrashPersonInjury` - Injury information

**Child Welfare Domain Nodes (cyfs: namespace)**:
- `cyfs_Child` - Child entities
- `cyfs_Parent` - Parent entities
- `cb_exchange_NEICETransmittalDocument` - Exchange root document
- `cb_ext_FollowupReport` - Follow-up report structures

**Association Nodes** (represent n-ary relationships):
- `j_PersonChargeAssociation` - Links person to charge with properties
- Any element ending in "Association"
- Marked with `_isAssociation: true` property

### Entity Resolution Nodes

**`ResolvedEntity`** - Duplicate entity clusters

**Purpose**: Group duplicate entities detected by Senzing SDK or text-based matching

**Key Properties**:
- `entity_id` - Unique cluster identifier (e.g., "RE_abc123")
- `name` - Representative name for cluster
- `birth_date` - Birth date (if available)
- `resolved_count` - Number of entities in cluster
- `resolved_at` - Resolution timestamp (ISO 8601)
- `resolution_method` - "senzing" or "text_based"
- `confidence` - Overall match confidence (0.0-1.0)
- `senzing_entity_id` - Senzing entity ID (if Senzing used)
- `_upload_ids` - Array of upload batch IDs (for multi-tenant support)
- `_schema_ids` - Array of schema IDs (for multi-tenant support)
- `sourceDocs` - Array of source filenames

## Relationship Types

### Containment Relationships (Document Structure)

**Pattern**: `HAS_{ELEMENT_NAME}`

**Purpose**: Preserve parent-child hierarchical structure from XML/JSON documents

**Color**: Gray, Solid line

**Examples**:
```cypher
(j_Crash)-[:HAS_CRASHVEHICLE]->(j_CrashVehicle)
(j_CrashVehicle)-[:HAS_CRASHDRIVER]->(j_CrashDriver)
(nc_Person)-[:HAS_PERSONNAME]->(nc_PersonName)
(j_CrashDriver)-[:HAS_DRIVERLICENSE]->(j_DriverLicense)
(j_CrashPerson)-[:HAS_CRASHPERSONINJURY]->(j_CrashPersonInjury)
(injury)-[:HAS_PRIVACYMETADATA]->(priv_PrivacyMetadata)
(charge)-[:HAS_METADATA]->(nc_Metadata)
```

**Generation**: Automatically created for all parent-child relationships during ingestion

### Reference Relationships (Domain Semantics)

**Pattern**: Named from the reference field in mapping.yaml (often uppercase)

**Purpose**: Express semantic object-to-object relationships beyond containment

**Color**: Green, Solid line

**Examples**:
```cypher
(j_CrashVehicle)-[:J_CRASHDRIVER]->(j_CrashDriver)
(j_DriverLicense)-[:J_DRIVERLICENSECARDIDENTIFICATION]->(j_DriverLicenseCardIdentification)
```

**Generation**: Created from `references[]` section of mapping.yaml

**Difference from Containment**:
- Containment: "This vehicle HAS a driver element in the document"
- Reference: "This vehicle's driver IS this specific driver entity"

### Association Relationships (Hypergraph Pattern)

**`ASSOCIATED_WITH`** - Generic association edge

**Purpose**: Connect association nodes to their endpoint entities

**Color**: Orange, Thick dotted line

**Edge Properties**:
- `role_qname` - QName of the role element (e.g., "nc:Person", "j:Charge")
- `direction` - "source" or "target" (optional)

**Pattern**:
```cypher
(AssociationNode)-[:ASSOCIATED_WITH {role_qname: "nc:Person"}]->(Entity1)
(AssociationNode)-[:ASSOCIATED_WITH {role_qname: "j:Charge"}]->(Entity2)
```

**Example (PersonChargeAssociation)**:
```cypher
CREATE (assoc:j_PersonChargeAssociation {
  id: 'file_assoc01',
  _isAssociation: true,
  j_JuvenileAsAdultIndicator: false
})
CREATE (assoc)-[:ASSOCIATED_WITH {role_qname: 'nc:Person'}]->(person)
CREATE (assoc)-[:ASSOCIATED_WITH {role_qname: 'j:Charge'}]->(charge)
```

**Why Not Direct Edges?**
- ✅ Associations can have properties (stored on association node)
- ✅ Associations can have 3+ endpoints (n-ary relationships)
- ✅ Associations can have metadata references
- ✅ Preserves NIEM association semantics

### Entity Role Relationships

**`REPRESENTS`** - Role-to-entity link

**Purpose**: Connect role nodes (CrashDriver, Victim) to actual entity nodes (Person)

**Color**: Purple, Dashed line

**Pattern**:
```cypher
(RoleNode)-[:REPRESENTS]->(EntityNode)
```

**How It Works**:

When the system encounters `structures:uri="#P01"`, it:
1. Creates the role node (e.g., j_CrashDriver) with all properties
2. Looks for or creates the entity node (e.g., nc_Person) with `structures:id="P01"`
3. Creates REPRESENTS relationship: `(role)-[:REPRESENTS]->(entity)`

**Examples**:
```cypher
// One person, multiple roles
(j_CrashDriver {structures_uri: '#P01'})-[:REPRESENTS]->(nc_Person {structures_id: 'P01'})
(j_CrashPerson {structures_uri: '#P01'})-[:REPRESENTS]->(nc_Person {structures_id: 'P01'})
(j_Victim {structures_uri: '#P01'})-[:REPRESENTS]->(nc_Person {structures_id: 'P01'})
```

**Key Feature**: Schema-agnostic
- Works with any role type (CrashDriver, Employee, Witness, Defendant, etc.)
- Works with any entity type (Person, Organization, Vehicle, Location, etc.)
- No hardcoded types in converter - determined dynamically

**Query Pattern**:
```cypher
// Find all roles for a person
MATCH (entity:nc_Person {structures_id: 'P01'})<-[:REPRESENTS]-(role)
RETURN entity, collect(role.qname) as roles

// Result: ['j:CrashDriver', 'j:CrashPerson']
```

### Co-Referencing Relationships

**`REFERS_TO`** - Cross-reference link

**Purpose**: Link nodes that reference the same entity via structures:uri or structures:ref

**Color**: Blue, Dashed line

**Pattern**:
```cypher
(Node1 {structures_uri: '#P01'})-[:REFERS_TO]->(Node2 {structures_id: 'P01'})
```

**Created from**:
- `structures:ref` attributes
- `structures:uri` attributes
- Metadata references (nc:metadataRef, priv:privacyMetadataRef)

### Entity Resolution Relationships

**`RESOLVED_TO`** - Entity-to-cluster link

**Purpose**: Link duplicate entities to their resolved cluster

**Color**: Magenta, Solid line

**Edge Properties**:
- `confidence` - Match confidence score (0.0-1.0)
- `resolution_method` - "senzing" or "text_based"
- `resolved_at` - Timestamp (ISO 8601)
- `senzing_entity_id` - Senzing entity ID (if applicable)

**Pattern**:
```cypher
(Entity1)-[:RESOLVED_TO {confidence: 0.95}]->(ResolvedEntity)
(Entity2)-[:RESOLVED_TO {confidence: 0.95}]->(ResolvedEntity)
```

**Example**:
```cypher
(p1:nc_Person {id: 'file1_P01', nc_PersonFullName: 'John Smith'})
  -[:RESOLVED_TO {confidence: 0.95, matched_on: 'given_name+surname'}]->
(re:ResolvedEntity {entity_id: 'RE_abc123', name: 'John Smith', resolved_count: 2})
```

## Property Patterns

### System Properties (All Nodes)

Every node has these system-managed properties:

```cypher
{
  id: "abc123_P01",              // Unique identifier (file-hash-prefixed)
  qname: "nc:Person",            // NIEM qualified name
  sourceDoc: "crash01.xml",      // Original filename
  _upload_id: "upload-456",      // Upload batch identifier
  _schema_id: "schema-789"       // Schema identifier
}
```

**Purpose of Multi-Tenant Properties**:

**`_upload_id`** - Upload batch isolation
- Tracks which batch upload created this node
- Enables deletion by batch: `MATCH (n {_upload_id: $id}) DETACH DELETE n`
- Supports multi-user workflows (Team A vs Team B uploads)

**`_schema_id`** - Schema isolation
- Tracks which schema was used to create this node
- Enables queries scoped to one schema: `MATCH (n {_schema_id: $id})`
- Supports multi-tenant SaaS scenarios (Customer 1 vs Customer 2 schemas)

**Why This Matters**:
```cypher
// Scenario: 3 teams using same Neo4j database
Team A: _schema_id='schema-crashdriver', 100 nodes
Team B: _schema_id='schema-childsafety', 200 nodes
Team C: _schema_id='schema-maritime', 50 nodes

// Query only Team A's data
MATCH (n {_schema_id: 'schema-crashdriver'}) RETURN n

// Delete only Team B's latest upload
MATCH (n {_upload_id: 'upload-20241108-teamB'}) DETACH DELETE n

// Entity resolution ACROSS Team A's uploads (find duplicates within team)
MATCH (e1 {_schema_id: 'schema-crashdriver'})-[:RESOLVED_TO]->(re)
WHERE re.resolved_count > 1
RETURN re
```

**Optional System Properties**:
- `structures_id` - Original structures:id value
- `structures_uri` - Original structures:uri value
- `structures_ref` - Original structures:ref value
- `ingestDate` - Ingestion timestamp

### NIEM Properties (Domain Data)

**Property Naming Convention**: `{namespace}_{elementName}` with `__` for nested paths

**Scalar Properties**:
```cypher
{
  nc_PersonGivenName: "John",
  nc_PersonSurName: "Smith",
  nc_PersonBirthDate: "1990-01-15",
  j_PersonAdultIndicator: true
}
```

**Flattened Nested Properties** (from schema designer selections):
```cypher
{
  nc_PersonName_nc_PersonGivenName: "John",
  nc_PersonName_nc_PersonSurName: "Smith",
  nc_ActivityDate__nc_Date: "2024-11-08"
}
```

**Array Properties** (multi-valued elements):
```cypher
{
  nc_PersonMiddleName: ["Death", "Bredon"],
  nc_PersonName_nc_PersonMiddleName: ["Death", "Bredon"]
}
```

### Augmentation Properties (Extension Data)

**Pattern**: Extension properties marked with metadata flag

```cypher
{
  exch_PersonFictionalCharacterIndicator: true,
  exch_PersonFictionalCharacterIndicator_isAugmentation: true
}
```

**Complex Augmentation Flattening**:
```cypher
{
  cb_exchange_TransmittalSubjectChild__nc_PersonFullName: "Jane Doe",
  cb_exchange_TransmittalSubjectChild__nc_PersonFullName_isAugmentation: true
}
```

**Purpose**:
- Preserve extension namespace data not in original schema
- Enable queries to identify schema vs extension properties
- Support custom domain extensions without schema changes

**Query Pattern**:
```cypher
// Find all nodes with augmentation properties
MATCH (n)
WHERE any(key IN keys(n) WHERE key ENDS WITH '_isAugmentation')
RETURN n
```

## Graph Structure Patterns

### Pattern 1: Flattened Properties (Schema Designer)

**Before Flattening** (XML):
```xml
<nc:Person>
  <nc:PersonName>
    <nc:PersonGivenName>John</nc:PersonGivenName>
    <nc:PersonSurName>Smith</nc:PersonSurName>
  </nc:PersonName>
  <nc:PersonBirthDate>
    <nc:Date>1990-01-15</nc:Date>
  </nc:PersonBirthDate>
</nc:Person>
```

**After Flattening** (Graph):
```cypher
CREATE (p:nc_Person {
  id: 'file_P01',
  qname: 'nc:Person',
  nc_PersonName_nc_PersonGivenName: 'John',
  nc_PersonName_nc_PersonSurName: 'Smith',
  nc_PersonBirthDate__nc_Date: '1990-01-15'
})
```

**No intermediate nodes created** for PersonName or PersonBirthDate (unless selected)

**Benefit**: Simpler queries, fewer nodes, direct property access

See [ADR-002: Graph Flattening Strategy](adr/ADR-002-graph-flattening-strategy.md)

### Pattern 2: Role-Entity Separation via REPRESENTS

**The NIEM Pattern**:
- Roles carry **context-specific information** (driver in a crash, victim in a crime)
- Entities are **reusable across roles** (same person can be driver AND victim)
- Link via `structures:uri` / `structures:ref`

**Graph Implementation**:

```cypher
// Entity (actual person) - minimal info
CREATE (person:nc_Person {
  id: 'file_P01',
  structures_id: 'P01',
  qname: 'nc:Person',
  _upload_id: 'upload-001',
  _schema_id: 'schema-crashdriver'
})

// Role 1: Driver - rich context
CREATE (driver:j_CrashDriver {
  id: 'file_syn_cd01',
  structures_uri: '#P01',
  nc_PersonName_nc_PersonGivenName: 'Peter',
  nc_PersonName_nc_PersonSurName: 'Wimsey',
  nc_PersonBirthDate__nc_Date: '1890-05-04',
  j_PersonAdultIndicator: true,
  _upload_id: 'upload-001',
  _schema_id: 'schema-crashdriver'
})
CREATE (driver)-[:REPRESENTS]->(person)

// Role 2: Injured person - same entity, different context
CREATE (crashperson:j_CrashPerson {
  id: 'file_syn_cp01',
  structures_uri: '#P01',
  _upload_id: 'upload-001',
  _schema_id: 'schema-crashdriver'
})
CREATE (crashperson)-[:REPRESENTS]->(person)
```

**Why REPRESENTS Is Schema-Agnostic**:

The converter doesn't need to know "what type of entity is at this URI":

```python
# Pseudocode in converter
if element.has_attribute('structures:uri'):
    role_node = create_node(element)  # j_CrashDriver
    uri = element.get('structures:uri')  # '#P01'

    # Create generic REPRESENTS edge
    # Entity type determined later when we encounter nc:Person element
    create_edge(role_node, 'REPRESENTS', entity_at_uri)
```

**Benefits**:
- ✅ Works with Person, Organization, Vehicle, any entity type
- ✅ No hardcoded type mappings needed
- ✅ Extensible to new NIEM domains
- ✅ Handles forward/backward references automatically

**Query Examples**:
```cypher
// Find all roles played by one person
MATCH (person:nc_Person)<-[:REPRESENTS]-(role)
WHERE person.structures_id = 'P01'
RETURN role.qname as role_type, role

// Find the entity for any role
MATCH (role {id: 'file_cd01'})-[:REPRESENTS]->(entity)
RETURN entity

// Find duplicate roles (same person playing same role twice - should be rare)
MATCH (entity)<-[:REPRESENTS]-(role1)
MATCH (entity)<-[:REPRESENTS]-(role2)
WHERE role1.qname = role2.qname AND id(role1) < id(role2)
RETURN entity, role1, role2
```

### Pattern 3: Hypergraph Associations

**N-ary relationships via association nodes**:

```cypher
// Association with properties
CREATE (assoc:j_PersonChargeAssociation {
  id: 'file_assoc01',
  _isAssociation: true,
  j_JuvenileAsAdultIndicator: false,
  _upload_id: 'upload-001',
  _schema_id: 'schema-justice'
})

// Multiple endpoints
CREATE (assoc)-[:ASSOCIATED_WITH {role_qname: 'nc:Person'}]->(person)
CREATE (assoc)-[:ASSOCIATED_WITH {role_qname: 'j:Charge'}]->(charge)
CREATE (assoc)-[:ASSOCIATED_WITH {role_qname: 'nc:Organization'}]->(org)
```

**Visual**: Orange hexagon nodes with thick dotted edges

**Why This Pattern?**
- Associations are first-class objects in NIEM (have properties, IDs, metadata)
- Can have 3+ endpoints (not just binary relationships)
- Properties belong to the association itself, not the edges

### Pattern 4: Dual Relationship Types

**Same parent-child expressed two ways**:

```cypher
// Containment (document structure)
(j_CrashVehicle)-[:HAS_CRASHDRIVER]->(j_CrashDriver)

// Reference (domain semantics)
(j_CrashVehicle)-[:J_CRASHDRIVER]->(j_CrashDriver)
```

**Different Query Semantics**:
- `HAS_CRASHDRIVER`: "Navigate document hierarchy from vehicle to driver"
- `J_CRASHDRIVER`: "Find the driver entity associated with this vehicle"

**Both relationships exist simultaneously** for richer querying

### Pattern 5: Entity Resolution Clustering

**Hub-and-spoke pattern**:

```cypher
// Entities from multiple files
CREATE (p1:nc_Person {
  id: 'file1_P01',
  nc_PersonFullName: 'John Smith',
  _upload_id: 'upload-001',
  _schema_id: 'schema-crashdriver'
})
CREATE (p2:nc_Person {
  id: 'file2_P02',
  nc_PersonFullName: 'John Smith',
  _upload_id: 'upload-002',
  _schema_id: 'schema-crashdriver'
})
CREATE (p3:nc_Person {
  id: 'file3_P03',
  nc_PersonFullName: 'John Smith',
  _upload_id: 'upload-003',
  _schema_id: 'schema-crashdriver'
})

// Resolved entity hub (multi-tenant properties)
CREATE (re:ResolvedEntity {
  entity_id: 'RE_abc123',
  name: 'John Smith',
  resolved_count: 3,
  resolution_method: 'senzing',
  confidence: 0.95,
  _upload_ids: ['upload-001', 'upload-002', 'upload-003'],  // Tracks all uploads
  _schema_ids: ['schema-crashdriver'],                       // Same schema
  sourceDocs: ['crash01.xml', 'crash02.xml', 'crash03.xml']
})

// Spokes
CREATE (p1)-[:RESOLVED_TO {confidence: 0.95}]->(re)
CREATE (p2)-[:RESOLVED_TO {confidence: 0.97}]->(re)
CREATE (p3)-[:RESOLVED_TO {confidence: 0.93}]->(re)
```

**Multi-Tenant Benefit**:
- Can see John Smith appears in 3 different uploads
- Can query: "Show me duplicates within upload-001 only"
- Can delete: "Remove all resolutions from upload-002"

## Example: CrashDriver Graph

### Complete Graph Structure

This shows the actual graph created from a CrashDriver XML file:

```cypher
// ============================================================================
// ROOT: Crash Event
// ============================================================================
CREATE (crash:j_Crash {
  id: 'abc123_CR01',
  qname: 'j:Crash',
  sourceDoc: 'CrashDriver1.xml',
  _upload_id: 'upload-20241108-001',
  _schema_id: 'schema-crashdriver',
  nc_ActivityDate__nc_Date: '1907-05-04'
})

// ============================================================================
// LEVEL 1: Crash Vehicle
// ============================================================================
CREATE (vehicle:j_CrashVehicle {
  id: 'abc123_CV01',
  qname: 'j:CrashVehicle',
  sourceDoc: 'CrashDriver1.xml',
  _upload_id: 'upload-20241108-001',
  _schema_id: 'schema-crashdriver'
})
CREATE (crash)-[:HAS_CRASHVEHICLE]->(vehicle)

// ============================================================================
// LEVEL 2: Crash Driver (Role with flattened properties)
// ============================================================================
CREATE (driver:j_CrashDriver {
  id: 'abc123_syn_cd01',
  qname: 'j:CrashDriver',
  sourceDoc: 'CrashDriver1.xml',
  structures_uri: '#P01',
  _upload_id: 'upload-20241108-001',
  _schema_id: 'schema-crashdriver',

  // Flattened name properties
  nc_PersonName_nc_PersonGivenName: 'Peter',
  nc_PersonName_nc_PersonMiddleName: ['Death', 'Bredon'],
  nc_PersonName_nc_PersonSurName: 'Wimsey',
  nc_PersonBirthDate__nc_Date: '1890-05-04',

  // Justice domain properties
  j_PersonAdultIndicator: true,

  // Extension augmentation properties
  exch_PersonFictionalCharacterIndicator: true,
  exch_PersonFictionalCharacterIndicator_isAugmentation: true
})
CREATE (vehicle)-[:HAS_CRASHDRIVER]->(driver)
CREATE (vehicle)-[:J_CRASHDRIVER]->(driver)  // Dual relationship (reference)

// ============================================================================
// LEVEL 3: Driver License
// ============================================================================
CREATE (dl:j_DriverLicense {
  id: 'abc123_DL01',
  qname: 'j:DriverLicense',
  sourceDoc: 'CrashDriver1.xml',
  _upload_id: 'upload-20241108-001',
  _schema_id: 'schema-crashdriver'
})
CREATE (driver)-[:HAS_DRIVERLICENSE]->(dl)

CREATE (dlid:j_DriverLicenseCardIdentification {
  id: 'abc123_DLID01',
  qname: 'j:DriverLicenseCardIdentification',
  nc_IdentificationID: 'A1234567',
  _upload_id: 'upload-20241108-001',
  _schema_id: 'schema-crashdriver'
})
CREATE (dl)-[:J_DRIVERLICENSECARDIDENTIFICATION]->(dlid)

// ============================================================================
// ENTITY: Actual Person (referenced by role via REPRESENTS)
// ============================================================================
CREATE (person:nc_Person {
  id: 'abc123_P01',
  qname: 'nc:Person',
  structures_id: 'P01',
  sourceDoc: 'CrashDriver1.xml',
  _upload_id: 'upload-20241108-001',
  _schema_id: 'schema-crashdriver'
})
CREATE (driver)-[:REPRESENTS]->(person)

// ============================================================================
// LEVEL 2B: Crash Person (Second role for same person)
// ============================================================================
CREATE (crashperson:j_CrashPerson {
  id: 'abc123_syn_cp01',
  qname: 'j:CrashPerson',
  sourceDoc: 'CrashDriver1.xml',
  structures_uri: '#P01',
  _upload_id: 'upload-20241108-001',
  _schema_id: 'schema-crashdriver'
})
CREATE (crash)-[:HAS_CRASHPERSON]->(crashperson)
CREATE (crashperson)-[:REPRESENTS]->(person)  // Same person, different role!

// ============================================================================
// LEVEL 3B: Injury Information
// ============================================================================
CREATE (injury:j_CrashPersonInjury {
  id: 'abc123_INJ01',
  qname: 'j:CrashPersonInjury',
  nc_InjuryDescriptionText: 'Broken Arm',
  j_InjurySeverityCode: 3,
  _upload_id: 'upload-20241108-001',
  _schema_id: 'schema-crashdriver'
})
CREATE (crashperson)-[:HAS_CRASHPERSONINJURY]->(injury)

// ============================================================================
// CHARGE: Criminal Charge
// ============================================================================
CREATE (charge:j_Charge {
  id: 'abc123_CH01',
  qname: 'j:Charge',
  structures_id: 'CH01',
  j_ChargeDescriptionText: 'Furious Driving',
  j_ChargeFelonyIndicator: false,
  _upload_id: 'upload-20241108-001',
  _schema_id: 'schema-crashdriver'
})

// ============================================================================
// ASSOCIATION: Person-Charge Link (Hypergraph pattern)
// ============================================================================
CREATE (assoc:j_PersonChargeAssociation {
  id: 'abc123_assoc01',
  qname: 'j:PersonChargeAssociation',
  _isAssociation: true,
  j_JuvenileAsAdultIndicator: false,
  _upload_id: 'upload-20241108-001',
  _schema_id: 'schema-crashdriver'
})
CREATE (assoc)-[:ASSOCIATED_WITH {role_qname: 'nc:Person'}]->(person)
CREATE (assoc)-[:ASSOCIATED_WITH {role_qname: 'j:Charge'}]->(charge)

// ============================================================================
// PRIVACY METADATA
// ============================================================================
CREATE (pmd1:priv_PrivacyMetadata {
  id: 'abc123_PMD01',
  structures_id: 'PMD01',
  qname: 'priv:PrivacyMetadata',
  priv_PrivacyCode: 'PII',
  _upload_id: 'upload-20241108-001',
  _schema_id: 'schema-crashdriver'
})
CREATE (pmd2:priv_PrivacyMetadata {
  id: 'abc123_PMD02',
  structures_id: 'PMD02',
  qname: 'priv:PrivacyMetadata',
  priv_PrivacyCode: 'MEDICAL',
  _upload_id: 'upload-20241108-001',
  _schema_id: 'schema-crashdriver'
})
CREATE (injury)-[:HAS_PRIVACYMETADATA]->(pmd1)
CREATE (injury)-[:HAS_PRIVACYMETADATA]->(pmd2)

// ============================================================================
// JUSTICE METADATA
// ============================================================================
CREATE (jmd:nc_Metadata {
  id: 'abc123_JMD01',
  structures_id: 'JMD01',
  qname: 'nc:Metadata',
  j_CriminalInformationIndicator: true,
  _upload_id: 'upload-20241108-001',
  _schema_id: 'schema-crashdriver'
})
CREATE (charge)-[:HAS_METADATA]->(jmd)
CREATE (assoc)-[:HAS_METADATA]->(jmd)
```

### Key Insights from CrashDriver Example

**1. One Person, Multiple Roles (via REPRESENTS)**:
```
Person (P01) ← REPRESENTS ← CrashDriver (role as driver)
Person (P01) ← REPRESENTS ← CrashPerson (role as injured person)
```
Query all roles: `MATCH (p:nc_Person)<-[:REPRESENTS]-(r) WHERE p.structures_id='P01'`

**2. Dual Relationship Types**:
```
Containment:  (CrashVehicle)-[:HAS_CRASHDRIVER]->(CrashDriver)
Reference:    (CrashVehicle)-[:J_CRASHDRIVER]->(CrashDriver)
```
Both exist for same nodes, different query semantics

**3. Property Flattening**:
```xml
<nc:PersonName><nc:PersonGivenName>Peter</nc:PersonGivenName></nc:PersonName>
```
Becomes: `nc_PersonName_nc_PersonGivenName: 'Peter'`

**4. Augmentation Marking**:
```
exch_PersonFictionalCharacterIndicator: true (extension property value)
exch_PersonFictionalCharacterIndicator_isAugmentation: true (metadata flag)
```

**5. Multi-Tenant Isolation**:
All nodes tagged with `_upload_id` and `_schema_id` for selective querying/deletion

## Common Query Patterns

### Query 1: Find All Roles for a Person

```cypher
// Find all roles that represent the same person entity
MATCH (entity:nc_Person {structures_id: 'P01'})<-[:REPRESENTS]-(role)
RETURN entity.structures_id as person_id,
       collect(role.qname) as roles_played,
       collect(role.id) as role_ids

// Result:
// person_id: 'P01'
// roles_played: ['j:CrashDriver', 'j:CrashPerson']
```

### Query 2: Traverse Document Structure

```cypher
// Get full crash hierarchy
MATCH path = (root:j_Crash)-[:HAS_*]->(leaf)
WHERE root.sourceDoc = 'crash01.xml'
RETURN path

// Or specific depth
MATCH (crash:j_Crash)-[:HAS_CRASHVEHICLE]->(vehicle)-[:HAS_CRASHDRIVER]->(driver)
WHERE crash._upload_id = $uploadId
RETURN crash, vehicle, driver
```

### Query 3: Find Domain Relationships

```cypher
// Find all drivers via semantic relationship
MATCH (vehicle:j_CrashVehicle)-[:J_CRASHDRIVER]->(driver:j_CrashDriver)
RETURN vehicle, driver

// vs containment relationship
MATCH (vehicle:j_CrashVehicle)-[:HAS_CRASHDRIVER]->(driver:j_CrashDriver)
RETURN vehicle, driver

// Both return same results, different semantic meaning
```

### Query 4: Find Association Endpoints

```cypher
// Find all entities connected via an association
MATCH (assoc {_isAssociation: true})-[r:ASSOCIATED_WITH]->(endpoint)
WHERE assoc.qname = 'j:PersonChargeAssociation'
RETURN assoc, r.role_qname as role, endpoint

// Find specific role in association
MATCH (assoc:j_PersonChargeAssociation)-[:ASSOCIATED_WITH {role_qname: 'nc:Person'}]->(person)
RETURN assoc, person

// Find all associations involving a person
MATCH (person:nc_Person)<-[:ASSOCIATED_WITH]-(assoc {_isAssociation: true})
RETURN person, assoc
```

### Query 5: Find Resolved Duplicates

```cypher
// Find all entities resolved to same cluster
MATCH (entity)-[:RESOLVED_TO]->(re:ResolvedEntity)
WHERE re.resolved_count > 1
RETURN re.entity_id as cluster,
       re.name as name,
       collect(entity.sourceDoc) as source_files,
       collect(entity.id) as entity_ids

// Find high-confidence matches only
MATCH (entity)-[r:RESOLVED_TO]->(re:ResolvedEntity)
WHERE r.confidence > 0.9
RETURN entity, r, re

// Find duplicates using Senzing (not text-based)
MATCH (entity)-[:RESOLVED_TO]->(re:ResolvedEntity {resolution_method: 'senzing'})
WHERE re.resolved_count > 1
RETURN re, collect(entity) as duplicates
```

### Query 6: Multi-Tenant Queries (Isolation by Schema/Upload)

```cypher
// All nodes from specific upload
MATCH (n {_upload_id: 'upload-20241108-001'})
RETURN n

// All nodes from specific schema
MATCH (n {_schema_id: 'schema-crashdriver'})
RETURN n

// Delete all nodes from specific upload (cleanup)
MATCH (n {_upload_id: 'upload-20241108-001'})
DETACH DELETE n

// Cross-upload entity resolution (find same person in multiple uploads)
MATCH (e1)-[:RESOLVED_TO]->(re:ResolvedEntity)
WHERE size(re._upload_ids) > 1  // Appears in multiple uploads
RETURN re.name, re._upload_ids, collect(e1.sourceDoc) as files
```

### Query 7: Find Extension Properties

```cypher
// Find all nodes with augmentation properties
MATCH (n)
WHERE any(key IN keys(n) WHERE key ENDS WITH '_isAugmentation')
RETURN n.qname, [key IN keys(n) WHERE key ENDS WITH '_isAugmentation'] as augmentations

// Find specific augmentation
MATCH (n)
WHERE n.exch_PersonFictionalCharacterIndicator_isAugmentation = true
RETURN n.exch_PersonFictionalCharacterIndicator as is_fictional, n
```

### Query 8: Find Privacy-Classified Data

```cypher
// Find all data with privacy classifications
MATCH (data)-[:HAS_PRIVACYMETADATA]->(pmd:priv_PrivacyMetadata)
RETURN data.qname, collect(pmd.priv_PrivacyCode) as privacy_codes

// Find PII data only
MATCH (data)-[:HAS_PRIVACYMETADATA]->(pmd {priv_PrivacyCode: 'PII'})
RETURN data

// Find medical privacy data
MATCH (data)-[:HAS_PRIVACYMETADATA]->(pmd {priv_PrivacyCode: 'MEDICAL'})
RETURN data
```

### Query 9: Find Co-Referenced Entities

```cypher
// Find all nodes referencing the same entity ID
MATCH (n)
WHERE n.structures_uri = '#P01' OR n.structures_id = 'P01'
RETURN n.qname as node_type, n

// Find entities with multiple references
MATCH (entity)
WHERE entity.structures_id IS NOT NULL
WITH entity
MATCH (ref)-[:REPRESENTS|REFERS_TO]->(entity)
WITH entity, count(ref) as ref_count
WHERE ref_count > 1
RETURN entity, ref_count
```

### Query 10: Get Statistics

```cypher
// Count nodes by type
MATCH (n)
RETURN n.qname as type, count(n) as count
ORDER BY count DESC

// Count relationships by type
MATCH ()-[r]->()
RETURN type(r) as relationship, count(r) as count
ORDER BY count DESC

// Find orphan nodes (no relationships)
MATCH (n)
WHERE NOT (n)-[]-()
RETURN n

// Schema/Upload statistics
MATCH (n)
RETURN n._schema_id as schema,
       n._upload_id as upload,
       count(n) as node_count
ORDER BY node_count DESC
```

## Schema Design Decisions

### Decision 1: File-Prefixed IDs for Multi-File Isolation

**Problem**: Multiple files may use same structures:id values

```xml
<!-- crash01.xml -->
<nc:Person structures:id="P01">John Smith</nc:Person>

<!-- crash02.xml -->
<nc:Person structures:id="P01">Jane Doe</nc:Person>  <!-- DIFFERENT person! -->
```

**Without Prefixing** ❌:
- Both create node with `id: 'P01'`
- Second file overwrites first
- Data loss!

**Solution**: Prefix all IDs with file hash
```
crash01.xml (hash: abc123) → id = "abc123_P01"
crash02.xml (hash: xyz789) → id = "xyz789_P01"
```

**Benefit**:
- ✅ No ID collisions
- ✅ Files are isolated
- ✅ Can query by file: `MATCH (n) WHERE n.id STARTS WITH 'abc123_'`
- ✅ Preserves original `structures_id` separately

See [ADR-001: Batch Processing Pattern](adr/ADR-001-batch-processing-pattern.md)

### Decision 2: Schema-Agnostic REPRESENTS Pattern

**Problem**: Role types vary by domain, entity types vary by domain

**Traditional Approach** ❌:
```cypher
// Would need separate relationships for each combination
(j_CrashDriver)-[:DRIVER_IS_PERSON]->(nc_Person)
(j_Employee)-[:EMPLOYEE_IS_PERSON]->(nc_Person)
(j_Suspect)-[:SUSPECT_IS_PERSON]->(nc_Person)
(j_VehicleOwner)-[:OWNER_IS_PERSON]->(nc_Person)
(j_VehicleOwner)-[:OWNER_IS_ORGANIZATION]->(nc_Organization)
// Hundreds of relationship types needed!
```

**Our Solution** ✅:
```cypher
// ONE generic relationship
(AnyRoleType)-[:REPRESENTS]->(AnyEntityType)
```

**How It's Implemented**:

The converter doesn't hardcode entity types. When it sees `structures:uri="#P01"`:

```python
# Pseudocode
def process_element_with_uri(element):
    # Create role node
    role_node = create_node_from_element(element)  # j_CrashDriver

    # Extract URI reference
    uri = element.get('structures:uri')  # '#P01'

    # Create REPRESENTS edge to whatever entity has that ID
    # Entity type determined dynamically when nc:Person element is encountered
    create_edge(role_node, 'REPRESENTS', entity_at_uri=uri)
```

**Benefits**:
- ✅ Extensible to new NIEM domains (works with ANY role/entity combination)
- ✅ No code changes needed for new entity types
- ✅ Simple queries: `MATCH (role)-[:REPRESENTS]->(entity)`
- ✅ Maintains semantic meaning regardless of domain

### Decision 3: `_upload_id` and `_schema_id` for Multi-Tenant Support

**Problem**: Multiple users/teams/projects sharing one Neo4j database

**Scenario 1 - Multiple Uploads**:
```
User uploads crash01.xml → 50 nodes created
User uploads crash02.xml → 50 nodes created
User uploads crash03.xml → 50 nodes created (OOPS - bad data!)

User wants to delete crash03.xml only → How?
```

**Without `_upload_id`** ❌:
- No way to identify which nodes came from which upload
- Must delete entire database and re-ingest crash01.xml, crash02.xml
- Data loss risk

**With `_upload_id`** ✅:
```cypher
// Tag all nodes from each upload
crash01.xml → all nodes get {_upload_id: 'upload-001'}
crash02.xml → all nodes get {_upload_id: 'upload-002'}
crash03.xml → all nodes get {_upload_id: 'upload-003'}

// Delete just crash03.xml
MATCH (n {_upload_id: 'upload-003'})
DETACH DELETE n
```

**Scenario 2 - Multiple Schemas (Teams/Projects)**:
```
Team A (Police): Uses crashdriver.xsd → 100 uploads
Team B (Child Welfare): Uses neice.xsd → 200 uploads
Team C (Maritime): Uses maritime.xsd → 50 uploads

All teams share one Neo4j database
```

**Without `_schema_id`** ❌:
- Cannot query "show me ONLY police data"
- Cannot filter graph visualization by schema
- Entity resolution mixes all schemas (police person matched with child welfare person!)

**With `_schema_id`** ✅:
```cypher
// Query only Team A's data
MATCH (n {_schema_id: 'schema-crashdriver'})
RETURN n

// Entity resolution scoped to schema
MATCH (e1 {_schema_id: 'schema-crashdriver'})-[:RESOLVED_TO]->(re)
WHERE size(re._schema_ids) = 1  // Only within same schema
RETURN re

// Graph visualization filtered by schema
MATCH (n {_schema_id: $selectedSchema})-[r]-(m {_schema_id: $selectedSchema})
RETURN n, r, m
```

**Multi-Tenant Benefits**:
- ✅ **Data Isolation**: Each team sees only their data
- ✅ **Selective Deletion**: Delete by upload/schema without affecting others
- ✅ **Scoped Queries**: Filter graph by team/project/upload
- ✅ **Entity Resolution Control**: Resolve within schema or across schemas
- ✅ **Future SaaS**: Add `_tenant_id` for customer isolation
- ✅ **GDPR Compliance**: Can delete all data for specific user/upload

**ResolvedEntity Multi-Tenant Tracking**:
```cypher
// ResolvedEntity tracks ALL uploads/schemas that contributed
CREATE (re:ResolvedEntity {
  entity_id: 'RE_abc123',
  name: 'John Smith',
  resolved_count: 3,
  _upload_ids: ['upload-001', 'upload-002', 'upload-003'],  // From 3 uploads
  _schema_ids: ['schema-crashdriver'],                       // Same schema
  sourceDocs: ['crash01.xml', 'crash02.xml', 'crash03.xml']
})
```

**Query Example**:
```cypher
// Find people who appear in multiple uploads (possible duplicates)
MATCH (entity)-[:RESOLVED_TO]->(re:ResolvedEntity)
WHERE size(re._upload_ids) > 1
RETURN re.name,
       size(re._upload_ids) as num_uploads,
       re._upload_ids as uploads,
       re.sourceDocs as files
```

### Decision 4: Flattened vs Nested Properties

**Trade-off**:
- **Nested**: Preserves exact document structure (more nodes, complex queries)
- **Flattened**: Simpler queries, fewer nodes (loses intermediate structure)

**Solution**: **Configurable via schema designer**
- User selects which complex elements become nodes
- Other complex elements are flattened as properties
- Default: Flatten most, create nodes for key entities

**Example**:
```cypher
// If PersonName NOT selected → flattened
{
  nc_PersonName_nc_PersonGivenName: 'John',
  nc_PersonName_nc_PersonSurName: 'Smith'
}

// If PersonName IS selected → separate node
(person:nc_Person)-[:HAS_PERSONNAME]->(name:nc_PersonName {
  nc_PersonGivenName: 'John',
  nc_PersonSurName: 'Smith'
})
```

**Benefit**: Balance between fidelity and query simplicity

See [ADR-002: Graph Flattening Strategy](adr/ADR-002-graph-flattening-strategy.md)

### Decision 5: Dual-Mode Converter

**Problem**: Exploration needs all data, production needs controlled structure

**Solution**: Two modes
- **Dynamic Mode**: Create nodes for all complex elements (includes extensions)
- **Mapping Mode**: Create nodes only for selected elements

**Trigger**: Presence/absence of selections.json file

**Benefit**: One system, two workflows (explore → optimize)

### Decision 6: Hypergraph Associations

**Problem**: NIEM associations have properties and 3+ endpoints

**Traditional Graph** ❌:
```cypher
// Binary edge can't carry association properties
(person)-[:CHARGED_WITH {j_JuvenileAsAdultIndicator: false}]->(charge)

// Problem: What if 3+ endpoints?
// Problem: Where do we put association metadata?
```

**Our Solution** ✅:
```cypher
// Association is a node (can have properties and metadata)
CREATE (assoc:j_PersonChargeAssociation {
  _isAssociation: true,
  j_JuvenileAsAdultIndicator: false
})
CREATE (assoc)-[:ASSOCIATED_WITH {role_qname: 'nc:Person'}]->(person)
CREATE (assoc)-[:ASSOCIATED_WITH {role_qname: 'j:Charge'}]->(charge)
CREATE (assoc)-[:HAS_METADATA]->(metadata)
```

**Benefits**:
- ✅ Supports 3+ endpoints (n-ary relationships)
- ✅ Association properties stored on association node
- ✅ Association can have metadata
- ✅ Full semantic fidelity with NIEM

## Data Integrity Constraints

### Uniqueness Constraints

```cypher
// Ensure unique node IDs
CREATE CONSTRAINT unique_node_id IF NOT EXISTS
FOR (n) REQUIRE n.id IS UNIQUE

// Ensure unique resolved entity IDs
CREATE CONSTRAINT unique_resolved_entity_id IF NOT EXISTS
FOR (n:ResolvedEntity) REQUIRE n.entity_id IS UNIQUE
```

### Property Existence Constraints (Future)

```cypher
// All nodes must have qname
CREATE CONSTRAINT require_qname IF NOT EXISTS
FOR (n) REQUIRE n.qname IS NOT NULL

// All nodes must have sourceDoc
CREATE CONSTRAINT require_source IF NOT EXISTS
FOR (n) REQUIRE n.sourceDoc IS NOT NULL
```

## Schema Evolution

### Current Version: 1.0

**Schema Changes Since Initial Version**:
- Added `_upload_id` and `_schema_id` for multi-tenant support
- Added `_isAugmentation` flags for extension properties
- Added `ResolvedEntity` nodes and `RESOLVED_TO` relationships
- Added `REPRESENTS` pattern for role-entity separation
- Added `ASSOCIATED_WITH` pattern for hypergraph associations

### Future Schema Changes (Planned)

- **Version 2.0**: Add NIEM version property to nodes
- **Version 2.1**: Add validation status properties
- **Version 3.0**: Support for NIEM 6.0 schema changes

**Migration Strategy**: Additive only (no breaking changes)

## Related Documentation

- **[GRAPH_GENERATION_LOGIC.md](GRAPH_GENERATION_LOGIC.md)** - Algorithm deep-dive for graph generation
- **[INGESTION_AND_MAPPING.md](INGESTION_AND_MAPPING.md)** - Data transformation pipeline
- **[ADR-002: Graph Flattening Strategy](adr/ADR-002-graph-flattening-strategy.md)** - Flattening design decisions
- **[ADR-001: Batch Processing Pattern](adr/ADR-001-batch-processing-pattern.md)** - File isolation design
- **[WORKFLOWS.md](WORKFLOWS.md)** - Sequence diagrams showing graph creation
- **[ARCHITECTURE.md](../ARCHITECTURE.md)** - System architecture overview

---

**Last Updated**: 2024-11-08
**Schema Version**: 1.0
**System Version**: 0.1.0-alpha
