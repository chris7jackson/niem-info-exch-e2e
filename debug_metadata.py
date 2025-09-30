#!/usr/bin/env python3
import xml.etree.ElementTree as ET
from pathlib import Path

xml_path = Path('samples/CrashDriver-cmf/CrashDriver1.xml')
xml_content = xml_path.read_text(encoding='utf-8')

# Parse XML and check for metadata refs
root = ET.fromstring(xml_content)

def check_element(elem, level=0):
    indent = "  " * level
    tag = elem.tag.split('}')[-1] if '}' in elem.tag else elem.tag

    # Check for nc:metadataRef
    nc_ref = None
    priv_ref = None

    for attr_name, attr_value in elem.attrib.items():
        if 'metadataRef' in attr_name or 'privacyMetadataRef' in attr_name:
            print(f"{indent}{tag} has attribute: {attr_name} = {attr_value}")
            if 'niem-core' in attr_name:
                nc_ref = attr_value
            if 'PrivacyMetadata' in attr_name or '/priv' in attr_name or 'example.com' in attr_name:
                priv_ref = attr_value

    if nc_ref or priv_ref:
        print(f"{indent}  -> Found metadata refs: nc={nc_ref}, priv={priv_ref}")

    # Check structures:id
    structures_id = elem.attrib.get('{https://docs.oasis-open.org/niemopen/ns/model/structures/6.0/}id')
    if structures_id:
        print(f"{indent}  -> structures:id = {structures_id}")

    # Recurse
    for child in elem:
        check_element(child, level + 1)

print("=== CHECKING XML FOR METADATA REFERENCES ===")
check_element(root)