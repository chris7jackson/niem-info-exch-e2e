# CrashDriver Test Fixtures

## Overview

This directory contains the official NIEM 6.0 CrashDriver test samples and schema for comprehensive converter testing.

**Source**: CrashDriver-Repo (NIEM Architecture Sample Data)
**NIEM Version**: 6.0
**Purpose**: Real-world test data for XML/JSON to Graph conversion

## Directory Structure

```
crashdriver/
├── README.md (this file)
├── examples/           # Instance documents (XML and JSON)
│   ├── msg1.xml, msg1.json
│   ├── msg2.xml, msg2.json
│   ├── msg3.xml, msg3.json
│   ├── msg4.xml, msg4.json
│   └── msg5.xml, msg5.json
└── schema/            # NIEM XSD schema files
    ├── CrashDriver.xsd              # Main exchange schema
    ├── PrivacyMetadata.xsd          # Privacy metadata schema
    └── niem/                        # NIEM reference schemas
        ├── niem-core.xsd
        ├── domains/ (justice.xsd, hs.xsd)
        ├── adapters/ (niem-gml.xsd)
        ├── utility/ (structures.xsd)
        └── external/ (GML 3.2.1)
```

## Example Files Description

### msg1.xml / msg1.json (Basic Example)
**Size**: 74 lines XML, 85 lines JSON
**Features Tested**:
- Basic object references using `structures:uri="#P01"` (NIEM 6.0 style)
- Person with multiple middle names (ordered properties)
- Driver license with nested identification
- Charge with felony indicator
- PersonChargeAssociation (hypergraph pattern)
- Metadata with structures:id and references
- Augmentations (PersonAugmentation, ChargeAugmentation)
- Geospatial coordinates (nested 4 levels deep)

**Key NIEM Elements**:
- j:Crash, j:CrashVehicle, j:CrashDriver, j:CrashPerson
- nc:Person, nc:PersonName, nc:PersonBirthDate
- j:Charge, j:ChargeDescriptionText
- j:DriverLicense, j:DriverLicenseCardIdentification
- j:PersonChargeAssociation (with j:JuvenileAsAdultIndicator)
- nc:Metadata, priv:PrivacyMetadata

**Best For Testing**:
- Property flattening (PersonName, BirthDate, nested identification)
- Hub pattern (Person P01 has 2 roles: CrashDriver and CrashPerson)
- Association endpoints (Person-Charge link)
- structures:id/uri/ref handling
- Augmentation flattening

### msg2.xml / msg2.json (Multiple Persons & Associations)
**Size**: 109 lines XML, 146 lines JSON
**Features Tested**:
- Multiple person objects (P01, P02, P03)
- Multiple association types:
  - j:PersonChargeAssociation (person-to-charge)
  - nc:PersonUnionAssociation (marriage between P01 and P02)
  - hs:PersonOtherKinAssociation (butler P03 to employer P01)
- Reference objects pattern (exch:ReferenceObjects section)
- Date variations (full Date vs YearDate)
- nil elements for reference-only structures

**Best For Testing**:
- Multiple associations in one document
- Different association types (binary and n-ary)
- Cross-person relationships
- Reference object handling
- Complex relationship graphs

### msg3.xml / msg3.json (Privacy Metadata & Reference Attributes)
**Size**: 89 lines XML, 117 lines JSON
**Features Tested**:
- Privacy metadata on data elements
- Reference attributes on simple content: `priv:privacyMetadataRef="PMD02"`
- Multiple privacy classifications (PII, MEDICAL, RESTRICTED)
- Augmentation on simple content elements
- Metadata relationships

**Best For Testing**:
- Privacy metadata handling
- Reference attributes (not just reference elements)
- Simple content with metadata
- Privacy code extraction

