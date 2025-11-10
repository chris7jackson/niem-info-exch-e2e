# Graph Generation Logic — Deep Dive

## Purpose

This document explains the **exact algorithms and logic** used to generate the Neo4j graph from NIEM schemas and instance documents. It complements the [INGESTION_AND_MAPPING.md](./INGESTION_AND_MAPPING.md) guide by focusing on the internal logic rather than usage patterns.

## Executive Summary

### What This Document Covers

This document provides deep technical detail on three critical processes:

1. **CMF → Mapping Generation** (`mapping.py`) - Complete 3-phase algorithm that extracts Classes, Properties, and Datatypes from CMF XML, classifies types (SIMPLE/WRAPPER/COMPLEX), and generates the `mapping.yaml` specification with flattened scalar property paths.

2. **XML/JSON → Cypher Query Generation** (`xml_to_graph/converter.py`, `json_to_graph/converter.py`) - Detailed traversal algorithms showing how both formats parse documents, apply mapping rules, create nodes/edges, detect augmentations, and generate identical Cypher statements.

3. **Graph Structure Design Decisions** - Rationale behind 6 architectural choices including file-prefixed IDs, containment vs reference relationships, role-based person modeling, augmentation prefixing, metadata handling, and conditional association nodes.

### Key Algorithmic Insights

**Mapping Generation - Complex Type Flattening:**
```python
# CMF defines PersonNameType as COMPLEX (2+ children)
"nc:PersonName" → PersonNameType (COMPLEX)
  ├─ "nc:PersonGivenName" → xs:string (SIMPLE)
  └─ "nc:PersonSurName" → xs:string (SIMPLE)

# Recursive flattening generates paths in mapping.yaml:
scalar_props:
  - path: nc:PersonName/nc:PersonGivenName
    neo4j_property: nc_PersonName_nc_PersonGivenName
  - path: nc:PersonName/nc:PersonSurName
    neo4j_property: nc_PersonName_nc_PersonSurName

# Result: Direct property access without intermediate nodes
XML:   <nc:PersonName><nc:PersonGivenName>John</nc:PersonGivenName></nc:PersonName>
Neo4j: {nc_PersonName_nc_PersonGivenName: "John"}
```

**Graph Creation - Unified Logic Across Formats:**
```python
# Both XML and JSON converters follow identical logic:
1. Parse format-specific syntax
   - XML: Extract namespaces, structures:id, structures:ref
   - JSON: Extract @context, @id, detect {"@id": "..."} references

2. Apply same mapping rules
   - obj_rule = obj_rules.get(qname)      # Same lookup
   - assoc_rule = assoc_by_qn.get(qname)  # Same lookup
   - refs = refs_by_owner.get(qname)      # Same lookup

3. Generate identical structures
   - nodes[obj_id] = (label, qname, props, aug_props)  # Same format
   - edges.append((from_id, from_label, to_id, to_label, rel_type, rel_props))

4. Produce identical Cypher
   - MERGE (n:`nc_Person` {id:'file_P01'}) ON CREATE SET n.qname='nc:Person'
   - MATCH (p:`nc_Person` {id:'file_P01'}), (c:`j_CrashDriver` {id:'file_CD01'})
     MERGE (p)-[:J_CRASHDRIVER]->(c)

Result: XML and JSON create byte-for-byte identical graph structures
```

**Graph Design - Semantic Modeling Patterns:**
```cypher
-- Pattern 1: Role-based entity modeling (one entity, multiple roles)
(j:CrashDriver {id: "role_1"})-[:REPRESENTS]->(nc:Person {id: "P01"})
(j:Victim {id: "role_2"})-[:REPRESENTS]->(nc:Person {id: "P01"})
-- Query: MATCH (p:nc_Person)<-[:REPRESENTS]-(role) RETURN p, role

-- Pattern 2: Dual relationship types (structure + semantics)
(j:Crash)-[:CONTAINS]->(j:CrashVehicle)      -- Containment (document structure)
(j:CrashVehicle)-[:J_CRASHDRIVER]->(j:CrashDriver)   -- Reference (domain semantics)

-- Pattern 3: Augmentation property prefixing (schema vs extensions)
CREATE (n:nc_Person {
  nc_PersonGivenName: 'John',                        -- Schema property
  aug_exch_CustomField: 'value'                      -- Extension property
})

-- Pattern 4: File-prefixed IDs (multi-file collision prevention)
CrashDriver1.xml: (n {id: 'abc123_P01'})  -- Different files,
CrashDriver2.xml: (n {id: 'def456_P01'})  -- different nodes
```

### Critical Design Principles

1. **Mapping is Source of Truth** - Single `mapping.yaml` drives both XML and JSON ingestion, ensuring format parity
2. **Semantic Preservation** - Graph structure reflects domain semantics (associations, references), not document syntax
3. **Provenance Tracking** - Every node records its `sourceDoc` and file-prefixed ID for traceability
4. **Extension Support** - Augmentations (`aug_*` prefix) preserve unmapped data without schema modifications
5. **Idempotent Operations** - All Cypher uses MERGE for safe re-ingestion of duplicate data

### Document Structure

The rest of this document provides:
- **Detailed pseudo-code** for all major algorithms
- **Step-by-step walkthroughs** of recursive traversal logic
- **Decision rationale** for each graph design pattern
- **Query examples** demonstrating each pattern in action

## Table of Contents

