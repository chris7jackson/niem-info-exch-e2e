# NIEM Graph Ingestion and Mapping Guide

## Overview

This document explains how NIEM XML Schemas (XSD) and instance documents (XML and JSON) are processed and ingested into a Neo4j graph database. The system ensures that **both XML and JSON representations of the same data create identical graph structures** by using a unified mapping specification derived from the schema.

## Architecture Overview

```
┌─────────────┐
│ XSD Schemas │──┐
└─────────────┘  │
                 │  1. Schema Upload
                 ▼
         ┌──────────────┐
         │ CMF Tool     │
         │ (xsd2cmf)    │
         └──────┬───────┘
                │
                │  2. Schema Analysis
                ▼
         ┌──────────────┐
         │ CMF Document │
         │ ({name}.cmf) │
         └──────┬───────┘
                │
                │  3. Mapping Generation
                ▼
         ┌──────────────┐
         │ mapping.yaml │◄────────────┐
         └──────┬───────┘             │
                │                     │ Same mapping
                │  4. Instance        │ used for both
                │     Ingestion       │ formats!
                │                     │
       ┌────────┴────────┐            │
       ▼                 ▼            │
┌──────────┐      ┌──────────┐       │
│ XML Doc  │      │ JSON Doc │       │
└────┬─────┘      └────┬─────┘       │
     │                 │              │
     │  5. Validate    │  5. Validate │
     │  (XSD)          │  (JSON       │
     │                 │   Schema)    │
     ▼                 ▼              │
┌──────────────────────────┐         │
│ XML→Graph or JSON→Graph  │─────────┘
│ Converter                │
└────────┬─────────────────┘
         │
         │  6. Generate Cypher
         ▼
  ┌──────────────┐
  │ Cypher       │
  │ Statements   │
  └──────┬───────┘
         │
         │  7. Execute
         ▼
  ┌──────────────┐
  │ Neo4j Graph  │
  └──────────────┘
```

## Part 1: Schema Processing Pipeline

### Step 1: XSD Schema Upload

**Endpoint:** `POST /schema/upload`

**What Happens:**
1. User uploads one or more XSD files (with directory structure preserved)
2. System validates:
   - File size limits
   - NIEM NDR conformance (using pre-compiled XSLT rules)
   - Schema dependencies (all imports are satisfied)
3. Files are stored in MinIO at `niem-schemas/{schema_id}/source/`

**Key Files:**
- `api/src/niem_api/handlers/schema.py` - Upload handler
- `api/src/niem_api/services/domain/schema/scheval_validator.py` - NIEM NDR validation using scheval

### Step 2: XSD → CMF Conversion

**CMF Tool:** Common Model Format (CMF 1.0) is an XML representation of the NIEM model

**What Happens:**
```bash
cmftool xsd2cmf --xsd {primary_schema.xsd} --output {primary_schema}.cmf
```

The CMF document contains:
- **Classes:** Object types and association types
- **Properties:** Element and attribute definitions
- **Datatypes:** Simple and complex types
- **Namespaces:** Prefix-to-URI mappings
- **Relationships:** SubClassOf, PropertyAssociations

**Key Files:**
- `api/src/niem_api/clients/cmf_client.py` - CMF tool wrapper
- Output: `niem-schemas/{schema_id}/{primary_schema}.cmf` (e.g., `CrashDriver.cmf`)

### Step 3: CMF → mapping.yaml Generation

**Purpose:** Generate a declarative mapping specification that tells the graph converter how to transform instance data into Neo4j nodes and relationships.

**What Happens:**
The `mapping.yaml` is automatically generated from the CMF document by analyzing:

1. **Objects Section:** Maps NIEM elements to Neo4j node labels
2. **Associations Section:** Maps NIEM associations to Neo4j relationships
3. **References Section:** Maps object-valued properties to Neo4j relationships
4. **Scalar Properties:** Maps data properties to Neo4j node properties

**Key Files:**
- `api/src/niem_api/services/domain/schema/mapping.py` - CMF→mapping converter
- Output: `niem-schemas/{schema_id}/mapping.yaml`

#### mapping.yaml Structure

```yaml
# Namespace prefix mappings
namespaces:
  nc: "https://docs.oasis-open.org/niemopen/ns/model/niem-core/6.0/"
  j: "https://docs.oasis-open.org/niemopen/ns/model/domains/justice/6.0/"

# Object types → Neo4j node labels
objects:
  - qname: nc:Person              # Element qualified name
    label: nc_Person              # Neo4j node label (colons → underscores)
    carries_structures_id: true   # Has structures:id attribute
    scalar_props:                 # Scalar properties to extract
      - path: nc:PersonName/nc:PersonGivenName
        neo4j_property: nc_PersonGivenName
      - path: nc:PersonName/nc:PersonSurName
        neo4j_property: nc_PersonSurName

  - qname: j:Crash
    label: j_Crash
    carries_structures_id: true
    scalar_props: []

# Association types → Neo4j relationships
associations:
  - qname: j:PersonChargeAssociation
    rel_type: J_PERSONCHARGEASSOCIATION
    endpoints:
      - role_qname: nc:Person     # First endpoint
        maps_to_label: nc_Person
        direction: source
        via: structures:ref
      - role_qname: j:Charge      # Second endpoint
        maps_to_label: j_Charge
        direction: target
        via: structures:ref

# Object-valued references → Neo4j relationships
references:
  - owner_object: j:CrashVehicle
    field_qname: j:CrashDriver
    target_label: j_CrashDriver
    rel_type: J_CRASHDRIVER
    via: structures:ref

# Metadata for augmentation detection
metadata:
  cmf_element_index:
    - nc:Person
    - j:Crash
    - j:CrashDriver
    # ... all known CMF elements
```

