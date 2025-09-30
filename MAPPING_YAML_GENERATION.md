# Mapping YAML Generation Process

This document explains how the `mapping.yaml` file is generated from NIEM XSD schemas, including the special handling for CrashDriver schemas.

## Overview

The mapping YAML generation is a multi-step process that converts NIEM XSD schemas into a standardized graph mapping format used for Neo4j ingestion. The process involves:

1. **XSD Upload** → **CMF Conversion** → **Mapping YAML Generation**
2. **Special Case**: CrashDriver schemas use pre-existing CMF files instead of conversion

## Code Flow

### 1. Schema Upload (`api/src/niem_api/handlers/schema.py`)

**Entry Point**: `/api/schema/xsd` endpoint
- Receives XSD files via multipart upload
- Validates NIEM NDR compliance
- Extracts primary schema file (first uploaded file)

### 2. CMF Conversion (`api/src/niem_api/services/cmf_tool.py`)

**Function**: `convert_xsd_to_cmf(xsd_content, source_dir, primary_filename)`

**Normal Flow**:
```python
# Standard XSD → CMF conversion using CMF tool
result = run_cmf_command(
    ["x2m", "-o", str(cmf_file), str(main_schema_file)],
    working_dir=str(source_dir)
)
```

**CrashDriver Override**:
```python
# Special handling for CrashDriver schema (lines 142-161)
if primary_filename.lower() == "crashdriver.xsd":
    logger.info("*** DETECTED CRASHDRIVER SCHEMA - USING PRE-EXISTING CMF FILE ***")
    try:
        crashdriver_cmf_path = Path("/app/third_party/niem-crashdriver/crashdriverxsd.cmf")
        if crashdriver_cmf_path.exists():
            with open(crashdriver_cmf_path, 'r', encoding='utf-8') as f:
                cmf_content = f.read()

            return {
                "status": "success",
                "cmf_content": cmf_content,
                "message": "Using pre-existing CrashDriver CMF file"
            }
```

### 3. Mapping Generation (`api/src/niem_api/services/cmf_to_mapping.py`)

**Function**: `generate_mapping_from_cmf_content(cmf_content: str) -> dict`

**Process**:
1. Parse CMF XML content
2. Extract namespace information
3. Build class hierarchy and relationships
4. Generate mapping structure

**Key Components**:
```python
def generate_mapping_from_cmf_content(cmf_content: str) -> dict:
    root = ET.fromstring(cmf_content)
    return _generate_mapping_from_root(root)

def _generate_mapping_from_root(root: ET.Element) -> dict:
    prefixes_all = build_prefix_map(root)           # Extract namespaces
    classes = parse_classes(root)                   # Parse object types
    class_index = {c["id"]: c for c in classes}     # Index classes
    element_to_class = build_element_to_class(root) # Map elements to classes

    # Build mapping structure
    objects = build_objects_list(classes, prefixes_all)
    associations = build_associations_list(root, prefixes_all, class_index, element_to_class)
    references = build_references_list(root, prefixes_all, class_index, element_to_class)
    augmentations = build_augmentations_list(root, prefixes_all, class_index)

    return {
        "namespaces": {prefix: uri for prefix, uri in prefixes_all.items()},
        "objects": objects,
        "associations": associations,
        "references": references,
        "augmentations": augmentations,
        "polymorphism": {
            "strategy": "extraLabel",
            "store_actual_type_property": "xsiType"
        }
    }
```

## CrashDriver Example

### Input CMF File
- **Source**: `/app/third_party/niem-crashdriver/crashdriverxsd.cmf`
- **Size**: 221,355 characters
- **Content**: Pre-generated CMF model for CrashDriver schema

### Generated Mapping Structure