### msg4.xml / msg4.json (GML Adapter - External Namespace)
**Size**: 75 lines XML, 88 lines JSON
**Features Tested**:
- External namespace adapter pattern (GML for geospatial)
- `niem-gml:LocationGeospatialPointAdapter`
- GML external schema: `gml:Point`, `gml:pos`
- SRS name handling: `srsName="urn:ogc:def:crs:EPSG::4326"`
- Adapter to NIEM bridging

**Best For Testing**:
- External adapter handling
- Non-NIEM namespace integration
- Geospatial coordinate processing
- External schema imports

### msg5.xml / msg5.json (Relationship Properties)
**Size**: 80 lines XML, 98 lines JSON
**Features Tested**:
- Relationship properties: `priv:privacyRelationCode="RESTRICTED"`
- Multiple PersonName elements for same person (alias pattern)
- Relationship-level metadata vs object-level metadata

**Best For Testing**:
- Relationship properties (attributes on references)
- Alias handling (2+ names for same person)
- Privacy at relationship level

## Schema Files Description

### CrashDriver.xsd (Main Exchange Schema)
- 9 complex types
- 9 element declarations
- Augmentation types for: Charge, Injury, Person, PersonChargeAssociation, PersonName
- Custom types: PersonFictionalGenreCodeType, ReferenceObjectType

### NIEM Reference Schemas
- **niem-core.xsd**: 83 core elements (Person, Organization, Location, etc.)
- **justice.xsd**: 52 justice domain elements (Crash, Charge, Driver, etc.)
- **hs.xsd**: 17 human services elements (PersonOtherKinAssociation, etc.)
- **structures.xsd**: 7 NIEM structure utilities (id, ref, uri attributes)
- **niem-gml.xsd**: 4 GML adapter elements
- **gml.xsd**: External geospatial schema (GML 3.2.1)

**Total**: ~200 elements across all schemas

## Usage in Tests

### Loading Examples

```python
import pytest
from pathlib import Path

@pytest.fixture
def crashdriver_fixtures_dir():
    """Path to CrashDriver test fixtures."""
    return Path(__file__).parent.parent / "fixtures" / "crashdriver"

@pytest.fixture
def msg1_xml(crashdriver_fixtures_dir):
    """Load msg1.xml content."""
    with open(crashdriver_fixtures_dir / "examples" / "msg1.xml") as f:
        return f.read()

@pytest.fixture
def msg1_json(crashdriver_fixtures_dir):
    """Load msg1.json content."""
    with open(crashdriver_fixtures_dir / "examples" / "msg1.json") as f:
        return f.read()
```

### Using in Tests

```python
def test_msg1_converts_successfully(msg1_xml, crashdriver_mapping):
    """Test that msg1.xml converts without errors."""
    cypher, nodes, contains, edges = generate_for_xml_content(
        msg1_xml, crashdriver_mapping, "msg1.xml"
    )

    assert len(nodes) > 0
    assert len(edges) > 0
```

## Test Recommendations by Sample

| Sample | Test Category | Recommended Test Files |
|--------|---------------|------------------------|
| msg1.xml | Property flattening, basic refs | test_converter_property_flattening.py |
| msg1.xml | Hub pattern (2 roles, 1 person) | test_converter_relationships.py |
| msg1.xml | Augmentations | test_converter_augmentation.py |
| msg2.xml | Multiple associations | test_converter_relationships.py |
| msg2.xml | Reference objects | test_converter_references.py |
| msg3.xml | Privacy metadata | test_converter_metadata.py |
| msg4.xml | External adapters | test_converter_adapters.py |
| msg5.xml | Relationship properties | test_converter_relationships.py |
| All msg* | XML/JSON parity | test_converter_format_parity.py |

## Notes

- **XML and JSON pairs**: Each msgX.xml has equivalent msgX.json for format parity testing
- **Official NIEM samples**: These are the canonical NIEM 6.0 architecture test cases
- **Complete schema**: All NIEM dependencies included for standalone testing
- **No modifications**: Files copied as-is from CrashDriver-Repo

**Last Updated**: 2024-11-08