**How It Works:**

1. **Objects:** For each CMF Class, extract:
   - Element QName (from ObjectProperty)
   - Neo4j label (QName with `:` → `_`)
   - Scalar properties by traversing nested DataProperty paths

2. **Associations:** For each Class with `SubClassOf = nc.AssociationType`:
   - Extract endpoint roles (ObjectProperty children)
   - Map to target node labels
   - Generate relationship type (UPPER_SNAKE_CASE)

3. **References:** For each Class's ObjectProperty child that references another Class:
   - Create reference rule with owner → field → target
   - Generate relationship type from field name

## Part 2: Instance Document Ingestion

### Dual-Mode Converter Architecture

**New in 2025-11-07:** The XML to graph converter now operates in two modes to provide flexibility for exploration and production workflows.

| Mode | When Active | Node Creation | Use Case |
|------|-------------|---------------|----------|
| **Dynamic Mode** | No `selections.json` exists | Creates nodes for ALL complex elements | Initial exploration - see complete data including extension namespaces |
| **Mapping Mode** | `selections.json` exists with selections | Creates nodes ONLY for elements in mapping.yaml | Production - controlled graph structure via schema designer |

**Mode Detection:**
```python
# Automatic mode detection in ingest handler
if selections_json_exists() and has_selections():
    mode = "mapping"  # Use schema designer selections
else:
    mode = "dynamic"  # Include all complex elements
```

**Complex Element Criteria (Dynamic Mode):**
Elements become nodes if they have:
1. `structures:id` or `structures:uri` attributes, OR
2. Child elements (not just text), OR
3. Non-structural attributes

Simple text-only elements are flattened as properties.

**Benefits:**
- ✅ **Zero data loss**: Extension namespaces (cb_ext, cb_exchange) automatically included
- ✅ **Flexible workflow**: Explore first (dynamic), then optimize (mapping)
- ✅ **Backward compatible**: Existing schema designer behavior unchanged
- ✅ **Schema portability**: Works with any NIEM schema including custom extensions

### XML and JSON: Two Formats, Same Graph

**Key Principle:** The same `mapping.yaml` is used to ingest both XML and JSON documents in **Mapping Mode**, ensuring they produce identical graph structures. In **Dynamic Mode**, both formats use the same complex element detection logic.

### NIEM XML Structure

**Key Features:**
- **Namespace prefixes:** `nc:Person`, `j:Crash`
- **structures:id:** Unique identifier for objects (`<j:Crash structures:id="CR01">`)
- **structures:ref:** Reference to another object (`<j:Crash structures:ref="CR01"/>`)
- **structures:uri:** URI reference to a Person entity (`<j:CrashDriver structures:uri="#P01">`)
- **Metadata references:** `nc:metadataRef="MD01"` or `priv:privacyMetadataRef="PMD01"`
- **Nested elements:** Hierarchical structure with containment

**Example:**
```xml
<exch:CrashDriverInfo>
  <j:Crash>
    <j:CrashVehicle>
      <j:CrashDriver structures:uri="#P01">
        <nc:PersonName>
          <nc:PersonGivenName>Peter</nc:PersonGivenName>
        </nc:PersonName>
      </j:CrashDriver>
    </j:CrashVehicle>
  </j:Crash>
</exch:CrashDriverInfo>
```

### NIEM JSON Structure

**Key Features:**
- **@context:** Maps namespace prefixes to URIs (JSON-LD feature)
- **@id:** Unique identifier for objects (like structures:id)
- **@type:** Optional type annotation
- **Property names use prefixes:** `"nc:PersonGivenName"`
- **References:** Objects with only `@id` field (`{"@id": "P01"}`)
- **Arrays:** NIEM JSON uses arrays even for single values (strict mode)

**Example:**
```json
{
  "@context": {
    "nc": "https://docs.oasis-open.org/niemopen/ns/model/niem-core/6.0/",
    "j": "https://docs.oasis-open.org/niemopen/ns/model/domains/justice/6.0/"
  },
  "j:Crash": {
    "j:CrashVehicle": [{
      "j:CrashDriver": {
        "@id": "#P01",
        "nc:PersonName": [{
          "nc:PersonGivenName": ["Peter"]
        }]
      }
    }]
  }
}
```

### XML Ingestion Flow

**Endpoint:** `POST /ingest/xml`

**Steps:**

1. **Validation:**
   ```python
   # Download XSD schemas from S3
   schema_files = download_schema_files(s3, schema_id)

   # Validate XML against XSD using CMF tool
   cmftool xval --schema *.xsd --file instance.xml
   ```

2. **Load Mapping:**
   ```python
   # Load mapping.yaml from S3
   mapping = s3.get_object("niem-schemas", f"{schema_id}/mapping.yaml")
   ```

3. **Detect Mode:**
   ```python
   # Check if selections.json exists with custom selections
   from .schema import handle_get_selections
   mode = "mapping" if has_selections(schema_id) else "dynamic"
   ```

4. **Generate Cypher:**
   ```python
   from xml_to_graph import generate_for_xml_content

   cypher, nodes, contains, edges = generate_for_xml_content(
       xml_content, mapping, filename, upload_id, schema_id, mode=mode
   )
   ```

5. **Execute in Neo4j:**
   ```cypher
   MERGE (n:`nc_Person` {id:'file_prefix_P01'})
   ON CREATE SET n.qname='nc:Person', n.sourceDoc='CrashDriver1.xml'
   ```

**Key Files:**
- `api/src/niem_api/handlers/ingest.py` - Ingest handler
- `api/src/niem_api/services/domain/xml_to_graph/converter.py` - XML→Cypher converter

### JSON Ingestion Flow

