# XML/JSON Converter Behavior Documentation

## Purpose

This document describes the actual behavior of the XML and JSON to Graph converters based on empirical testing with real NIEM CrashDriver samples. Use this as the specification for unit tests.

**Last Updated**: 2024-11-08
**Tested With**: msg1.xml, msg2.xml from CrashDriver-Repo

---

## Dynamic Mode Behavior (No Schema/Mapping)

### Node Creation Rules

**Rule 1: All Complex Elements → Separate Nodes**

In dynamic mode (no selections.json), the converter creates a **separate node** for every complex element, not flattened properties.

**Example from msg1.xml**:
```xml
<j:CrashDriver structures:uri="#P01">
  <nc:PersonBirthDate>
    <nc:Date>1890-05-04</nc:Date>
  </nc:PersonBirthDate>
  <nc:PersonName>
    <nc:PersonGivenName>Peter</nc:PersonGivenName>
    <nc:PersonSurName>Wimsey</nc:PersonSurName>
  </nc:PersonName>
  <j:PersonAdultIndicator>true</j:PersonAdultIndicator>
</j:CrashDriver>
```

**Results in 3 separate nodes** (NOT flattened):

**Node 1: j_CrashDriver**
```json
{
  "label": "j_CrashDriver",
  "properties": {
    "qname": "j:CrashDriver",
    "structures_uri": "#P01",
    "_isRole": true,
    "j_PersonAdultIndicator": "true",
    "j_PersonAdultIndicator_isAugmentation": true,
    "exch_PersonFictionalCharacterIndicator": "true"
  }
}
```

**Node 2: nc_PersonBirthDate**
```json
{
  "label": "nc_PersonBirthDate",
  "properties": {
    "qname": "nc:PersonBirthDate",
    "nc_Date": "1890-05-04"
  }
}
```

**Node 3: nc_PersonName**
```json
{
  "label": "nc_PersonName",
  "properties": {
    "qname": "nc:PersonName",
    "nc_PersonGivenName": "Peter",
    "nc_PersonSurName": "Wimsey",
    "nc_PersonMiddleName": "Bredon",
    "nc_PersonNameSalutationText": "Lord Peter"
  }
}
```

**Connected via CONTAINS relationships**:
```
(CrashDriver)-[:CONTAINS]->(PersonBirthDate)
(CrashDriver)-[:CONTAINS]->(PersonName)
```

---

### Property Placement Rules

**Rule 2: Properties Go on Immediate Parent Node**

Simple text elements and attributes become properties on their **immediate parent node**.

**Examples**:
- `<nc:PersonGivenName>Peter</nc:PersonGivenName>` → property on **PersonName node**
- `<nc:Date>1890-05-04</nc:Date>` → property on **PersonBirthDate node**
- `<j:PersonAdultIndicator>true</j:PersonAdultIndicator>` → property on **CrashDriver node**

**NOT flattened** with path delimiters like `nc_PersonName__nc_PersonGivenName`.

---

### ID Prefixing Rules

**Rule 3: File Hash Prefix on All IDs**

Every node ID gets prefixed with the file hash (SHA-256, first 8 chars).

**Pattern**: `{file_hash}_{original_id}`

**Examples from msg1.xml** (hash: `3514ad85`):
- Element with structures:id="CH01" → `3514ad85_CH01`
- Element with structures:id="JMD01" → `3514ad85_JMD01`
- Element with structures:id="P01" → `3514ad85_hub_P01` (hub node)
- Element without structures:id → `3514ad85_syn_{synthetic_hash}`

**Benefit**: Prevents ID collisions across multiple files

---

### Hub Pattern (Co-Referencing)

**Rule 4: 2+ Roles → Hub Node + REPRESENTS Edges**

When 2 or more elements reference the same entity via `structures:uri`, a **hub node** is created.

**Example from msg1.xml**:
```xml
<j:CrashDriver structures:uri="#P01">...</j:CrashDriver>
<j:CrashPerson structures:uri="#P01">...</j:CrashPerson>
```

