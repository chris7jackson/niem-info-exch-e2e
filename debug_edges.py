#!/usr/bin/env python3
import sys
sys.path.insert(0, 'api/src')

from niem_api.services.import_xml_to_cypher import generate_for_xml_content
from pathlib import Path
import yaml

# Load XML
xml_path = Path('samples/CrashDriver-cmf/CrashDriver1.xml')
xml_content = xml_path.read_text(encoding='utf-8')

# Load mapping
mapping_path = Path('current_api_mapping.yaml')
with open(mapping_path, 'r') as f:
    mapping = yaml.safe_load(f)

# Generate Cypher
cypher, nodes, contains, edges = generate_for_xml_content(xml_content, mapping, 'CrashDriver1.xml')

print("=== EDGES ===")
for fid, flabel, tid, tlabel, rel, rprops in edges:
    print(f"{fid} ({flabel}) --[{rel}]--> {tid} ({tlabel})")

print("\n=== CONTAINS ===")
for pid, plabel, cid, clabel, rel in contains:
    print(f"{pid} ({plabel}) --[{rel}]--> {cid} ({clabel})")