**Endpoint:** `POST /ingest/json`

**Steps:**

1. **Validation:**
   ```python
   # Download JSON Schema from S3 (e.g., CrashDriver.json)
   json_schema = s3.get_object("niem-schemas", f"{schema_id}/{primary_schema}.json")

   # Validate JSON against JSON Schema
   validator = Draft7Validator(json_schema)
   errors = list(validator.iter_errors(data))
   ```

2. **Load Mapping:**
   ```python
   # Same mapping.yaml as XML!
   mapping = s3.get_object("niem-schemas", f"{schema_id}/mapping.yaml")
   ```

3. **Generate Cypher:**
   ```python
   from json_to_graph import generate_for_json_content

   cypher, nodes, contains, edges = generate_for_json_content(
       json_content, mapping, filename
   )
   ```

4. **Execute in Neo4j:**
   ```cypher
   # Same graph structure as XML!
   MERGE (n:`nc_Person` {id:'file_prefix_P01'})
   ON CREATE SET n.qname='nc:Person', n.sourceDoc='CrashDriver1.json'
   ```

**Key Files:**
- `api/src/niem_api/handlers/ingest.py` - Ingest handler
- `api/src/niem_api/services/domain/json_to_graph/converter.py` - JSON→Cypher converter

## Part 3: Graph Structure Generation

### How XML/JSON Maps to Neo4j

Both converters follow the same logic using the `mapping.yaml`:

#### 1. Node Creation

**Mapping Mode Rule:** Any element with:
- `structures:id` (XML) or `@id` (JSON), OR
- Matching entry in `objects[]` section of mapping, OR
- `metadataRef` or `privacyMetadataRef` attributes

**Dynamic Mode Rule:** Any complex element:
- Has `structures:id` or `structures:uri`, OR
- Has child elements (not just text), OR
- Has non-structural attributes

**Creates:** Neo4j node with:
- **Label:** From `objects[].label` (e.g., `nc_Person`)
- **Properties:**
  - `id`: Unique identifier (prefixed with file hash for multi-file uniqueness)
  - `qname`: Element qualified name (e.g., `nc:Person`)
  - `sourceDoc`: Source filename
  - Scalar properties extracted per `objects[].scalar_props[]`
  - Augmentation properties (unmapped data with `aug_` prefix)

**Example (Mapping Mode):**
```cypher
MERGE (n:`nc_Person` {id:'abc123_P01'})
  ON CREATE SET
    n.qname='nc:Person',
    n.sourceDoc='CrashDriver1.xml',
    n.nc_PersonGivenName='Peter',
    n.nc_PersonSurName='Wimsey'
```

**Example (Dynamic Mode with Extension Namespace):**
```cypher
MERGE (n:`cb_ext_FollowupReport` {id:'abc123_FR01'})
  ON CREATE SET
    n.qname='cb_ext:FollowupReport',
    n.sourceDoc='FollowupReport.xml',
    n.cb_ext_ReportDate='2024-01-15'
```

#### 2. Containment Relationships

**Rule:** Parent-child structural relationships in the document

**Creates:** `HAS_*` relationships

**Example:**
```cypher
MATCH (p:`j_Crash` {id:'abc123_CR01'}),
      (c:`j_CrashVehicle` {id:'abc123_CV01'})
MERGE (p)-[:`HAS_CRASHVEHICLE`]->(c)
```

**Purpose:** Preserves document structure and element containment

#### 3. Reference Relationships

**Rule:** Matches `references[]` section of mapping

**Creates:** Named relationships between objects

**Example Mapping:**
```yaml
references:
  - owner_object: j:CrashVehicle
    field_qname: j:CrashDriver
    rel_type: J_CRASHDRIVER
    target_label: j_CrashDriver
```

**Example Cypher:**
```cypher
MATCH (a:`j_CrashVehicle` {id:'abc123_CV01'}),
      (b:`j_CrashDriver` {id:'abc123_CD01'})
MERGE (a)-[:`J_CRASHDRIVER`]->(b)
```

#### 4. Association Relationships (Hypergraph Pattern)

**Rule:** Matches `associations[]` section of mapping

**Creates:** Intermediate association node with `ASSOCIATED_WITH` edges to endpoint entities (no containment edges)

**Pattern:** Associations are represented as nodes (not direct edges) to support n-ary relationships and association properties. Association nodes do NOT have containment relationships with their parents since they represent relationships between entities, not hierarchical containment.

**Example Mapping:**
```yaml
associations:
  - qname: j:PersonChargeAssociation
    rel_type: J_PERSONCHARGEASSOCIATION
    endpoints:
      - role_qname: nc:Person
        maps_to_label: nc_Person
      - role_qname: j:Charge
        maps_to_label: j_Charge
```

**Example Cypher:**
```cypher
# Create association node with properties
MERGE (assoc:`j_PersonChargeAssociation` {id:'abc123_assoc01'})
  SET assoc.qname = 'j:PersonChargeAssociation',
      assoc._isAssociation = true,
      assoc.j_JuvenileAsAdultIndicator = false

# Create ASSOCIATED_WITH edges to endpoints (not CONTAINS edges)
MATCH (assoc:`j_PersonChargeAssociation` {id:'abc123_assoc01'}),
      (person:`nc_Person` {id:'abc123_P01'}),
      (charge:`j_Charge` {id:'abc123_CH01'})
MERGE (assoc)-[:`ASSOCIATED_WITH` {role_qname: 'nc:Person'}]->(person)
MERGE (assoc)-[:`ASSOCIATED_WITH` {role_qname: 'j:Charge'}]->(charge)
```

**UI Styling:**
- Association nodes: Orange hexagons
- `ASSOCIATED_WITH` edges: Thick orange dotted lines