1. [CMF → Mapping Generation Logic](#cmf--mapping-generation-logic)
2. [XML/JSON → Cypher Query Generation Logic](#xmljson--cypher-query-generation-logic)
3. [Graph Structure Design Decisions](#graph-structure-design-decisions)

---

## CMF → Mapping Generation Logic

**Source:** `api/src/niem_api/services/domain/schema/mapping.py`

The mapping generation is a **3-phase extraction process** from the CMF (Common Model Format) XML document.

### Phase 1: Parse CMF Structure

**Input:** CMF 1.0 XML document (output from `cmftool xsd2cmf`)

**Key CMF Elements Parsed:**

```python
# 1. Namespace Declarations (prefix → URI mappings)
def build_prefix_map(root: ET.Element) -> Dict[str, str]:
    """
    Extract all <cmf:Namespace> elements:

    <Namespace>
      <NamespacePrefixText>nc</NamespacePrefixText>
      <NamespaceURI>https://.../niem-core/6.0/</NamespaceURI>
    </Namespace>

    Returns: {"nc": "https://.../niem-core/6.0/", ...}
    """
```

```python
# 2. Class Definitions (Object Types and Associations)
def parse_classes(root: ET.Element) -> List[Dict[str, Any]]:
    """
    Extract all <cmf:Class> elements:

    <Class structures:id="nc.PersonType">
      <Name>PersonType</Name>
      <Namespace structures:ref="nc"/>
      <SubClassOf structures:ref="structures.ObjectType"/>
      <ChildPropertyAssociation>
        <DataProperty structures:ref="nc.PersonName"/>
        <MinOccursQuantity>0</MinOccursQuantity>
        <MaxOccursQuantity>unbounded</MaxOccursQuantity>
      </ChildPropertyAssociation>
    </Class>

    Returns list of:
    {
      "id": "nc.PersonType",
      "name": "PersonType",
      "namespace_prefix": "nc",
      "subclass_of": "structures.ObjectType",
      "props": [
        {
          "dataProperty": "nc.PersonName",
          "objectProperty": None,
          "min": "0",
          "max": "unbounded"
        }
      ]
    }
    """
```

```python
# 3. ObjectProperty Definitions (Element declarations)
def build_element_to_class(root: ET.Element) -> Dict[str, str]:
    """
    Extract <cmf:ObjectProperty> elements to map element names to their types:

    <ObjectProperty structures:id="nc.Person">
      <Name>Person</Name>
      <Class structures:ref="nc.PersonType"/>
    </ObjectProperty>

    Returns: {"nc.Person": "nc.PersonType"}

    This mapping allows us to determine:
    - Which element name (nc.Person) corresponds to which type definition (nc.PersonType)
    - What role elements reference (important for associations)
    """
```

```python
# 4. DataProperty Index (Property definitions with datatypes)
def build_dataproperty_index(root: ET.Element) -> Dict[str, Dict[str, Any]]:
    """
    Extract <cmf:DataProperty> elements:

    <DataProperty structures:id="nc.PersonName">
      <Name>PersonName</Name>
      <Datatype structures:ref="nc.PersonNameType"/>
      <Namespace structures:ref="nc"/>
    </DataProperty>

    Returns: {
      "nc.PersonName": {
        "id": "nc.PersonName",
        "name": "PersonName",
        "datatype": "nc.PersonNameType",
        "namespace": "nc"
      }
    }
    """
```

```python
# 5. Datatype Classification (Simple vs Complex types)
def build_datatype_index(root: ET.Element) -> Dict[str, Dict[str, Any]]:
    """
    Classify datatypes as SIMPLE, WRAPPER, or COMPLEX:

    <Datatype structures:id="nc.PersonNameType">
      <ChildPropertyAssociation>
        <DataProperty structures:ref="nc.PersonGivenName"/>
      </ChildPropertyAssociation>
      <ChildPropertyAssociation>
        <DataProperty structures:ref="nc.PersonSurName"/>
      </ChildPropertyAssociation>
    </Datatype>

    Classification logic:
    - SIMPLE: Has RestrictionBase, no child properties (e.g., xs:string)
    - WRAPPER: Has exactly 1 child property (unwrap to access value)
    - COMPLEX: Has 2+ child properties (flatten to individual properties)

    Returns: {
      "nc.PersonNameType": {
        "id": "nc.PersonNameType",
        "class": "COMPLEX",
        "child_count": 2,
        "child_props": [...]
      }
    }
    """
```

### Phase 2: Build Mapping Structures

**Algorithm for Objects Section:**

```python
def _build_objects_mapping(
    objects: List[Dict[str, Any]],
    dataprop_index: Dict[str, Dict[str, Any]],
    datatype_index: Dict[str, Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    For each ObjectProperty element in the CMF:

    1. Convert element ID to QName:
       "nc.Person" → "nc:Person"

    2. Convert QName to Neo4j label:
       "nc:Person" → "nc_Person"

    3. Extract scalar properties by flattening nested DataProperty paths:
       - Start with Class's ChildPropertyAssociation list
       - For each DataProperty reference:
         a. Look up the property in dataprop_index
         b. Look up its datatype in datatype_index
         c. If SIMPLE → add as scalar property
         d. If WRAPPER → recurse into single child (path concatenation)
         e. If COMPLEX → recurse into all children (path concatenation)
       - Build dotted path: "nc:PersonName.nc:PersonGivenName"
       - Convert to Neo4j property name: "nc_PersonName_nc_PersonGivenName"

    4. Mark if element carries structures:id (always true for mapped objects)

    Returns: {
      "qname": "nc:Person",
      "label": "nc_Person",
      "carries_structures_id": true,
      "scalar_props": [
        {
          "path": "nc:PersonName/nc:PersonGivenName",
          "neo4j_property": "nc_PersonName_nc_PersonGivenName"
        },
        {
          "path": "nc:PersonName/nc:PersonSurName",
          "neo4j_property": "nc_PersonName_nc_PersonSurName"
        }
      ]
    }
    """
```

**Property Flattening Algorithm:**

```python
def _flatten_property(
    prop_ref: str,
    data_prop: Dict[str, Any],
    dataprop_index: Dict[str, Dict[str, Any]],
    datatype_index: Dict[str, Dict[str, Any]],
    max_depth: int,
    current_depth: int,
    path_prefix: str = ""
) -> List[Dict[str, str]]:
    """
    Recursive algorithm to flatten nested complex types into scalar paths.

    Example: PersonNameType has child properties PersonGivenName and PersonSurName

    Input:
      prop_ref = "nc.PersonName"
      data_prop = {"id": "nc.PersonName", "datatype": "nc.PersonNameType"}
      path_prefix = ""

    Process:
      1. Build path: "" + "nc:PersonName" = "nc:PersonName"
      2. Look up datatype "nc.PersonNameType" in datatype_index
      3. Classification = COMPLEX (has 2+ children)
      4. Recurse into each child:
         a. Child 1: "nc.PersonGivenName"
            - New path_prefix = "nc:PersonName"
            - Datatype = xs:string (SIMPLE)
            - Return: {"path": "nc:PersonName/nc:PersonGivenName"}
         b. Child 2: "nc.PersonSurName"
            - New path_prefix = "nc:PersonName"
            - Datatype = xs:string (SIMPLE)
            - Return: {"path": "nc:PersonName/nc:PersonSurName"}

    Output: [
      {"path": "nc:PersonName/nc:PersonGivenName", "neo4j_property": "nc_PersonName_nc_PersonGivenName"},
      {"path": "nc:PersonName/nc:PersonSurName", "neo4j_property": "nc_PersonName_nc_PersonSurName"}
    ]

    This flattening allows direct access to leaf values without intermediate nodes:
      XML:   <nc:PersonName><nc:PersonGivenName>John</nc:PersonGivenName></nc:PersonName>
      Neo4j: {nc_PersonName_nc_PersonGivenName: "John"}
    """
```

**Algorithm for Associations Section:**

```python
def _build_associations_mapping(
    associations: List[Dict[str, Any]],
    element_to_class: Dict[str, str],
    label_for_class: callable
) -> List[Dict[str, Any]]:
    """
    For each Class with SubClassOf = "nc.AssociationType":

    1. Identify as an association (e.g., j:CrashDriverAssociation)

    2. Extract endpoints from ChildPropertyAssociation with ObjectProperty:
       <Class structures:id="j.CrashDriverAssociationType">
         <SubClassOf structures:ref="nc.AssociationType"/>
         <ChildPropertyAssociation>
           <ObjectProperty structures:ref="j.Crash"/>
           <MinOccursQuantity>1</MinOccursQuantity>
           <MaxOccursQuantity>1</MaxOccursQuantity>
         </ChildPropertyAssociation>
         <ChildPropertyAssociation>
           <ObjectProperty structures:ref="j.CrashDriver"/>
           <MinOccursQuantity>1</MinOccursQuantity>
           <MaxOccursQuantity>unbounded</MaxOccursQuantity>
         </ChildPropertyAssociation>
       </Class>

    3. For each endpoint:
       - role_qname: "j:Crash" or "j:CrashDriver"
       - maps_to_label: Look up target class → "j_Crash" or "j_CrashDriver"
       - direction: First endpoint = "source", second = "target"
       - cardinality: "min..max" (e.g., "1..1", "1..*")

    4. Generate relationship type:
       "j:CrashDriverAssociation" → "J_CRASHDRIVERASSOCIATION" (UPPER_SNAKE_CASE)

    Returns: {
      "qname": "j:CrashDriverAssociation",
      "rel_type": "J_CRASHDRIVERASSOCIATION",
      "endpoints": [
        {
          "role_qname": "j:Crash",
          "maps_to_label": "j_Crash",
          "direction": "source",
          "via": "structures:ref",
          "cardinality": "1..1"
        },
        {
          "role_qname": "j:CrashDriver",
          "maps_to_label": "j_CrashDriver",
          "direction": "target",
          "via": "structures:ref",
          "cardinality": "1..*"
        }
      ]
    }
    """
```

**Algorithm for References Section:**

```python
def _build_references_mapping(
    objects: List[Dict[str, Any]],
    element_to_class: Dict[str, str],
    association_ids: Set[str],
    label_for_class: callable
) -> List[Dict[str, Any]]:
    """
    For each non-association Class:

    1. Iterate through ChildPropertyAssociation entries with ObjectProperty

    2. Filter: Keep only if target class is NOT an association
       (Association relationships are handled separately)

    3. For each object-valued property:
       <Class structures:id="j.CrashVehicleType">
         <ChildPropertyAssociation>
           <ObjectProperty structures:ref="j.CrashDriver"/>
           <MinOccursQuantity>1</MinOccursQuantity>
           <MaxOccursQuantity>unbounded</MaxOccursQuantity>
         </ChildPropertyAssociation>
       </Class>

    4. Create reference rule:
       - owner_object: "j:CrashVehicle" (QName of owning class)
       - field_qname: "j:CrashDriver" (QName of property/field)
       - target_label: Look up target class → "j_CrashDriver"
       - rel_type: Generate from field name → "J_CRASHDRIVER"
       - cardinality: "1..*"

    Returns: {
      "owner_object": "j:CrashVehicle",
      "field_qname": "j:CrashDriver",
      "target_label": "j_CrashDriver",
      "rel_type": "J_CRASHDRIVER",
      "via": "structures:ref",
      "cardinality": "1..*"
    }

    This rule means:
      XML:   <j:CrashVehicle><j:CrashDriver structures:ref="CD01"/></j:CrashVehicle>
      Graph: (j_CrashVehicle)-[:J_CRASHDRIVER]->(j_CrashDriver {id: "CD01"})
    """
```

### Phase 3: Generate Metadata

```python
# Build CMF element index for augmentation detection
cmf_elements = set()
for element in root.findall(".//cmf:ObjectProperty", NS):
    elem_id = element.attrib.get(f"{{{STRUCT_NS}}}id")
    if elem_id:
        cmf_elements.add(to_qname(elem_id))  # Add "nc:Person", "j:Crash", etc.

for element in root.findall(".//cmf:DataProperty", NS):
    elem_id = element.attrib.get(f"{{{STRUCT_NS}}}id")
    if elem_id:
        cmf_elements.add(to_qname(elem_id))

# This index is used to detect augmentations (unmapped elements)
# If an element QName is NOT in this set, it's an augmentation
metadata = {
    "cmf_element_index": sorted(list(cmf_elements))
}
```

**Final mapping.yaml structure:**

```yaml
namespaces: {...}
objects: [...]
associations: [...]
references: [...]
augmentations: []  # Reserved for future
polymorphism:
  strategy: extraLabel
  store_actual_type_property: xsiType
metadata:
  cmf_element_index: [...]  # All known CMF element QNames
```

---

## XML/JSON → Cypher Query Generation Logic

### XML Converter Algorithm

**Source:** `api/src/niem_api/services/domain/xml_to_graph/converter.py`

**High-Level Flow:**

```
XML Document
    ↓
Parse XML + Extract Namespaces
    ↓
Traverse Tree (Depth-First)
    ↓
For Each Element:
    ├─ Is Association? → Extract Endpoints → Create Edge
    ├─ Is Object? → Create Node + Containment Edge
    ├─ Has Reference Rule? → Create Reference Edge
    └─ Recurse to Children
    ↓
Generate Cypher Statements
    ↓
Return (cypher_text, nodes, contains, edges)
```

**Detailed Traversal Algorithm:**

```python
def traverse(elem: ET.Element, parent_info: Tuple[str, str], path_stack: List[ET.Element]):
    """
    Recursive depth-first traversal of XML tree.

    Arguments:
        elem: Current XML element
        parent_info: (parent_node_id, parent_label) or None
        path_stack: List of ancestor elements (for synthetic ID generation)

    State maintained across traversal:
        nodes: Dict[node_id, (label, qname, props, aug_props)]
        edges: List[(from_id, from_label, to_id, to_label, rel_type, rel_props)]
        contains: List[(parent_id, parent_label, child_id, child_label, rel)]
    """

    # Step 1: Determine Element Type
    elem_qn = qname_from_tag(elem.tag, ns_map)  # e.g., "nc:Person"

    # Step 2: Check if Association
    assoc_rule = assoc_by_qn.get(elem_qn)
    if assoc_rule:
        """
        Association Handling:

        <j:CrashDriverAssociation>
          <j:Crash structures:ref="CR01"/>
          <j:CrashDriver structures:ref="CD01"/>
        </j:CrashDriverAssociation>

        Algorithm:
        1. Extract role references from child elements
        2. Match against association endpoints from mapping
        3. Create edge between first two endpoints:
           (j_Crash {id: "CR01"})-[:J_CRASHDRIVERASSOCIATION]->(j_CrashDriver {id: "CD01"})

        4. Check if association should also be a node:
           - Has structures:id? → Make it a node
           - Has metadata references? → Make it a node
           - Otherwise: Just create edge, don't create association node
        """
        role_refs = []
        for ep in assoc_rule["endpoints"]:
            # Find child element matching role QName
            for ch in elem:
                if qname_from_tag(ch.tag, ns_map) == ep["role_qname"]:
                    to_id = ch.attrib.get(f"{{{STRUCT_NS}}}ref")
                    role_refs.append((ep, to_id))
                    break

        # Create edge if both endpoints found
        if len(role_refs) >= 2:
            ep_a, id_a = role_refs[0]
            ep_b, id_b = role_refs[1]
            edges.append((
                f"{file_prefix}_{id_a}",  # Prefix IDs for multi-file uniqueness
                ep_a["maps_to_label"],
                f"{file_prefix}_{id_b}",
                ep_b["maps_to_label"],
                assoc_rule["rel_type"],
                {}
            ))

        # Check if association needs to be a node
        sid = elem.attrib.get(f"{{{STRUCT_NS}}}id")
        has_metadata = bool(get_metadata_refs(elem, ns_map))

        if not (sid or has_metadata):
            # No node needed - just traverse children and return
            for ch in elem:
                traverse(ch, parent_info, path_stack)
            return

        # Fall through to create association as a node...

    # Step 3: Handle Objects (Nodes)
    obj_rule = obj_rules.get(elem_qn)
    sid = elem.attrib.get(f"{{{STRUCT_NS}}}id")
    ref = elem.attrib.get(f"{{{STRUCT_NS}}}ref")
    uri_ref = elem.attrib.get(f"{{{STRUCT_NS}}}uri")
    is_nil = elem.attrib.get(f"{{{XSI_NS}}}nil") == "true"
    has_metadata_refs = bool(get_metadata_refs(elem, ns_map))

    # Step 3a: Check if Reference (not a new node)
    if (ref or uri_ref) and is_nil:
        """
        Reference Handling (XML pattern):

        <j:CrashDriver structures:ref="CD01" xsi:nil="true"/>

        This references an existing node, doesn't create a new one.
        Create containment edge from parent to referenced node:

        (parent)-[:HAS_CRASHDRIVER]->(j_CrashDriver {id: "CD01"})
        """
        target_id = f"{file_prefix}_{ref or uri_ref.lstrip('#')}"

        if parent_info:
            parent_id, parent_label = parent_info
            rel = "HAS_" + local_from_qname(elem_qn).upper()
            contains.append((parent_id, parent_label, target_id, None, rel))

        # Continue to children (though ref/nil typically has none)
        for ch in elem:
            traverse(ch, parent_info, path_stack)
        return

    # Step 3b: Create Node if Matched by Mapping or Has ID
    if obj_rule or sid or has_metadata_refs:
        """
        Node Creation Logic:

        Conditions for creating a node:
        1. Has mapping rule (obj_rule exists)
        2. Has structures:id attribute
        3. Has metadata references (nc:metadataRef or priv:privacyMetadataRef)
        """

        # Determine label
        if obj_rule:
            node_label = obj_rule["label"]  # From mapping
        else:
            node_label = elem_qn.replace(":", "_")  # Default from QName

        # Determine node ID
        if sid:
            # Use structures:id (prefixed for uniqueness)
            node_id = f"{file_prefix}_{sid}"
        elif uri_ref:
            """
            Role-based Entity Modeling (Schema-Agnostic):

            <j:CrashDriver structures:uri="#P01">
              <nc:PersonName>...</nc:PersonName>
            </j:CrashDriver>

            Creates:
            1. j:CrashDriver node with synthetic ID (role node)
            2. Edge: (j:CrashDriver)-[:REPRESENTS]->(entity_id: "P01")
               - Entity label resolved when actual entity element encountered
               - Works with any entity type (Person, Organization, Vehicle, etc.)

            This pattern allows one entity to play multiple roles and is
            schema-agnostic (not hardcoded to nc:Person).
            """
            entity_id = f"{file_prefix}_{uri_ref.lstrip('#')}"

            # DON'T create entity node here - defer to actual entity element in document
            # This allows the pattern to work with any entity type

            # Create role node with synthetic ID
            parent_id = parent_info[0] if parent_info else "root"
            ordinal_path = "/".join([qname_from_tag(e.tag, ns_map) for e in path_stack] + [elem_qn])
            node_id = synth_id(parent_id, elem_qn, ordinal_path, file_prefix)

            # Create role-to-entity relationship with deferred label resolution
            # Label will be resolved when entity node is encountered/created
            edges.append((node_id, node_label, entity_id, None, "REPRESENTS", {}))
        else:
            # Generate synthetic ID (no structures:id or uri)
            parent_id = parent_info[0] if parent_info else "root"
            ordinal_path = "/".join([qname_from_tag(e.tag, ns_map) for e in path_stack] + [elem_qn])
            node_id = synth_id(parent_id, elem_qn, ordinal_path, file_prefix)

        # Step 3c: Hybrid Property Extraction (Schema-Driven + Auto-Extraction)
        """
        This hybrid approach combines the best of both worlds:
        1. Schema-driven flattening via scalar_props (controlled, optimized paths)
        2. Automatic extraction of everything else (no data loss)

        The approach ensures:
        - No duplicates (tracks what scalar_props already extracted)
        - No data loss (captures all CMF elements and augmentations)
        - Clear augmentation marking (_isAugmentation flags)
        - Minimal configuration (only map what needs flattening)
        """
        props = {}
        mapped_child_qnames = set()

        # STEP 1: Extract explicitly mapped scalar properties (schema-driven flattening)
        if obj_rule:
            """
            Scalar Property Extraction (from mapping.yaml):

            What makes something a "scalar property"?
            - Schema analysis in mapping.py classifies datatypes as SIMPLE, WRAPPER, or COMPLEX
            - SIMPLE: Direct values (xs:string, xs:date) → direct property
            - WRAPPER: Single child container → flatten through (unwrap)
            - COMPLEX: Multiple children → flatten all to separate properties

            For each scalar_props entry in mapping:
            {
              "path": "nc:PersonName/nc:PersonGivenName",
              "neo4j_property": "nc_PersonName_nc_PersonGivenName"
            }

            Traverse nested path from current element:
            1. Start at <nc:Person>
            2. Find child <nc:PersonName> (COMPLEX type with 2+ children)
            3. Find child <nc:PersonGivenName> (SIMPLE type: xs:string)
            4. Extract text content: "John"
            5. Add to props: {"nc_PersonName_nc_PersonGivenName": "John"}

            This flattening avoids creating intermediate PersonName nodes.
            """
            setters = collect_scalar_setters(obj_rule, elem, ns_map)
            for key, value in setters:
                props[key] = value

            # Track which direct children were already processed by scalar_props
            # This prevents duplicate extraction in the auto-extraction phase
            for prop_config in obj_rule.get("scalar_props", []) or []:
                path = prop_config["path"]
                if not path.startswith("@"):
                    # Extract first path segment (direct child element)
                    first_segment = path.split("/")[0]
                    mapped_child_qnames.add(first_segment)

        # STEP 2: Auto-extract ALL remaining simple-text children (hybrid approach)
        """
        Automatic Property Extraction:

        This phase captures everything NOT already handled by scalar_props:
        1. CMF elements not in mapping (no data loss)
        2. Augmentation elements (extension data)

        Example with mapping that only includes nc:PersonName/* :

        XML:
        <nc:Person>
          <nc:PersonName>                    ← Handled by scalar_props
            <nc:PersonGivenName>John</nc:PersonGivenName>
            <nc:PersonSurName>Smith</nc:PersonSurName>
          </nc:PersonName>
          <nc:PersonBirthDate>1980-01-01</nc:PersonBirthDate>  ← AUTO-EXTRACTED (CMF, unmapped)
          <exch:CustomField>value</exch:CustomField>            ← AUTO-EXTRACTED (augmentation)
        </nc:Person>

        Result properties:
        {
          # From scalar_props (flattened):
          nc_PersonName_nc_PersonGivenName: "John",
          nc_PersonName_nc_PersonSurName: "Smith",

          # From auto-extraction (CMF element not in mapping):
          nc_PersonBirthDate: "1980-01-01",

          # From auto-extraction (augmentation):
          exch_CustomField: "value",
          exch_CustomField_isAugmentation: true
        }

        Benefits:
        - No data loss: captures all simple-text values
        - No duplicates: skips children already in scalar_props
        - Clear semantics: exact property names, augmentation flags
        - Minimal config: only map what needs special flattening
        """
        aug_props = {}
        for child in elem:
            child_qn = qname_from_tag(child.tag, ns_map)

            # Skip if already extracted via scalar_props (avoid duplication)
            if child_qn in mapped_child_qnames:
                continue

            # Check if child has simple text content (no nested elements)
            if child.text and child.text.strip() and len(list(child)) == 0:
                # Use exact property name (preserve semantic meaning)
                prop_name = child_qn.replace(':', '_')

                # Check if this is an augmentation (extension data not in CMF schema)
                is_aug = cmf_element_index and is_augmentation(child_qn, cmf_element_index)

                if is_aug:
                    # Store as augmentation property with metadata flag
                    aug_props[prop_name] = child.text.strip()
                    aug_props[f"{prop_name}_isAugmentation"] = True
                else:
                    # Store as regular property (CMF element not in mapping)
                    props[prop_name] = child.text.strip()

            # STEP 3: Handle complex augmentation children (nested structures)
            # Attach properties directly to parent node (no orphan Augmentation nodes)
            elif cmf_element_index and is_augmentation(child_qn, cmf_element_index) and len(list(child)) > 0:
                """
                Complex Augmentation Flattening:

                <nc:Person>
                  <cb_exchange:TransmittalSubjectChild>
                    <nc:PersonFullName>Jane Doe</nc:PersonFullName>
                    <nc:PersonBirthDate>1990-01-01</nc:PersonBirthDate>
                  </cb_exchange:TransmittalSubjectChild>
                </nc:Person>

                Creates properties on parent node (NO separate Augmentation nodes):
                {
                  "cb_exchange_TransmittalSubjectChild.nc_PersonFullName": "Jane Doe",
                  "cb_exchange_TransmittalSubjectChild.nc_PersonFullName_isAugmentation": true,
                  "cb_exchange_TransmittalSubjectChild.nc_PersonBirthDate": "1990-01-01",
                  "cb_exchange_TransmittalSubjectChild.nc_PersonBirthDate_isAugmentation": true
                }

                Benefits:
                - NO orphan Augmentation nodes - all data co-located with parent
                - Exact property names preserve semantic meaning
                - Fast queries - no traversals needed
                - Entity resolution enabled - all data available for matching
                """
                # Extract nested properties with dot notation
                nested_props = _extract_all_properties_recursive(child, ns_map)
                for key, value in nested_props.items():
                    # Flatten with exact property names (NO aug_ prefix for semantic clarity)
                    prop_name = f"{child_qn.replace(':', '_').replace('.', '_')}.{key}"
                    aug_props[prop_name] = value
                    # Add augmentation metadata flag for identification
                    aug_props[f"{prop_name}_isAugmentation"] = True

        # Step 3e: Register Node
        if node_id in nodes:
            # Node already exists (e.g., person entity) - merge properties
            nodes[node_id][2].update({k: v for k, v in props.items() if k not in nodes[node_id][2]})
            nodes[node_id][3].update({k: v for k, v in aug_props.items() if k not in nodes[node_id][3]})
        else:
            # New node
            nodes[node_id] = [node_label, elem_qn, props, aug_props]

        # Step 3f: Create Containment Edge
        if parent_info:
            p_id, p_label = parent_info
            rel = "HAS_" + local_from_qname(elem_qn).upper()
            contains.append((p_id, p_label, node_id, node_label, rel))

        # Update parent context for children
        parent_ctx = (node_id, node_label)
    else:
        # No node created - pass through parent context
        parent_ctx = parent_info

    # Step 4: Handle Reference Edges
    if elem_qn in refs_by_owner:
        """
        Reference Edge Creation:

        Mapping rule:
        {
          "owner_object": "j:CrashVehicle",
          "field_qname": "j:CrashDriver",
          "target_label": "j_CrashDriver",
          "rel_type": "J_CRASHDRIVER"
        }

        XML:
        <j:CrashVehicle structures:id="CV01">
          <j:CrashDriver structures:ref="CD01"/>
        </j:CrashVehicle>

        Creates edge:
        (j_CrashVehicle {id: "CV01"})-[:J_CRASHDRIVER]->(j_CrashDriver {id: "CD01"})
        """
        for rule in refs_by_owner[elem_qn]:
            for ch in elem:
                if qname_from_tag(ch.tag, ns_map) == rule["field_qname"]:
                    # Check for structures:ref (traditional) or structures:id (direct child)
                    to_id = ch.attrib.get(f"{{{STRUCT_NS}}}ref") or ch.attrib.get(f"{{{STRUCT_NS}}}id")

                    if to_id and node_id:
                        edges.append((
                            node_id,
                            rule["owner_object"].replace(":", "_"),
                            f"{file_prefix}_{to_id}",
                            rule["target_label"],
                            rule["rel_type"],
                            {}
                        ))

    # Step 5: Recurse to Children
    path_stack.append(elem)
    for ch in elem:
        traverse(ch, parent_ctx, path_stack)
    path_stack.pop()
```

**Cypher Generation:**

```python
def generate_cypher(nodes, contains, edges, filename):
    """
    Generate Cypher statements from collected structures.

    Order of operations:
    1. MERGE all nodes
    2. MERGE containment relationships
    3. MERGE reference/association relationships
    """

    lines = [f"// Generated for {filename}"]

    # 1. MERGE Nodes
    for node_id, (label, qname, props, aug_props) in nodes.items():
        """
        MERGE (n:`nc_Person` {id:'file_P01'})
          ON CREATE SET
            n.qname='nc:Person',
            n.sourceDoc='CrashDriver1.xml',
            n.nc_PersonGivenName='John',
            n.aug_exch_CustomField='value'

        Notes:
        - Use MERGE to avoid duplicates (upsert semantic)
        - ON CREATE SET for provenance and properties
        - Properties with dots use backticks: n.`nc_PersonName.nc_PersonGivenName`
        - Augmentation properties start with "aug_" prefix
        """
        lines.append(f"MERGE (n:`{label}` {{id:'{node_id}'}})")

        setbits = [f"n.qname='{qname}'", f"n.sourceDoc='{filename}'"]

        # Add core mapped properties
        for key, value in sorted(props.items()):
            prop_key = f"`{key}`" if '.' in key else key
            setbits.append(f"n.{prop_key}='{value}'")

        # Add augmentation properties
        for key, value in sorted(aug_props.items()):
            prop_key = f"`{key}`" if '.' in key else key
            if isinstance(value, list):
                # Multiple values stored as JSON array
                json_value = json.dumps(value).replace("'", "\\'")
                setbits.append(f"n.{prop_key}='{json_value}'")
            else:
                escaped_value = str(value).replace("'", "\\'")
                setbits.append(f"n.{prop_key}='{escaped_value}'")

        lines.append("  ON CREATE SET " + ", ".join(setbits) + ";")

    # 2. MERGE Containment Edges
    for (parent_id, parent_label, child_id, child_label, rel) in contains:
        """
        MATCH (p:`j_Crash` {id:'file_CR01'}), (c:`j_CrashVehicle` {id:'file_CV01'})
        MERGE (p)-[:`CONTAINS`]->(c);

        Notes:
        - MATCH both nodes first (must exist)
        - MERGE the relationship to avoid duplicates
        - Relationship type generated from element local name
        """
        lines.append(
            f"MATCH (p:`{parent_label}` {{id:'{parent_id}'}}), "
            f"(c:`{child_label}` {{id:'{child_id}'}}) "
            f"MERGE (p)-[:`{rel}`]->(c);"
        )

    # 3. MERGE Reference/Association Edges
    for (from_id, from_label, to_id, to_label, rel, rel_props) in edges:
        """
        MATCH (a:`j_CrashVehicle` {id:'file_CV01'}), (b:`j_CrashDriver` {id:'file_CD01'})
        MERGE (a)-[:`J_CRASHDRIVER`]->(b);

        Notes:
        - Association edges: Created from association elements
        - Reference edges: Created from reference mapping rules
        - Both use MERGE to avoid duplicate relationships
        """
        lines.append(
            f"MATCH (a:`{from_label}` {{id:'{from_id}'}}), "
            f"(b:`{to_label}` {{id:'{to_id}'}}) "
            f"MERGE (a)-[:`{rel}`]->(b);"
        )

    return "\n".join(lines)
```

### JSON Converter Algorithm

**Source:** `api/src/niem_api/services/domain/json_to_graph/converter.py`

**Key Differences from XML:**

```python
# 1. JSON-LD Context Handling
context = data.get("@context", {})
# Maps prefixes to URIs: {"nc": "https://.../niem-core/6.0/"}

# 2. ID Extraction
obj_id = obj.get("@id")  # Instead of structures:id attribute

# 3. Reference Detection
def is_reference(value):
    """
    JSON references are objects with only @id:
    {"@id": "P01"}

    vs full object:
    {"@id": "P01", "nc:PersonName": {...}}
    """
    return isinstance(value, dict) and "@id" in value and len(value) == 1

# 4. Type Extraction
obj_type = obj.get("@type")  # Instead of xsi:type attribute
```

**Same Mapping Application:**

```python
# Both converters use identical mapping structures:
obj_rule = obj_rules.get(qname)  # Same lookup
assoc_rule = assoc_by_qn.get(qname)  # Same lookup
refs = refs_by_owner.get(qname)  # Same lookup

# Both generate identical node structures:
nodes[obj_id] = (label, qname, props, aug_props)

# Both generate identical edges:
edges.append((from_id, from_label, to_id, to_label, rel_type, rel_props))

# Both generate identical Cypher:
cypher = generate_cypher_from_structures(nodes, edges, contains)
```

**This ensures XML and JSON create identical graphs.**

---

## Graph Structure Design Decisions

### Decision 1: File-Prefixed IDs

**Problem:** Multiple files may use the same structures:id values

**Solution:**
```python
file_prefix = hashlib.sha1(f"{filename}_{time.time()}".encode()).hexdigest()[:8]
node_id = f"{file_prefix}_{structures_id}"
```

**Result:**
- `CrashDriver1.xml` with `P01` → node ID `abc123_P01`
- `CrashDriver2.xml` with `P01` → node ID `def456_P01`
- Different people, different nodes

### Decision 2: Containment vs Reference Relationships

**Containment Relationships (`CONTAINS`):**
- Represent structural parent-child relationships in the document
- Always created when a node is nested inside another node
- Example: `(j:Crash)-[:CONTAINS]->(j:CrashVehicle)`

**Reference Relationships (named from mapping):**
- Represent semantic object-to-object relationships
- Created from `associations[]` and `references[]` mapping rules
- Example: `(j:CrashVehicle)-[:J_CRASHDRIVER]->(j:CrashDriver)`

**Why both?**
- Containment preserves document structure (useful for reconstruction)
- References express domain semantics (useful for querying)

### Decision 3: Role-Based Entity Modeling (Schema-Agnostic)

**Problem:** NIEM uses roles (CrashDriver, Victim, Witness) that reference core entities using `structures:uri`

**Solution:**
```
(j:CrashDriver {id: "role_1"})-[:REPRESENTS]->(nc:Person {id: "P01"})
(j:Victim {id: "role_2"})-[:REPRESENTS]->(nc:Person {id: "P01"})
(j:VehicleOperator {id: "role_3"})-[:REPRESENTS]->(nc:Vehicle {id: "V01"})
```

**Benefits:**
- One entity with core attributes (name, DOB for Person; VIN for Vehicle)
- Multiple role nodes with role-specific attributes (driver license, injury)
- Schema-agnostic pattern works with any entity type (Person, Organization, Vehicle, etc.)
- Query all roles for an entity: `MATCH (e {id: "P01"})<-[:REPRESENTS]-(role) RETURN e, role`

### Decision 4: Hybrid Property Extraction (Schema-Driven + Auto-Extraction)

**Problem:** Need to balance schema control with data completeness - don't lose unmapped CMF elements or augmentations

**Solution: 3-Phase Hybrid Approach**

1. **Scalar Properties (Schema-Driven Flattening)**
   - Configured in mapping.yaml based on CMF datatype analysis (SIMPLE/WRAPPER/COMPLEX)
   - Flattens nested structures (e.g., `nc:PersonName/nc:PersonGivenName`)
   - Provides control over graph schema optimization

2. **Auto-Extraction (Everything Else)**
   - Captures ALL simple-text children not already in scalar_props
   - Ensures no data loss for unmapped CMF elements
   - Automatically detects and marks augmentations

3. **Complex Augmentations (Flattened to Parent)**
   - Nested augmentation structures flattened with dot notation
   - All data co-located on parent node (no orphan Augmentation nodes)

**Example:**
```cypher
-- Given mapping.yaml with only nc:PersonName/* configured:
CREATE (n:nc_Person {
  -- Phase 1: From scalar_props (schema-driven flattening)
  nc_PersonName_nc_PersonGivenName: 'John',
  nc_PersonName_nc_PersonSurName: 'Smith',

  -- Phase 2: Auto-extracted (CMF elements NOT in mapping - no data loss!)
  nc_PersonBirthDate: '1980-01-01',
  nc_PersonFullName: 'John Smith',

  -- Phase 2: Auto-extracted (augmentation - extension data)
  exch_CustomField: 'value',
  exch_CustomField_isAugmentation: true,

  -- Phase 3: Complex augmentation (flattened with dot notation)
  cb_exchange_TransmittalSubjectChild.nc_PersonFullName: 'Jane Doe',
  `cb_exchange_TransmittalSubjectChild.nc_PersonFullName_isAugmentation`: true
})
```

**Key Principles:**
- **Hybrid = Schema-Driven + Auto-Extraction**: Best of both worlds
- **No duplicates**: Tracks what scalar_props already extracted
- **No data loss**: Auto-extracts everything else (CMF + augmentations)
- **No aug_ prefix**: Property names preserve exact semantic meaning
- **Augmentation metadata**: `_isAugmentation: true` flag identifies extension data
- **No orphan nodes**: All data co-located on parent (fast queries, no joins)
- **Minimal configuration**: Only map what needs special flattening

**Benefits:**
- **Zero data loss**: Captures all CMF elements and augmentations automatically
- **Controlled optimization**: Schema-driven flattening where you need it
- **Clear distinction**: Regular vs augmentation properties via flags
- **Entity resolution enabled**: All data available for matching/deduplication
- **Fast queries**: No traversals needed, all data on node
- **Semantic clarity**: Exact property names preserve meaning
- **Minimal config burden**: Only configure paths needing special handling

**Query Examples:**
```cypher
-- Find all nodes with augmentation properties
MATCH (n)
WHERE any(k IN keys(n) WHERE k ENDS WITH '_isAugmentation')
RETURN n

-- Get only augmentation properties from a node
MATCH (n:nc_Person {id: 'P01'})
RETURN [k IN keys(n) WHERE k ENDS WITH '_isAugmentation' |
  replace(k, '_isAugmentation', '') + ': ' + n[replace(k, '_isAugmentation', '')]]
```

### Decision 5: Metadata Relationships via Containment

**Problem:** NIEM metadata references (`nc:metadataRef`, `priv:privacyMetadataRef`) create cross-references

**Decision:** Use containment edges (`HAS_METADATA`, `HAS_PRIVACYMETADATA`) instead of separate metadata reference edges

**Rationale:**
- Metadata is structurally contained in the document
- Containment edges already capture the relationship
- Avoids duplicate edges for the same semantic relationship

### Decision 6: Association Node Creation

**Conditional:** Associations only become nodes if they have:
- `structures:id` attribute (need to reference them)
- Metadata references (carry metadata)

**Otherwise:** Just create the relationship edge without an intermediate node

**Rationale:**
- Most associations are just relationship patterns (no extra data)
- Creating unnecessary nodes increases graph size
- Node created when association carries properties/metadata

### Decision 7: Deferred Entity Type Resolution

**Problem:** Original implementation hardcoded `nc:Person` entity creation when encountering `structures:uri` references

**Old Approach (Hardcoded):**
```python
# When seeing <j:CrashDriver structures:uri="#P01">:
nodes[person_id] = ["nc_Person", "nc:Person", {}, {}]  # Always creates nc:Person
edges.append((node_id, node_label, person_id, "nc_Person", "REPRESENTS_PERSON", {}))
```

**New Approach (Deferred Resolution):**
```python
# When seeing <j:CrashDriver structures:uri="#P01">:
# DON'T create entity node here - defer to actual entity element in document
edges.append((node_id, node_label, entity_id, None, "REPRESENTS", {}))

# Label resolved later when actual entity element encountered:
# <nc:Person structures:id="P01"> OR
# <nc:Organization structures:id="P01"> OR
# <nc:Vehicle structures:id="P01">
```

**Benefits:**
- **Schema portability**: Works across different NIEM domains without code changes
- **Entity agnostic**: Supports Person, Organization, Vehicle, Location, Item, etc.
- **Custom namespace support**: Handles custom entity types from different namespaces
- **Repeatability**: Same ingestion logic works for any NIEM schema

**Label Resolution Mechanism:**
- Existing label resolution logic (lines 640-656 in converter.py) handles `None` labels
- When creating edges, if target label is `None`, MATCH finds node by ID only
- Actual label determined when entity element is processed and node is created

### Decision 8: NIEM Structures Metadata and Reference Handling

**Problem:** NIEM uses three structures namespace attributes for identification and references:
- `structures:id` - Explicit ID assignment
- `structures:ref` - Reference to an element by ID
- `structures:uri` - URI-based identification and reference (can use fragments like `#P01`)

These need to be captured as metadata and used to create reference relationships in the graph.

**Solution: Two-Pass Processing with Metadata Capture**

**Pass 1: ID Collection**
```python
def collect_ids_pass1(elem: Element):
    """
    Collect all elements with structures:id or structures:uri for forward reference resolution.

    Process structures:id:
      <nc:Person structures:id="P01">...</nc:Person>
      → Register: id_registry["file_P01"] = {element, qname, raw_id}

    Process structures:uri (defines identifiable resources):
      <j:CrashDriver structures:uri="#P01">...</j:CrashDriver>
      → Extract fragment: "#P01" → "P01"
      → Register: id_registry["file_P01"] = {element, qname, raw_id, source: 'uri'}

    URI Normalization:
      - Fragment present: "#P01" → "P01"
      - Full URI: "http://example.com/entities/P01" → "P01" (basename)

    Co-referencing:
      - Multiple elements with same URI are valid (NIEM pattern)
      - First occurrence registered, duplicates skipped
      - Example: <j:CrashDriver structures:uri="#P01"> and
                 <j:CrashPerson structures:uri="#P01"> both reference same entity
    """
```

**Pass 2: Graph Creation with Metadata**
```python
# For all nodes (associations and objects):

# 1. Capture structures attributes as node properties
if structures_id:
    props["structures_id"] = structures_id
if structures_uri:
    props["structures_uri"] = structures_uri
if structures_ref:
    props["structures_ref"] = structures_ref

# 2. Create REFERS_TO edges for structures:ref and structures:uri
if structures_ref:
    # Direct reference to an ID
    target_id = f"{file_prefix}_{structures_ref}"
    edges.append((node_id, label, target_id, None, "REFERS_TO", {}))

elif structures_uri:
    # URI reference - extract fragment or basename
    if '#' in structures_uri:
        target_id = f"{file_prefix}_{structures_uri.split('#')[-1]}"
    else:
        # Use last path segment
        target_id = f"{file_prefix}_{basename(structures_uri)}"
    edges.append((node_id, label, target_id, None, "REFERS_TO", {}))
```

**Association Endpoint Resolution (NIEM Type Substitution)**
```python
# Old approach - hardcoded label:
endpoint_label = ep["maps_to_label"]  # Always uses expected type from mapping

# New approach - dynamic resolution:
endpoint_label = None  # Let resolution find actual node label

# Example:
# Mapping expects:        nc:Person
# Actual element is:      j:CrashDriver (concrete type substitution)
# structures:uri="#P01" links them to same entity

# Association edge creation:
edges.append((assoc_node_id, assoc_label, endpoint_id, None, rel_type, edge_props))
#                                                       ^^^^
#                                                  Will be resolved from actual node

# Label Resolution (happens after all nodes created):
for fid, flabel, tid, tlabel, rel, rprops in edges:
    if tlabel is None and tid in nodes:
        tlabel = nodes[tid][0]  # Get actual label from created node
```

**Unresolved References (Placeholder Nodes)**
```python
# After traversal, check for references to non-existent IDs
for source_qn, target_id, context in pending_refs:
    if target_id not in nodes:
        # Parse context to extract expected type
        # Context: "Association j:PersonChargeAssociation endpoint nc:Person"
        # → Expected type: "nc:Person" → Label: "nc_Person"

        # Create placeholder node with correct type
        nodes[target_id] = [
            label,
            role_qname,
            {
                '_unresolved': True,
                '_error': 'Referenced ID not found in document',
                '_context': context,
                '_raw_id': target_id
            },
            {}
        ]
```

**Graph Structure Created:**

```cypher
-- 1. Metadata on all nodes
CREATE (n:j_CrashDriver {
  id: 'file_obj123',
  structures_uri: '#P01',         -- Captured metadata
  nc_PersonGivenName: 'John'
})

CREATE (m:j_CrashPerson {
  id: 'file_obj456',
  structures_uri: '#P01',         -- Same URI (co-referencing)
  j_InjuryDescription: 'Broken Arm'
})

CREATE (a:j_PersonChargeAssociation {
  id: 'file_assoc789',
  structures_id: 'PCA01'          -- Captured metadata
})

CREATE (c:j_Charge {
  id: 'file_CH01',
  structures_id: 'CH01',          -- Captured metadata
  j_ChargeDescription: 'Furious Driving'
})

-- 2. REFERS_TO edges for co-referencing (both refer to same entity)
MATCH (cd:j_CrashDriver {id: 'file_obj123'}),
      (entity {id: 'file_P01'})
MERGE (cd)-[:REFERS_TO]->(entity)

MATCH (cp:j_CrashPerson {id: 'file_obj456'}),
      (entity {id: 'file_P01'})
MERGE (cp)-[:REFERS_TO]->(entity)

-- 3. Association endpoint edges (with dynamic label resolution)
-- Reference in XML: <nc:Person structures:uri="#P01" xsi:nil="true"/>
-- Actual node created: j:CrashDriver with structures:uri="#P01"
-- Label resolved to: j_CrashDriver (not nc_Person!)
MATCH (a:j_PersonChargeAssociation {id: 'file_assoc789'}),
      (cd:j_CrashDriver {id: 'file_P01'})  -- Label resolved from actual node!
MERGE (a)-[:HAS_PERSON]->(cd)

MATCH (a:j_PersonChargeAssociation {id: 'file_assoc789'}),
      (c:j_Charge {id: 'file_CH01'})
MERGE (a)-[:HAS_CHARGE]->(c)
```

**Benefits:**

1. **Complete Provenance**: All three structures attributes captured as metadata
2. **Reference Relationships**: REFERS_TO edges model co-referencing patterns
3. **URI Normalization**: Consistent ID extraction from various URI formats
4. **Type Substitution Support**: Dynamic label resolution handles NIEM substitution groups
5. **Forward References**: Two-pass approach handles references before definitions
6. **Data Quality Tracking**: Placeholder nodes flag unresolved references with metadata

**Query Examples:**

```cypher
-- Find all nodes referencing a specific entity
MATCH (n)-[:REFERS_TO]->(entity {id: 'file_P01'})
RETURN n, entity

-- Find co-referenced entities (multiple nodes pointing to same entity)
MATCH (n)-[:REFERS_TO]->(entity)<-[:REFERS_TO]-(m)
WHERE n <> m
RETURN entity, collect(n) as referencing_nodes

-- Find nodes with unresolved references
MATCH (n)
WHERE n._unresolved = true
RETURN n.id, n._context, n._error

-- Trace structures metadata
MATCH (n)
WHERE n.structures_id IS NOT NULL OR n.structures_uri IS NOT NULL
RETURN n.qname, n.structures_id, n.structures_uri, n.structures_ref
```

---

## Query Examples Demonstrating the Logic

### Query 1: Find All Roles for an Entity

```cypher
MATCH (e {id: 'file_P01'})<-[:REPRESENTS]-(role)
RETURN e.nc_PersonGivenName, e.nc_PersonSurName, labels(role), role
```

**Demonstrates:**
- Role-based entity modeling
- One entity (Person, Organization, Vehicle, etc.), multiple role nodes
- Schema-agnostic pattern works across all entity types

### Query 2: Traverse Document Structure

```cypher
MATCH path = (root:j_Crash)-[:CONTAINS*]->(leaf)
RETURN path
```

**Demonstrates:**
- Containment relationships preserve document hierarchy
- Can reconstruct original document structure

### Query 3: Find Domain Relationships

```cypher
MATCH (vehicle:j_CrashVehicle)-[:J_CRASHDRIVER]->(driver:j_CrashDriver)
RETURN vehicle, driver
```

**Demonstrates:**
- Reference relationships express domain semantics
- Named relationships from mapping make queries intuitive

### Query 4: Find Augmented Data

```cypher
-- Find all nodes with augmentation properties
MATCH (n)
WHERE any(key IN keys(n) WHERE key ENDS WITH '_isAugmentation')
RETURN n, [key IN keys(n) WHERE key ENDS WITH '_isAugmentation' |
  replace(key, '_isAugmentation', '') + ': ' + n[replace(key, '_isAugmentation', '')]]

-- Find specific augmentation property
MATCH (n)
WHERE n.customNamespace_customField_isAugmentation = true
RETURN n.customNamespace_customField AS value
```

**Demonstrates:**
- Augmentation metadata flags (`_isAugmentation`)
- Easy to identify extension data
- Exact property names (semantic clarity)

---

## Summary

### CMF → Mapping Logic

1. **Parse CMF structure** to extract Classes, Properties, Datatypes
2. **Classify** Classes as AssociationType vs ObjectType
3. **Flatten** complex datatypes into scalar property paths
4. **Generate** objects, associations, references sections
5. **Build** CMF element index for augmentation detection

### XML/JSON → Cypher Logic

1. **Parse** format-specific structure (XML tree or JSON objects)
2. **Traverse** document structure recursively
3. **Apply mapping rules** to determine nodes and relationships
4. **Extract properties** using scalar_props paths
5. **Detect augmentations** using CMF element index
6. **Generate Cypher** with MERGE statements for idempotency

### Key Principles

- **Mapping is source of truth**: Same mapping drives both XML and JSON
- **Format parity**: Both converters produce identical graphs
- **Semantic preservation**: Graph structure reflects domain semantics, not syntax
- **Provenance tracking**: Every node knows its source
- **Extension support**: Augmentations preserve unmapped data

---

## File References

| Logic Component | Source File |
|----------------|-------------|
| CMF → Mapping Generation | `api/src/niem_api/services/domain/schema/mapping.py` |
| XML → Cypher Conversion | `api/src/niem_api/services/domain/xml_to_graph/converter.py` |
| JSON → Cypher Conversion | `api/src/niem_api/services/domain/json_to_graph/converter.py` |
| Graph Schema Management | `api/src/niem_api/services/domain/graph/schema_manager.py` |
| CMF Tool Client | `api/src/niem_api/clients/cmf_client.py` |

For usage and integration information, see [INGESTION_AND_MAPPING.md](./INGESTION_AND_MAPPING.md).