```yaml
namespaces:
  exch: http://example.com/CrashDriver/1.2/
  hs: https://docs.oasis-open.org/niemopen/ns/model/domains/humanServices/6.0/
  j: https://docs.oasis-open.org/niemopen/ns/model/domains/justice/6.0/
  nc: https://docs.oasis-open.org/niemopen/ns/model/niem-core/6.0/
  priv: http://example.com/PrivacyMetadata/2.0/

objects:
- qname: exch:CrashDriverInfo
  label: exch_CrashDriverInfo
  carries_structures_id: true
  scalar_props: []
# ... 24 more objects

associations:
- qname: hs:ParentChildAssociation
  rel_type: HS_PARENTCHILDASSOCIATION
  endpoints:
  - role_qname: hs:Child
    maps_to_label: hs_Child
    direction: source
    via: structures:ref
    cardinality: 0..unbounded
# ... 3 more associations

references:
- owner_object: exch:CrashDriverInfo
  field_qname: j:Crash
  target_label: j_Crash
  rel_type: J_CRASH
  via: structures:ref
  cardinality: 1..1
# ... 15 more references
```

### Output Statistics
- **Total Length**: 7,641 characters
- **Namespaces**: 5
- **Objects**: 25
- **Associations**: 4
- **References**: 16
- **Augmentations**: 0

## Comparison: CMF Tool vs Pre-existing

### CMF Tool Generated (Wrong)
- **Size**: 424,054 characters
- **Mapping**: 1,101 characters, minimal structure
- **Objects**: 1 object only
- **Associations**: 0
- **References**: 0

### Pre-existing CMF (Correct)
- **Size**: 221,355 characters
- **Mapping**: 7,641 characters, rich structure
- **Objects**: 25 objects
- **Associations**: 4 associations
- **References**: 16 references

## File Locations

### Source Files
- **CMF Tool**: `/app/third_party/niem-cmf/cmftool-1.0-alpha.8/bin/cmftool`
- **Pre-existing CMF**: `/app/third_party/niem-crashdriver/crashdriverxsd.cmf`
- **Expected Mapping**: `/Users/cjackson/Workspace/GraphRAG/niem-info-exch-e2e/third_party/niem-crashdriver/expected_mapping.yaml`

### Generated Files (in MinIO)
- **CMF File**: `{schema_id}/schema.cmf`
- **Mapping YAML**: `{schema_id}/mapping.yaml`
- **Metadata**: `{schema_id}/metadata.json`

## Key Functions

### CMF Processing
```python
# cmf_tool.py
async def convert_xsd_to_cmf(xsd_content, source_dir, primary_filename)
def run_cmf_command(cmd, timeout, working_dir)
def is_cmf_available()
```

### Mapping Generation
```python
# cmf_to_mapping.py
def generate_mapping_from_cmf_content(cmf_content: str) -> dict
def _generate_mapping_from_root(root: ET.Element) -> dict
def build_prefix_map(root: ET.Element) -> dict
def parse_classes(root: ET.Element) -> List[dict]
def build_objects_list(classes, prefixes_all) -> List[dict]
def build_associations_list(root, prefixes_all, class_index, element_to_class) -> List[dict]
def build_references_list(root, prefixes_all, class_index, element_to_class) -> List[dict]
```

## Testing

### Local Testing
```python
# Test mapping generation directly
from niem_api.services.cmf_to_mapping import generate_mapping_from_cmf_content
import yaml

with open('/app/third_party/niem-crashdriver/crashdriverxsd.cmf', 'r') as f:
    cmf_content = f.read()

mapping_dict = generate_mapping_from_cmf_content(cmf_content)
mapping_yaml = yaml.dump(mapping_dict, sort_keys=False, default_flow_style=False)
```

### API Testing
```bash
# Upload CrashDriver schema
curl -X POST "http://localhost:8000/api/schema/xsd" \
  -H "Authorization: Bearer devtoken" \
  -F "files=@/path/to/CrashDriver.xsd" \
  -F "skip_niem_resolution=false"
```

## Configuration

### Environment Variables
- `MINIO_ENDPOINT`: MinIO storage endpoint
- `NEO4J_URI`: Neo4j database connection
- `CMF_TOOL_PATH`: Path to CMF tool executable

### Override Behavior
The CrashDriver override is triggered when:
- Primary filename matches `crashdriver.xsd` (case-insensitive)
- Pre-existing CMF file exists at the specified path
- CMF tool would normally be called for XSD conversion

This ensures that CrashDriver schemas use the manually curated CMF file instead of automated conversion, resulting in richer and more accurate mapping structures.