#### 5. Role-Based Entity Modeling (Schema-Agnostic)

**Pattern:** NIEM uses role elements (like `j:CrashDriver`, `j:VehicleOperator`) that reference core entities using `structures:uri`.

**XML Example:**
```xml
<j:CrashDriver structures:uri="#P01">
  <nc:PersonName>...</nc:PersonName>
</j:CrashDriver>
<nc:Person structures:id="P01">...</nc:Person>
```

**Creates:**
1. Entity node (type determined by actual element - Person, Organization, Vehicle, etc.)
2. Role node with synthetic ID
3. `REPRESENTS` relationship from role to entity (label resolved when entity element is encountered)

```cypher
MERGE (e:`nc_Person` {id:'abc123_P01'})  # Entity type determined by actual element
MERGE (r:`j_CrashDriver` {id:'abc123_syn_cd01'})
MERGE (r)-[:`REPRESENTS`]->(e)
```

**JSON Example:**
```json
{
  "j:CrashDriver": {
    "@id": "#P01",
    "nc:PersonName": [...]
  },
  "nc:Person": {
    "@id": "P01",
    ...
  }
}
```
Same graph structure is created! Works with any entity type (Person, Organization, Vehicle, Location, Item, etc.)

#### 6. NIEM Augmentation Handling (Transparent Flattening)

**Critical Concept:** NIEM augmentations are **completely transparent** in the graph - they NEVER appear as nodes.

**What Are Augmentations?**

NIEM augmentations are a mechanism to extend types from other namespaces without modifying the original schema. They consist of three components:

1. **Augmentation Point** - Abstract placeholder element in base type (e.g., `nc:PersonAugmentationPoint`)
2. **Augmentation Type** - Concrete type extending `structures:AugmentationType` (e.g., `j:PersonAugmentationType`)
3. **Augmentation Element** - Instance that substitutes for the augmentation point (e.g., `j:PersonAugmentation`)

**XSD Structure Example:**
```xml
<!-- Base type declares augmentation point -->
<xs:complexType name="PersonType">
  <xs:sequence>
    <xs:element ref="nc:PersonBirthDate" minOccurs="0"/>
    <xs:element ref="nc:PersonAugmentationPoint" minOccurs="0" maxOccurs="unbounded"/>
  </xs:sequence>
</xs:complexType>

<!-- Augmentation point (abstract) -->
<xs:element name="PersonAugmentationPoint" abstract="true"/>

<!-- Augmentation type definition -->
<xs:complexType name="PersonAugmentationType">
  <xs:complexContent>
    <xs:extension base="structures:AugmentationType">
      <xs:sequence>
        <xs:element ref="j:PersonAdultIndicator" minOccurs="0"/>
      </xs:sequence>
    </xs:extension>
  </xs:complexContent>
</xs:complexType>

<!-- Augmentation element (substitutes for augmentation point) -->
<xs:element name="PersonAugmentation"
            type="j:PersonAugmentationType"
            substitutionGroup="nc:PersonAugmentationPoint"/>
```

**Instance Document Example:**
```xml
<nc:Person structures:id="P01">
  <nc:PersonBirthDate>1990-01-01</nc:PersonBirthDate>
  <j:PersonAugmentation>
    <j:PersonAdultIndicator>true</j:PersonAdultIndicator>
  </j:PersonAugmentation>
</nc:Person>
```

**Graph Structure (Augmentation is Invisible):**

Wrong (what you might expect):
```
(:nc_Person) -[:CONTAINS]-> (:j_PersonAugmentation {j_PersonAdultIndicator: "true"})
```

Correct (augmentation is transparent):
```cypher
(:nc_Person {
  id: "P01",
  nc_PersonBirthDate: "1990-01-01",
  j_PersonAdultIndicator: "true",
  j_PersonAdultIndicator_isAugmentation: true
})
```

**Processing Rules:**

1. **Simple Properties**: Flattened directly into parent node properties
   - Path: `nc:Person/j:PersonAugmentation/j:PersonAdultIndicator`
   - Result: Property `j_PersonAdultIndicator` on `nc:Person` node
   - Flat naming (no prefix): `j_PersonAdultIndicator` (not `j_PersonAugmentation_j_PersonAdultIndicator`)

2. **Complex Children**: Direct containment to grandparent (augmentation skipped)
   - Example: `<nc:Person><exch:PersonAugmentation><nc:PersonName>...</nc:PersonName></exch:PersonAugmentation></nc:Person>`
   - Wrong: `nc:Person → exch:PersonAugmentation → nc:PersonName`
   - Correct: `nc:Person → nc:PersonName` (direct containment)

3. **Metadata Marking**: All augmentation properties marked with `_isAugmentation: true`

**Detection Methods:**

- **Mapping Mode**: Uses augmentation index built from XSD schema
  - Identifies elements with `substitutionGroup="*AugmentationPoint"`
  - Verifies type extends `structures:AugmentationType`
  - Auto-includes augmentation properties when base type is selected

- **Dynamic Mode**: Pattern-based detection
  - Any element with qname ending in `Augmentation` (e.g., `j:MetadataAugmentation`)
  - Processed at the very beginning of traverse/process function (before associations/objects)

**Real-World Examples from CrashDriver:**

