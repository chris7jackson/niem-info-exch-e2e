# Manual Testing Guide: Generate Expected Mapping YAML

This guide shows how to manually test the mapping YAML generation process and create the `expected_mapping.yaml` file from the pre-existing CrashDriver CMF file.

## Prerequisites

- Docker container running with the API
- Access to the pre-existing CMF file at `/app/third_party/niem-crashdriver/crashdriverxsd.cmf`

## Method 1: Direct Python Testing in Container

### Step 1: Access the Container
```bash
docker compose exec api bash
```

### Step 2: Test Mapping Generation
```bash
# Start Python in the container
python3 -c "
import sys
sys.path.append('/app/src')

from niem_api.services.cmf_to_mapping import generate_mapping_from_cmf_content
import yaml

print('=== Testing CrashDriver Mapping Generation ===')

# Read the pre-existing CMF file
cmf_path = '/app/third_party/niem-crashdriver/crashdriverxsd.cmf'
print(f'Reading CMF file from: {cmf_path}')

with open(cmf_path, 'r', encoding='utf-8') as f:
    cmf_content = f.read()

print(f'CMF file size: {len(cmf_content)} characters')
print(f'First 200 chars: {cmf_content[:200]}...')

# Generate mapping dictionary
try:
    print('\n=== Generating Mapping Dictionary ===')
    mapping_dict = generate_mapping_from_cmf_content(cmf_content)

    print(f'Mapping generation successful!')
    print(f'Dictionary keys: {list(mapping_dict.keys())}')
    print(f'Namespaces: {len(mapping_dict.get(\"namespaces\", {}))}')
    print(f'Objects: {len(mapping_dict.get(\"objects\", []))}')
    print(f'Associations: {len(mapping_dict.get(\"associations\", []))}')
    print(f'References: {len(mapping_dict.get(\"references\", []))}')

    # Convert to YAML
    mapping_yaml = yaml.dump(mapping_dict, sort_keys=False, default_flow_style=False)
    print(f'\n=== Generated Mapping YAML ===')
    print(f'YAML length: {len(mapping_yaml)} characters')

    # Display the YAML
    print('\n=== YAML Content ===')
    print(mapping_yaml)

except Exception as e:
    print(f'Error: {e}')
    import traceback
    traceback.print_exc()
"
```

## Method 2: Save to File and Copy to Host

### Step 1: Generate and Save in Container
```bash
docker compose exec api python3 -c "
import sys
sys.path.append('/app/src')

from niem_api.services.cmf_to_mapping import generate_mapping_from_cmf_content
import yaml

# Read CMF file
with open('/app/third_party/niem-crashdriver/crashdriverxsd.cmf', 'r', encoding='utf-8') as f:
    cmf_content = f.read()

# Generate mapping
mapping_dict = generate_mapping_from_cmf_content(cmf_content)
mapping_yaml = yaml.dump(mapping_dict, sort_keys=False, default_flow_style=False)

# Save to container temp file
with open('/tmp/expected_mapping.yaml', 'w', encoding='utf-8') as f:
    f.write(mapping_yaml)

print('Generated and saved mapping to /tmp/expected_mapping.yaml')
print(f'File size: {len(mapping_yaml)} characters')
"
```

### Step 2: Copy from Container to Host
```bash
# Copy the generated file from container to host
docker compose cp api:/tmp/expected_mapping.yaml ./third_party/niem-crashdriver/expected_mapping.yaml

# Verify the file was created
ls -la ./third_party/niem-crashdriver/expected_mapping.yaml
echo "File size: $(wc -c < ./third_party/niem-crashdriver/expected_mapping.yaml) characters"
```

## Method 3: One-Line Host Command

### Direct Generation to Host File
```bash
docker compose exec api python3 -c "
import sys
sys.path.append('/app/src')

from niem_api.services.cmf_to_mapping import generate_mapping_from_cmf_content
import yaml

# Read and process
with open('/app/third_party/niem-crashdriver/crashdriverxsd.cmf', 'r', encoding='utf-8') as f:
    cmf_content = f.read()

mapping_dict = generate_mapping_from_cmf_content(cmf_content)
mapping_yaml = yaml.dump(mapping_dict, sort_keys=False, default_flow_style=False)

print(mapping_yaml)
" > ./third_party/niem-crashdriver/expected_mapping.yaml

echo "Created expected_mapping.yaml ($(wc -c < ./third_party/niem-crashdriver/expected_mapping.yaml) characters)"
```

## Method 4: Test Individual Functions

### Step 1: Test CMF File Access
```bash
docker compose exec api python3 -c "
from pathlib import Path

cmf_path = Path('/app/third_party/niem-crashdriver/crashdriverxsd.cmf')
print(f'CMF file exists: {cmf_path.exists()}')
print(f'CMF file size: {cmf_path.stat().st_size if cmf_path.exists() else \"N/A\"} bytes')

if cmf_path.exists():
    with open(cmf_path, 'r', encoding='utf-8') as f:
        content = f.read()
    print(f'Successfully read {len(content)} characters')
    print(f'First 100 chars: {content[:100]}')
"
```

