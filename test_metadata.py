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

# Generate Cypher
cypher, nodes, contains, edges = generate_for_xml_content(xml_content, mapping, 'CrashDriver1.xml')

print('=== NODES ===')
for nid, (label, qn, props) in sorted(nodes.items()):
    print(f'{nid}: {label} ({qn})')

print('\n=== METADATA EDGES (HAS_METADATA) ===')
metadata_edges = [e for e in edges if e[4] == 'HAS_METADATA']
for fid, flabel, tid, tlabel, rel, rprops in metadata_edges:
    print(f'{fid} ({flabel}) --[{rel}]--> {tid} ({tlabel})')

print('\n=== ALL EDGES (first 20) ===')
for fid, flabel, tid, tlabel, rel, rprops in edges[:20]:
    print(f'{fid} ({flabel}) --[{rel}]--> {tid} ({tlabel})')

print(f'\n=== SUMMARY ===')
print(f'Total nodes: {len(nodes)}')
print(f'Total edges: {len(edges)}')
print(f'Total containment edges: {len(contains)}')
print(f'Metadata edges: {len(metadata_edges)}')

# Check if root wrapper was created
root_wrapper = [nid for nid, (label, qn, props) in nodes.items() if 'CrashDriverInfo' in qn]
print(f'\nRoot wrapper nodes (should be empty): {root_wrapper}')

# Check specific metadata connections
print('\n=== CHECKING SPECIFIC REQUIREMENTS ===')
crash_injury_nodes = [(nid, label) for nid, (label, qn, props) in nodes.items() if 'CrashPersonInjury' in qn]
charge_nodes = [(nid, label) for nid, (label, qn, props) in nodes.items() if qn == 'j:Charge']
person_charge_assoc = [(nid, label) for nid, (label, qn, props) in nodes.items() if 'PersonChargeAssociation' in qn]

print(f'CrashPersonInjury nodes: {crash_injury_nodes}')
print(f'Charge nodes: {charge_nodes}')
print(f'PersonChargeAssociation nodes: {person_charge_assoc}')