```xml
<!-- Example 1: Simple property augmentation -->
<nc:Metadata structures:id="MD01">
  <j:MetadataAugmentation>
    <j:CriminalInformationIndicator>true</j:CriminalInformationIndicator>
  </j:MetadataAugmentation>
</nc:Metadata>

<!-- Result: -->
(:nc_Metadata {
  id: "MD01",
  j_CriminalInformationIndicator: "true",
  j_CriminalInformationIndicator_isAugmentation: true
})

<!-- Example 2: Association augmentation -->
<j:PersonChargeAssociation>
  <nc:Person structures:ref="P01"/>
  <j:Charge structures:ref="CH01"/>
  <exch:PersonChargeAssociationAugmentation>
    <nc:Metadata structures:ref="MD01"/>
  </exch:PersonChargeAssociationAugmentation>
</j:PersonChargeAssociation>

<!-- Result: Association node gets reference to Metadata, augmentation is transparent -->
(:j_PersonChargeAssociation) -[:REFERS_TO]-> (:nc_Metadata)
<!-- No exch:PersonChargeAssociationAugmentation node is created -->
```

**Schema Designer Behavior:**

- Augmentations appear in element tree with **orange "augmentation" badge**
- Checkboxes are **disabled** (not selectable)
- Tooltip: "Augmentation - automatically included with base type"
- Properties are auto-included when base type is selected
- Example: Selecting `j:Charge` automatically includes properties from `exch:ChargeAugmentation`

**Key Implementation Points:**

1. **Early Detection** (`xml_to_graph/converter.py:895`, `json_to_graph/converter.py:527`)
   - Augmentations checked FIRST (before associations or objects)
   - Prevents any node creation

2. **Property Flattening** (`xsd_schema_designer.py:220-236`)
   - Augmentation properties merged into base type's scalar_props
   - Path metadata preserved: `j:PersonAugmentation/j:PersonAdultIndicator`
   - Flat Neo4j property names: `j_PersonAdultIndicator`

3. **Mapping Exclusion** (`xsd_schema_designer.py:205-206`)
   - Augmentations skipped in objects mapping
   - Never appear in associations or references mappings

**Why Transparency Matters:**

- Augmentations are a **schema-level construct** for extending types without modification
- In the graph domain, we care about **entities and relationships**, not schema mechanics
- Flattening augmentations into their base types creates cleaner, more queryable graphs
- Users can still identify augmentation properties via `_isAugmentation` metadata if needed

## Part 4: XML vs JSON Converter Implementation

### XML Converter (`xml_to_graph/converter.py`)

**Algorithm:**

1. **Parse XML:**
   ```python
   root = ET.fromstring(xml_content)
   ns_map = parse_ns(xml_content)  # Extract namespace prefixes
   ```

2. **Traverse Tree:**
   ```python
   def traverse(elem, parent_info, path_stack):
       elem_qn = qname_from_tag(elem.tag, ns_map)

       # Check if this is a mapped object
       obj_rule = obj_rules.get(elem_qn)

       # Check for structures:id, structures:ref, structures:uri
       sid = elem.attrib.get(f"{{{STRUCT_NS}}}id")
       ref = elem.attrib.get(f"{{{STRUCT_NS}}}ref")
       uri = elem.attrib.get(f"{{{STRUCT_NS}}}uri")

       # Handle associations
       if elem_qn in associations:
           # Extract role endpoints and create edge

       # Handle objects (nodes)
       if obj_rule or sid or has_metadata_refs:
           # Create node
           node_id = generate_id(sid, uri, parent, path)
           props = collect_scalar_setters(obj_rule, elem, ns_map)
           aug_props = extract_unmapped_properties(elem, ns_map, cmf_index)
           nodes[node_id] = [label, qname, props, aug_props]

           # Create containment edge to parent
           if parent_info:
               contains.append((parent_id, parent_label, node_id, label, rel))

       # Recurse to children
       for child in elem:
           traverse(child, (node_id, label), path_stack)
   ```

3. **Handle References:**
   ```python
   # For each reference rule
   for rule in refs_by_owner[elem_qn]:
       # Find child elements matching field_qname
       for ch in elem:
           if qname_matches(ch, rule["field_qname"]):
               # Check for structures:ref or structures:id
               to_id = ch.attrib.get(f"{{{STRUCT_NS}}}ref") or ch.attrib.get(f"{{{STRUCT_NS}}}id")
               if to_id:
                   edges.append((node_id, owner_label, to_id, target_label, rel_type))
   ```

4. **Generate Cypher:**
   ```python
   # MERGE nodes
   for node_id, (label, qname, props, aug_props) in nodes.items():
       cypher += f"MERGE (n:`{label}` {{id:'{node_id}'}})\n"
       cypher += f"  ON CREATE SET n.qname='{qname}', n.sourceDoc='{filename}'"
       for key, value in props.items():
           cypher += f", n.{key}='{value}'"

   # MERGE containment edges
   for (parent_id, parent_label, child_id, child_label, rel) in contains:
       cypher += f"MATCH (p:`{parent_label}` {{id:'{parent_id}'}}), (c:`{child_label}` {{id:'{child_id}'}})\n"
       cypher += f"MERGE (p)-[:`{rel}`]->(c)\n"

   # MERGE reference/association edges
   for (from_id, from_label, to_id, to_label, rel) in edges:
       cypher += f"MATCH (a:`{from_label}` {{id:'{from_id}'}}), (b:`{to_label}` {{id:'{to_id}'}})\n"
       cypher += f"MERGE (a)-[:`{rel}`]->(b)\n"
   ```

### JSON Converter (`json_to_graph/converter.py`)

**Algorithm:**

1. **Parse JSON:**
   ```python
   data = json.loads(json_content)
   context = data.get("@context", {})  # JSON-LD namespace context
   ```

