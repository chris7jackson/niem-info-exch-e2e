#!/usr/bin/env python3
import sys
sys.path.insert(0, 'api/src')

from niem_api.services.import_xml_to_cypher import generate_for_xml_content
from pathlib import Path

# Load XML
xml_path = Path('samples/CrashDriver-cmf/CrashDriver1.xml')
xml_content = xml_path.read_text(encoding='utf-8')

# Minimal mapping (empty)
mapping = {
    "objects": [],
    "associations": [],
    "references": [],
    "namespaces": {}
}

# Generate Cypher - this will show us what nodes are created
cypher, nodes, contains, edges = generate_for_xml_content(xml_content, mapping, 'CrashDriver1.xml')

print("=== NODES CREATED ===")
for nid, (label, qn, props) in sorted(nodes.items(), key=lambda x: x[1][1]):
    print(f"{nid}: {qn} ({label})")

print("\n=== CHECKING FOR EXPECTED NODES ===")
expected = ['j:CrashPersonInjury', 'j:Charge', 'j:PersonChargeAssociation']
for exp in expected:
    found = [nid for nid, (label, qn, props) in nodes.items() if qn == exp]
    print(f"{exp}: {len(found)} nodes - {found}")

print("\n=== METADATA EDGES ===")
for fid, flabel, tid, tlabel, rel, rprops in edges:
    if rel == 'HAS_METADATA':
        fname = nodes.get(fid, (None, 'UNKNOWN', {}))[1]
        tname = nodes.get(tid, (None, 'UNKNOWN', {}))[1]
        print(f"{fname} ({fid}) --[{rel}]--> {tname} ({tid})")