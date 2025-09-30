#!/usr/bin/env python3
import sys
sys.path.insert(0, 'api/src')
import xml.etree.ElementTree as ET
import re
from pathlib import Path
from typing import Dict, List

def parse_ns(xml_text: str) -> Dict[str, str]:
    """Parse namespace declarations from XML text."""
    ns_map = dict(re.findall(r'xmlns:([A-Za-z0-9_-]+)\s*=\s*"([^"]+)"', xml_text))
    match = re.search(r'xmlns\s*=\s*"([^"]+)"', xml_text)
    if match:
        ns_map[""] = match.group(1)
    return ns_map

def get_metadata_refs(elem: ET.Element, xml_ns_map: Dict[str, str]) -> List[str]:
    """Extract metadata reference IDs from nc:metadataRef or priv:privacyMetadataRef attributes."""
    metadata_refs = []

    print(f"\n=== Checking element: {elem.tag} ===")
    print(f"Attributes: {elem.attrib}")
    print(f"Namespace map: {xml_ns_map}")

    # Check for nc:metadataRef
    for prefix, uri in xml_ns_map.items():
        print(f"Checking prefix '{prefix}' with URI '{uri}'")
        if 'niem-core' in uri:
            nc_metadata_ref = elem.attrib.get(f"{{{uri}}}metadataRef")
            print(f"  Looking for {{{uri}}}metadataRef: {nc_metadata_ref}")
            if nc_metadata_ref:
                metadata_refs.extend(nc_metadata_ref.strip().split())
        elif 'PrivacyMetadata' in uri or '/priv' in uri:
            priv_metadata_ref = elem.attrib.get(f"{{{uri}}}privacyMetadataRef")
            print(f"  Looking for {{{uri}}}privacyMetadataRef: {priv_metadata_ref}")
            if priv_metadata_ref:
                metadata_refs.extend(priv_metadata_ref.strip().split())

    print(f"Found metadata refs: {metadata_refs}")
    return metadata_refs

# Load XML
xml_path = Path('samples/CrashDriver-cmf/CrashDriver1.xml')
xml_content = xml_path.read_text(encoding='utf-8')
root = ET.fromstring(xml_content)
xml_ns_map = parse_ns(xml_content)

# Find specific elements
for elem in root.iter():
    tag = elem.tag.split('}')[-1] if '}' in elem.tag else elem.tag
    if tag in ['Charge', 'PersonChargeAssociation', 'CrashPersonInjury']:
        refs = get_metadata_refs(elem, xml_ns_map)
        print(f"\n>>> RESULT for {tag}: {refs}")