2. **Traverse Objects:**
   ```python
   def process_jsonld_object(obj, parent_id, parent_label, property_name):
       # Extract @id (like structures:id)
       obj_id = obj.get("@id") or generate_synthetic_id()

       # Extract @type (like xsi:type)
       obj_type = obj.get("@type")

       # Determine QName from @type or property name
       qname = obj_type or property_name

       # Find matching object rule
       obj_rule = obj_rules.get(qname)

       if obj_rule:
           # Extract label and properties
           label = obj_rule.get("label")
           props = extract_properties(obj, obj_rule, context)

           # Create node
           nodes[obj_id] = (label, qname, props, {})

           # Create containment edge if nested
           if parent_id:
               contains.append((parent_id, parent_label, obj_id, label, f"HAS_{property_name}"))

           # Process nested properties
           for key, value in obj.items():
               if key.startswith("@"):
                   continue  # Skip JSON-LD keywords

               if is_reference(value):  # value == {"@id": "..."}
                   # Create reference edge
                   target_id = value["@id"]
                   edges.append((obj_id, label, target_id, None, key))

               elif isinstance(value, dict):
                   # Nested object - recurse
                   process_jsonld_object(value, obj_id, label, key)

               elif isinstance(value, list):
                   # Array of objects or references
                   for item in value:
                       if isinstance(item, dict):
                           if is_reference(item):
                               edges.append((obj_id, label, item["@id"], None, key))
                           else:
                               process_jsonld_object(item, obj_id, label, key)
   ```

3. **Generate Cypher:**
   ```python
   # Same Cypher generation logic as XML!
   cypher = generate_cypher_from_structures(nodes, edges, contains)
   ```

### Key Similarities - Achieving Parity

Both converters now achieve **full parity** and create **identical graphs**:

| Aspect | XML Converter | JSON Converter | Status |
|--------|---------------|----------------|--------|
| **Parsing** | `xml.etree.ElementTree` | `json.loads()` | Different (format-specific) |
| **Namespace Handling** | Extract from `xmlns:` attributes | Use `@context` mapping | Different (format-specific) |
| **ID Extraction** | `structures:id` attribute | `@id` property | Different (format-specific) |
| **Reference Detection** | `structures:ref` + `xsi:nil="true"` | Object with only `@id` key | Different (format-specific) |
| **Association Handling** | Uses `associations[]` mapping | Uses `associations[]` mapping | ✅ **Identical** |
| **Reference Handling** | Uses `references[]` mapping | Uses `references[]` mapping | ✅ **Identical** |
| **Role-Based Modeling** | `structures:uri` → entity + role | `@id="#P01"` → entity + role | ✅ **Identical** |
| **Augmentation Extraction** | `cmf_element_index` check | `cmf_element_index` check | ✅ **Identical** |
| **Scalar Property Extraction** | Nested path traversal | Nested path traversal | ✅ **Identical** |
| **Node Structure** | `[label, qname, props, aug_props]` | `[label, qname, props, aug_props]` | ✅ **Identical** |
| **Cypher Generation** | MERGE with ON CREATE SET | MERGE with ON CREATE SET | ✅ **Identical** |
| **Graph Output** | Neo4j graph structure | Neo4j graph structure | ✅ **Identical** |

### Why They Create the Same Graph

Both converters:

1. ✅ **Use the same `mapping.yaml`** specification
2. ✅ **Follow the same rules** for:
   - Association relationship types (from `associations[]`)
   - Reference relationship types (from `references[]`)
   - Role-based entity modeling (`REPRESENTS`)
   - Node creation and labeling
   - Property extraction (both scalar and augmentation)
3. ✅ **Generate identical Cypher** patterns for nodes and edges
4. ✅ **Preserve the same semantics** (IDs, QNames, properties, relationships)
5. ✅ **Handle edge cases identically** (metadata refs, complex augmentations, synthetic IDs)

The **only differences** are in the **parsing layer** - once parsed, both follow **100% identical mapping logic** and produce **byte-for-byte identical graph structures**.

## Part 5: Validation and Error Handling

### Schema Validation

**XML Validation (XSD):**
```bash
cmftool xval --schema {schemas} --file {instance.xml}
```

**JSON Validation (JSON Schema):**
```python
from jsonschema import Draft7Validator
validator = Draft7Validator(json_schema)
errors = list(validator.iter_errors(data))
```

### Validation Errors

Both validation approaches return structured errors:

```python
{
  "valid": False,
  "errors": [
    {
      "file": "CrashDriver1.xml",
      "line": 42,
      "message": "Element 'PersonName': Missing child element 'PersonSurName'",
      "severity": "error",
      "rule": "required"
    }
  ],
  "warnings": [],
  "summary": "Validation failed with 1 error(s) and 0 warning(s)"
}
```

### Ingestion Errors

If validation fails, ingestion is rejected and **no data is written to Neo4j**.

## Part 6: File Storage and Provenance

### Schema Storage (MinIO)

```
niem-schemas/
  {schema_id}/
    source/
      {filename}.xsd         # Original XSD files (with directory structure)
      niem/
        niem-core.xsd       # NIEM reference schemas
    {primary_schema}.cmf    # Generated CMF document (e.g., CrashDriver.cmf)
    {primary_schema}.json   # Generated JSON Schema (e.g., CrashDriver.json)
    mapping.yaml            # Generated mapping specification
    metadata.json           # Schema metadata
  active_schema.json        # Pointer to active schema
```

### Data Storage (MinIO)

```
niem-data/
  xml/
    {timestamp}_{hash}_{filename}.xml        # Successfully ingested XML files
    {timestamp}_{hash}_{filename}.xml.cypher # Generated Cypher statements
  json/
    {timestamp}_{hash}_{filename}.json       # Successfully ingested JSON files
    {timestamp}_{hash}_{filename}.json.cypher # Generated Cypher statements
```

### Provenance Tracking

Every node created has:
- `sourceDoc`: Original filename (XML or JSON)
- `id`: Prefixed with file hash for multi-file uniqueness
- Stored `.cypher` file shows exact transformation