### Step 2: Test Mapping Functions Step by Step
```bash
docker compose exec api python3 -c "
import sys
sys.path.append('/app/src')
import xml.etree.ElementTree as ET

from niem_api.services.cmf_to_mapping import (
    build_prefix_map,
    parse_classes,
    build_objects_list,
    build_associations_list,
    build_references_list,
    build_augmentations_list
)

print('=== Testing Individual Mapping Functions ===')

# Read and parse CMF
with open('/app/third_party/niem-crashdriver/crashdriverxsd.cmf', 'r', encoding='utf-8') as f:
    cmf_content = f.read()

root = ET.fromstring(cmf_content)
print('✓ CMF XML parsed successfully')

# Test each function
try:
    prefixes_all = build_prefix_map(root)
    print(f'✓ Prefixes: {len(prefixes_all)} namespaces')
    print(f'  Namespaces: {list(prefixes_all.keys())}')

    classes = parse_classes(root)
    print(f'✓ Classes: {len(classes)} classes parsed')

    class_index = {c[\"id\"]: c for c in classes if c[\"id\"]}
    print(f'✓ Class index: {len(class_index)} indexed')

    from niem_api.services.cmf_to_mapping import build_element_to_class
    element_to_class = build_element_to_class(root)
    print(f'✓ Element mapping: {len(element_to_class)} elements mapped')

    objects = build_objects_list(classes, prefixes_all)
    print(f'✓ Objects: {len(objects)} objects built')

    associations = build_associations_list(root, prefixes_all, class_index, element_to_class)
    print(f'✓ Associations: {len(associations)} associations built')

    references = build_references_list(root, prefixes_all, class_index, element_to_class)
    print(f'✓ References: {len(references)} references built')

    augmentations = build_augmentations_list(root, prefixes_all, class_index)
    print(f'✓ Augmentations: {len(augmentations)} augmentations built')

    print('\n=== All functions working correctly! ===')

except Exception as e:
    print(f'✗ Error in function testing: {e}')
    import traceback
    traceback.print_exc()
"
```

## Method 5: Compare with Current API Output

### Step 1: Generate Expected Mapping
```bash
# Generate the expected mapping
docker compose exec api python3 -c "
import sys
sys.path.append('/app/src')
from niem_api.services.cmf_to_mapping import generate_mapping_from_cmf_content
import yaml

with open('/app/third_party/niem-crashdriver/crashdriverxsd.cmf', 'r', encoding='utf-8') as f:
    cmf_content = f.read()

mapping_dict = generate_mapping_from_cmf_content(cmf_content)
mapping_yaml = yaml.dump(mapping_dict, sort_keys=False, default_flow_style=False)
print(mapping_yaml)
" > ./expected_mapping.yaml
```

### Step 2: Upload Schema and Get Current Output
```bash
# Upload CrashDriver schema
SCHEMA_RESPONSE=$(curl -s -X POST "http://localhost:8000/api/schema/xsd" \
  -H "Authorization: Bearer devtoken" \
  -F "files=@./samples/CrashDriver-cmf/CrashDriver.xsd" \
  -F "skip_niem_resolution=false")

# Extract schema ID
SCHEMA_ID=$(echo $SCHEMA_RESPONSE | python3 -c "import sys, json; print(json.load(sys.stdin)['schema_id'])")
echo "Schema ID: $SCHEMA_ID"

# Get current mapping from MinIO
docker compose exec api python3 -c "
import boto3

s3 = boto3.client(
    's3',
    endpoint_url='http://minio:9000',
    aws_access_key_id='minio',
    aws_secret_access_key='minio123'
)

schema_id = '$SCHEMA_ID'
mapping_response = s3.get_object(Bucket='niem-schemas', Key=f'{schema_id}/mapping.yaml')
current_mapping = mapping_response['Body'].read().decode('utf-8')
print(current_mapping)
" > ./current_mapping.yaml
```

### Step 3: Compare the Files
```bash
echo "=== File Sizes ==="
echo "Expected: $(wc -c < ./expected_mapping.yaml) characters"
echo "Current:  $(wc -c < ./current_mapping.yaml) characters"

echo -e "\n=== First 20 Lines Comparison ==="
echo "--- Expected ---"
head -20 ./expected_mapping.yaml

echo -e "\n--- Current ---"
head -20 ./current_mapping.yaml

# Show differences
echo -e "\n=== Differences ==="
diff ./expected_mapping.yaml ./current_mapping.yaml | head -20
```

## Expected Output Structure

When you run these tests, you should see:

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
  # ... association details

references:
- owner_object: exch:CrashDriverInfo
  field_qname: j:Crash
  target_label: j_Crash
  # ... reference details

# ... more content
```

## Troubleshooting

### If CMF File Not Found
```bash
docker compose exec api ls -la /app/third_party/niem-crashdriver/
```

### If Import Errors
```bash
docker compose exec api python3 -c "
import sys
print('Python path:', sys.path)
sys.path.append('/app/src')

try:
    from niem_api.services.cmf_to_mapping import generate_mapping_from_cmf_content
    print('✓ Import successful')
except ImportError as e:
    print('✗ Import failed:', e)
"
```

### If YAML Generation Fails
```bash
docker compose exec api python3 -c "
import yaml
test_dict = {'test': 'value'}
try:
    yaml_output = yaml.dump(test_dict)
    print('✓ YAML library working')
    print('Output:', yaml_output)
except Exception as e:
    print('✗ YAML error:', e)
"
```

This guide provides multiple methods to manually test and generate the expected mapping YAML, allowing you to verify the mapping generation process and compare it with the current API output.