**Creates**:
1. **2 Role Nodes** (marked with `_isRole`: true):
   - `j_CrashDriver` with `structures_uri`: "#P01"
   - `j_CrashPerson` with `structures_uri`: "#P01"

2. **1 Hub Node**:
   ```json
   {
     "label": "Entity_P01",
     "properties": {
       "_isHub": true,
       "entity_id": "P01",
       "uri_value": "#P01",
       "role_count": "2",
       "role_types": "['j:CrashDriver', 'j:CrashPerson']"
     }
   }
   ```

3. **REPRESENTS Relationships**:
   ```
   (j_CrashDriver)-[:REPRESENTS]->(Entity_P01)
   (j_CrashPerson)-[:REPRESENTS]->(Entity_P01)
   ```

---

### Association Handling

**Rule 5: Association Elements → Association Nodes**

Elements with "Association" in the name or AssociationType base become special nodes.

**Example from msg1.xml**:
```xml
<j:PersonChargeAssociation>
  <nc:Person structures:ref="P01"/>
  <j:Charge structures:ref="CH01"/>
  <j:JuvenileAsAdultIndicator>false</j:JuvenileAsAdultIndicator>
</j:PersonChargeAssociation>
```

**Creates Association Node**:
```json
{
  "label": "j_PersonChargeAssociation",
  "properties": {
    "_isAssociation": true,
    "j_JuvenileAsAdultIndicator": "false"
  }
}
```

**With ASSOCIATED_WITH Edges**:
```
(j_PersonChargeAssociation)-[:ASSOCIATED_WITH {role_qname: "nc:Person"}]->(Entity_P01)
(j_PersonChargeAssociation)-[:ASSOCIATED_WITH {role_qname: "j:Charge"}]->(j_Charge)
```

---

### Augmentation Handling

**Rule 6: Augmentation Properties Marked with Flag**

Augmentation elements don't create separate nodes - their properties are added to the parent with `_isAugmentation` flag.

**Example from msg1.xml**:
```xml
<j:CrashDriver>
  <j:PersonAugmentation>
    <j:PersonAdultIndicator>true</j:PersonAdultIndicator>
  </j:PersonAugmentation>
</j:CrashDriver>
```

**Results in CrashDriver node properties**:
```json
{
  "j_PersonAdultIndicator": "true",
  "j_PersonAdultIndicator_isAugmentation": true
}
```

**No separate PersonAugmentation node created.**