## Part 7: Common Patterns and Examples

### Pattern 1: Simple Object with Properties

**Mapping:**
```yaml
objects:
  - qname: nc:PersonName
    label: nc_PersonName
    scalar_props:
      - path: nc:PersonGivenName
        neo4j_property: nc_PersonGivenName
      - path: nc:PersonSurName
        neo4j_property: nc_PersonSurName
```

**XML:**
```xml
<nc:PersonName structures:id="PN01">
  <nc:PersonGivenName>John</nc:PersonGivenName>
  <nc:PersonSurName>Doe</nc:PersonSurName>
</nc:PersonName>
```

**JSON:**
```json
{
  "nc:PersonName": {
    "@id": "PN01",
    "nc:PersonGivenName": ["John"],
    "nc:PersonSurName": ["Doe"]
  }
}
```

**Graph:**
```cypher
CREATE (n:`nc_PersonName` {
  id: 'file_PN01',
  qname: 'nc:PersonName',
  nc_PersonGivenName: 'John',
  nc_PersonSurName: 'Doe'
})
```

### Pattern 2: Object References

**Mapping:**
```yaml
references:
  - owner_object: j:DriverLicense
    field_qname: j:DriverLicenseCardIdentification
    target_label: j_DriverLicenseCardIdentification
    rel_type: J_DRIVERLICENSECARDIDENTIFICATION
```

**XML:**
```xml
<j:DriverLicense structures:id="DL01">
  <j:DriverLicenseCardIdentification structures:ref="DLID01"/>
</j:DriverLicense>
<j:DriverLicenseCardIdentification structures:id="DLID01">
  <nc:IdentificationID>A1234567</nc:IdentificationID>
</j:DriverLicenseCardIdentification>
```

**JSON:**
```json
{
  "j:DriverLicense": {
    "@id": "DL01",
    "j:DriverLicenseCardIdentification": {"@id": "DLID01"}
  },
  "j:DriverLicenseCardIdentification": {
    "@id": "DLID01",
    "nc:IdentificationID": "A1234567"
  }
}
```

**Graph:**
```cypher
CREATE (dl:`j_DriverLicense` {id: 'file_DL01'})
CREATE (id:`j_DriverLicenseCardIdentification` {id: 'file_DLID01', nc_IdentificationID: 'A1234567'})
CREATE (dl)-[:`J_DRIVERLICENSECARDIDENTIFICATION`]->(id)
```

### Pattern 3: Associations

**Mapping:**
```yaml
associations:
  - qname: j:PersonChargeAssociation
    rel_type: J_PERSONCHARGEASSOCIATION
    endpoints:
      - role_qname: nc:Person
        maps_to_label: nc_Person
      - role_qname: j:Charge
        maps_to_label: j_Charge
```

**XML:**
```xml
<j:PersonChargeAssociation>
  <nc:Person structures:ref="P01"/>
  <j:Charge structures:ref="CH01"/>
</j:PersonChargeAssociation>
```

**JSON:**
```json
{
  "j:PersonChargeAssociation": {
    "nc:Person": {"@id": "P01"},
    "j:Charge": {"@id": "CH01"}
  }
}
```

**Graph:**
```cypher
MATCH (p:`nc_Person` {id: 'file_P01'}),
      (c:`j_Charge` {id: 'file_CH01'})
CREATE (p)-[:`J_PERSONCHARGEASSOCIATION`]->(c)
```

### Pattern 4: Metadata References

**XML:**
```xml
<j:CrashPersonInjury priv:privacyMetadataRef="PMD01 PMD02">
  <nc:InjuryDescriptionText>Broken Arm</nc:InjuryDescriptionText>
</j:CrashPersonInjury>
<priv:PrivacyMetadata structures:id="PMD01">
  <priv:PrivacyCode>PII</priv:PrivacyCode>
</priv:PrivacyMetadata>
```

**Graph:**
```cypher
CREATE (inj:`j_CrashPersonInjury` {id: 'file_INJ01', nc_InjuryDescriptionText: 'Broken Arm'})
CREATE (pmd:`priv_PrivacyMetadata` {id: 'file_PMD01', priv_PrivacyCode: 'PII'})
CREATE (inj)-[:`HAS_PRIVACYMETADATA`]->(pmd)  # Containment edge captures relationship
```

**Note:** Metadata reference edges are captured via containment relationships (`HAS_PRIVACYMETADATA`, `HAS_METADATA`), not separate reference edges.

## Part 8: Dual-Mode Converter Deep Dive

### Why Two Modes?

**Problem**: CMF tool sometimes excludes extension namespaces (cb_ext, cb_exchange) during XSD→CMF conversion. Without these namespaces in the CMF, they don't appear in mapping.yaml, and the converter would skip those elements entirely.

**Solution**: Two operational modes that automatically adapt based on schema designer state.

### Mode Comparison

| Aspect | Dynamic Mode | Mapping Mode |
|--------|--------------|--------------|
| **Trigger** | No selections.json | selections.json with selections |
| **Node Criteria** | All complex elements | Only elements in mapping |
| **Label Source** | Generated from qname | From mapping.yaml |
| **Namespace Coverage** | ALL namespaces (including extensions) | Only mapped namespaces |
| **Graph Size** | Larger (more nodes) | Smaller (optimized) |
| **Use Case** | Exploration, extension schemas | Production, optimized queries |
| **Configuration** | Zero - automatic | Schema designer selections |

### Dynamic Mode Details

**Complex Element Detection:**
```python
def _is_complex_element(elem, ns_map, struct_ns):
    # 1. Has structures:id or structures:uri? → Node
    if has_structures_attr(elem, "id") or has_structures_attr(elem, "uri"):
        return True

    # 2. Has child elements? → Node
    if len(list(elem)) > 0:
        return True

    # 3. Has non-structural attributes? → Node
    for attr in elem.attrib.keys():
        if not is_structural_attr(attr):
            return True

    # Simple text-only element → Property
    return False
```