**Extension Properties** (non-schema):
```json
{
  "exch_PersonFictionalCharacterIndicator": "true"
}
```
(No augmentation flag - it's an extension property, not augmentation)

---

## Test Implications

### What to Test

#### 1. Node Creation Tests
- ✅ Verify complex elements create separate nodes (nc_PersonName, nc_PersonBirthDate)
- ✅ Verify node labels match qname pattern (j_CrashDriver, nc_PersonName)
- ✅ Verify all system properties added (_upload_id, _schema_id, qname, id)
- ❌ Don't test for flattened properties in dynamic mode

#### 2. Property Placement Tests
- ✅ Verify properties on correct parent node (nc_PersonGivenName on PersonName node)
- ✅ Verify direct child properties (j_PersonAdultIndicator on CrashDriver)
- ✅ Verify array properties (nc_PersonMiddleName could be array if multiple)
- ✅ Verify boolean values preserved as strings ("true", "false")

#### 3. ID Prefixing Tests
- ✅ Verify file hash prefix on all IDs
- ✅ Verify structures:id preserved: `{hash}_CH01`
- ✅ Verify synthetic IDs: `{hash}_syn_{hash}`
- ✅ Verify hub IDs: `{hash}_hub_{entity_id}`
- ✅ Verify same ID in different files → different prefixed IDs

#### 4. Hub Pattern Tests
- ✅ Verify hub node created for 2+ roles
- ✅ Verify hub properties (_isHub, entity_id, role_count, role_types)
- ✅ Verify role nodes marked (_isRole: true)
- ✅ Verify REPRESENTS edges from roles to hub
- ✅ Verify single occurrence doesn't create hub

#### 5. Association Tests
- ✅ Verify association nodes created
- ✅ Verify _isAssociation flag set
- ✅ Verify association properties preserved
- ✅ Verify ASSOCIATED_WITH edges to endpoints
- ✅ Verify edge properties (role_qname)

#### 6. Augmentation Tests
- ✅ Verify augmentation properties on parent node
- ✅ Verify _isAugmentation flag on augmented properties
- ✅ Verify no separate augmentation nodes created
- ✅ Verify extension properties added without flag

#### 7. Relationship Tests
- ✅ CONTAINS: parent-child document structure
- ✅ REPRESENTS: role → hub entity
- ✅ ASSOCIATED_WITH: association → endpoints
- ✅ REFERS_TO: structures:ref references (if applicable)

---

## Key Findings Summary

| Aspect | Dynamic Mode Behavior |
|--------|----------------------|
| **Complex Elements** | Separate nodes (NOT flattened) |
| **Simple Properties** | On immediate parent node |
| **ID Prefixing** | `{file_hash}_{id}` or `{file_hash}_syn_{hash}` |
| **Hub Pattern** | Created for 2+ roles with same structures:uri |
| **Associations** | Separate nodes with _isAssociation flag |
| **Augmentations** | Properties on parent with _isAugmentation flag |
| **Extension Properties** | Added to node, no special flag |

---

## Mapping Mode Behavior (With Schema/selections.json)

**TODO**: Test and document mapping mode behavior where selected elements become nodes and unselected elements are flattened as properties.

**Expected Differences**:
- Only selected elements → nodes
- Unselected complex elements → flattened properties with path delimiters
- Property names: `nc_PersonName__nc_PersonGivenName` (double underscore)

---

## Sample Data Details

### msg1.xml Created Nodes (19 total)

1. **exch_CrashDriverInfo** - Root element
2. **j_Crash** - Crash event
3. **nc_ActivityDate** - Crash date (nc_Date: "1907-05-04")
4. **nc_ActivityLocation** - Crash location
5. **nc_Location2DGeospatialCoordinate** - Geospatial wrapper
6. **nc_GeographicCoordinateLatitude** - Latitude (nc_LatitudeDegreeValue: "51.87")
7. **nc_GeographicCoordinateLongitude** - Longitude (nc_LongitudeDegreeValue: "-1.28")
8. **j_CrashVehicle** - Vehicle in crash
9. **j_CrashDriver** - Driver role (_isRole: true, structures_uri: "#P01")
10. **nc_PersonBirthDate** - Birth date (nc_Date: "1890-05-04")
11. **nc_PersonName** - Name (nc_PersonGivenName: "Peter", etc.)
12. **j_DriverLicense** - License
13. **j_DriverLicenseCardIdentification** - ID card (nc_IdentificationID: "A1234567")
14. **j_CrashPerson** - Person role (_isRole: true, structures_uri: "#P01")
15. **j_CrashPersonInjury** - Injury (j_InjurySeverityCode: "3", nc_InjuryDescriptionText: "Broken Arm")
16. **j_Charge** - Charge (structures_id: "#CH01")
17. **nc_Metadata** - Justice metadata (structures_id: "#JMD01")
18. **j_PersonChargeAssociation** - Association (_isAssociation: true)
19. **Entity_P01** - Hub node (_isHub: true, role_count: "2")

### Relationship Count (21 total)

Expected relationship types:
- CONTAINS (parent-child structure)
- REPRESENTS (role → hub)
- ASSOCIATED_WITH (association → endpoints)
- Possibly REFERS_TO (for structures:ref)

---

## Use This for Test Assertions

When writing tests, assert:
- ✅ Node count: 19 nodes from msg1.xml in dynamic mode
- ✅ Relationship count: 21 relationships
- ✅ Specific nodes exist with expected properties
- ✅ Relationships connect correct nodes
- ✅ Flags set correctly (_isHub, _isRole, _isAssociation, _isAugmentation)