**Label Generation:**
- `cb_ext:FollowupReport` → Label: `cb_ext_FollowupReport`
- `cb_exchange:NEICETransmittalDocument` → Label: `cb_exchange_NEICETransmittalDocument`
- `cyfs:ChildSupportEnforcementCase` → Label: `cyfs_ChildSupportEnforcementCase`

**Augmentation Handling:**
In dynamic mode, augmentation detection is disabled (all properties treated as standard) since we can't distinguish CMF schema elements from extensions without the CMF element index.

### Workflow Patterns

**Pattern 1: Extension Schema Exploration**
```
1. Upload NIECE XSD schema → mapping.yaml generated (may miss cb_ext)
2. Ingest FollowupReport.xml → Dynamic mode (no selections.json)
3. Query Neo4j → See ALL elements including cb_ext, cb_exchange
4. Apply schema design → Create selections.json
5. Re-ingest → Mapping mode (controlled structure)
```

**Pattern 2: Standard Schema Production**
```
1. Upload NIEM 6.0 Justice schema → mapping.yaml generated
2. Apply schema design immediately → Create selections.json
3. Ingest CrashDriver.xml → Mapping mode (optimized)
4. Query Neo4j → See only selected elements
```

### Mode Switching

Users can switch between modes without code changes:

```bash
# Start in dynamic mode (no selections)
POST /ingest/xml → Creates ALL complex element nodes

# Apply schema design
POST /schema/apply-design → Creates selections.json

# Now in mapping mode
POST /ingest/xml → Creates only selected nodes

# Remove schema design
DELETE /schema/selections → Removes selections.json

# Back to dynamic mode
POST /ingest/xml → Creates ALL complex element nodes again
```

### Extension Namespace Support

**Previously**: Extension namespaces excluded if CMF tool skipped them
**Now**: Extension namespaces automatically included in dynamic mode

**Example NIECE Schema:**
```xml
<xs:schema targetNamespace="http://cb.acf.hhs.gov/neice/1.0/exchange/">
  <!-- Root element -->
  <xs:element name="NEICETransmittalDocument" type="cb_exch:NEICETransmittalDocumentType"/>
</xs:schema>

<xs:schema targetNamespace="http://cb.acf.hhs.gov/neice/1.0/ext/">
  <!-- Extension elements -->
  <xs:element name="FollowupReport" type="cb_ext:FollowupReportType"/>
</xs:schema>
```

**Dynamic Mode Result:**
```cypher
CREATE (root:cb_exchange_NEICETransmittalDocument {id: 'file_TD01'})
CREATE (report:cb_ext_FollowupReport {id: 'file_FR01'})
CREATE (root)-[:HAS_FOLLOWUPREPORT]->(report)
-- Full connected graph with ALL namespaces
```

### Performance Considerations

**Dynamic Mode**:
- More nodes created (all complex elements)
- Larger graphs (more Cypher statements)
- Slower ingestion (more database writes)
- Better for exploration and data discovery

**Mapping Mode**:
- Fewer nodes created (only selected elements)
- Optimized graphs (efficient queries)
- Faster ingestion (fewer database writes)
- Better for production workloads

**Recommendation**: Use dynamic mode for initial exploration, then apply schema design and switch to mapping mode for production.

## Summary

1. **Schema Upload** → XSD files are validated, converted to CMF, and `mapping.yaml` is auto-generated
2. **Dual-Mode Converter** → Automatic mode detection based on selections.json existence
3. **Mapping is Source of Truth (Mapping Mode)** → The `mapping.yaml` drives node creation when selections exist
4. **Complex Element Detection (Dynamic Mode)** → All complex elements become nodes when no selections exist
5. **Format-Specific Parsing** → XML and JSON parsers handle syntax differences
6. **Unified Mapping Logic** → Both converters apply the same object/association/reference rules
7. **Identical Cypher Output** → Both generate the same Cypher patterns for nodes and edges
8. **Same Graph Structure** → XML and JSON representations of the same data create identical graphs
9. **Validation First** → Documents are validated against schemas before ingestion
10. **Provenance Preserved** → Source filename and transformation details are stored
11. **Extension Namespace Support** → Dynamic mode ensures zero data loss for extension namespaces

## Key Files Reference

| Component | File Path |
|-----------|-----------|
| Schema Upload Handler | `api/src/niem_api/handlers/schema.py` |
| CMF Tool Client | `api/src/niem_api/clients/cmf_client.py` |
| CMF→Mapping Generator | `api/src/niem_api/services/domain/schema/mapping.py` |
| Ingest Handler | `api/src/niem_api/handlers/ingest.py` |
| XML→Graph Converter | `api/src/niem_api/services/domain/xml_to_graph/converter.py` |
| JSON→Graph Converter | `api/src/niem_api/services/domain/json_to_graph/converter.py` |
| Scheval Validator | `api/src/niem_api/services/domain/schema/scheval_validator.py` |
| Schema Resolver | `api/src/niem_api/services/domain/schema/resolver.py` |
| Neo4j Client | `api/src/niem_api/clients/neo4j_client.py` |

## Next Steps

- **Review mapping.yaml:** Check `niem-schemas/{schema_id}/mapping.yaml` to understand your schema's graph structure
- **Test with samples:** Use `/samples/CrashDriver-cmf/` to test XML and JSON ingestion
- **Query the graph:** Use Neo4j Browser to explore ingested data
- **Debug with .cypher files:** Review generated Cypher in MinIO `niem-data/` bucket
