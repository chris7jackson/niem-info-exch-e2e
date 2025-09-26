
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CMF → mapping.yaml (NIEM → Neo4j) — Documented Transformer
=========================================================

Purpose
-------
Transform a NIEM CMF 1.0 XML file into a *mapping.yaml* that a Neo4j importer
can use to create a property graph from NIEM-conformant XML instances.

What this script emits
----------------------
A YAML mapping with the following sections:

- namespaces:  { prefix: uri, ... }  (only those prefixes actually used)
- objects:     [ { qname, label, carries_structures_id, scalar_props[] }, ... ]
- associations:[ { qname, rel_type, endpoints[], rel_props[] }, ... ]
- references:  [ { owner_object, field_qname, target_label, rel_type, via, cardinality }, ... ]
- augmentations: []  (placeholder for future extension)
- polymorphism: { strategy, store_actual_type_property }

How mapping is *executed* later (importer behavior)
---------------------------------------------------
The mapping is designed to drive a generic importer (e.g., import_xml_to_cypher.py):
1) objects[] → Node labels
   - For every NIEM object element (QName matches `objects[*].qname`), the importer MERGEs a node with that label.
   - If the element has @structures:id, that value is used as node identity.
   - If absent (for contained objects), the importer may generate a stable synthetic id (parentId+QName+path hash).
   - scalar_props[] entries (if any are added by you) flatten simple leaves (strings, dates, codes) to node properties.

2) references[] → Directed edges based on owner/field pointers
   - For the owner element, the importer looks for a child with `field_qname` that carries @structures:ref.
   - It resolves the ref to a target node (whose label is `target_label`) and MERGEs an edge with type `rel_type`.
   - `cardinality` from CMF is carried for auditing; the importer can check degree bounds post-ingest.

3) associations[] → Directed edges from AssociationType instances
   - An AssociationType element in the XML produces one or more edges between role participants.
   - Each `endpoints[]` item specifies a role element QName (`role_qname`) that must carry @structures:ref.
   - The importer finds the two (or more) role refs, resolves them to nodes, and MERGEs an edge with `rel_type`.
   - `direction` is set here using a deterministic convention (first role → source, second role → target).
     You can later adjust this per association for domain readability (e.g., event → participant).

Architectural decisions (this transformer)
-----------------------------------------
- **Model-driven:** We derive the graph mapping from CMF "Class" and "ChildPropertyAssociation" facts.
- **Association detection:** A class whose SubClassOf == `nc.AssociationType` is treated as an association.
- **Role resolution:** For each association, role participants are obtained by resolving
  ObjectProperty → Class, then converting to a node label via that class's associated element (if any).
- **Reference edges:** For object classes, any object-valued property whose *target class is not an association*
  becomes a `references[]` rule (assumed to be represented by @structures:ref in instances).
- **Naming hygiene:**
  - Node labels: `prefix_LocalName` (e.g., `j_Crash`, `nc_Person`)
  - Relationship types: `UPPER_SNAKE` of the element/class QName (e.g., `J_CRASH_INVOLVES_PERSON`).
  - These names are sanitized to contain only `[A-Za-z0-9_]` for Cypher safety.
- **Namespaces:** Only prefixes actually referenced by classes/properties are carried into the mapping.
- **Polymorphism:** A default stanza is included so importers can implement one of:
  - "extraLabel": add an extra label for actual `xsi:type`
  - "propertyOnly": record the `xsi:type` as a node property

Limitations & things this script *does not* do
----------------------------------------------
- **Scalar leaf discovery**: CMF doesn't always expose simple leaf paths in a way that unambiguously maps to
  flattenable properties. We emit `scalar_props: []` by default; you may add entries for your high-value paths.
- **Augmentations**: We don't expand `*AugmentationType` automatically. In practice:
  - Simple augmentation content → add to `objects[*].scalar_props` manually.
  - Object/role augmentation content → add a `references[]` rule or a new `associations[]` entry.
- **Contained object rules**: Whether a nested complex child should become a separate node (with a `HAS_*` edge)
  or be flattened is a modeling decision and is handled at import time. This transformer focuses on the *type system*.
- **N-ary associations / more than 2 roles**: We emit all endpoints we discover, in declared order. Your importer
  can either materialize one edge per ordered pair or pick a specific pair. Document your domain choice.
- **Multiple inheritance / anonymous inline types**: CMF normally resolves to named classes; if your CMF has
  anonymous constructs, consider normalizing them in your modeling tool before running this transformer.
- **Non-CMF sources**: This requires NIEM CMF 1.0 XML. Other metamodels (direct XSD, OWL) aren't parsed here.

Compatibility with NIEM CMFs
----------------------------
- **Designed for NIEM CMF 1.0**: uses elements/attributes defined in the CMF 1.0 spec namespace:
  `https://docs.oasis-open.org/niemopen/ns/specification/cmf/1.0/`.
- **Works across domains**: justice (`j`), core (`nc`), homeland security (`hs`), etc., as long as the CMF
  contains Classes, ObjectProperties with linked Classes, Namespaces, and ChildPropertyAssociations.
- **Association detection key**: the strict check is `SubClassOf == "nc.AssociationType"`.
  If your tool emits a different form (e.g., a prefix/URI variant), you may need to adjust that constant.
- **Prefixes**: This script expects `NamespacePrefixText` and `NamespaceURI` entries; most CMF tools emit them.
- **Robustness**: If a CMF omits certain sections (e.g., no associations), the output still validates and
  the importer will simply not create association edges.

Typical pipeline
----------------
1. Generate CMF from your IEPD + NIEM references (one time per model).
2. Run this transformer to produce `mapping.yaml`.
3. Validate the mapping coverage with '
3. Run your XML importer over any number of instance files using the mapping.
4. Run post-ingest Cypher audits (dangling refs, degree checks, expected label pairs).

Usage
-----
    python cmf_to_mapping.documented.py <input.cmf.xml> <output.yaml>

Exit status is 0 on success; non-zero on usage error.

"""

import sys, re, yaml
import xml.etree.ElementTree as ET

# --- Constants & Namespaces ---------------------------------------------------

CMF_NS = "https://docs.oasis-open.org/niemopen/ns/specification/cmf/1.0/"
STRUCT_NS = "https://docs.oasis-open.org/niemopen/ns/model/structures/6.0/"
NS = {"cmf": CMF_NS, "structures": STRUCT_NS}

# --- Helpers ------------------------------------------------------------------

def to_qname(dotted: str) -> str:
    """Convert 'prefix.LocalName' to 'prefix:LocalName' (CMF uses dotted ids)."""
    return dotted.replace(".", ":") if dotted else dotted

def to_label(qn: str) -> str:
    """Convert a QName to a safe Neo4j label (prefix_LocalName)."""
    return qn.replace(":", "_").replace(".", "_")

def to_rel_type(name: str) -> str:
    """Generate a safe, upper-snake relationship type from a QName or id."""
    base = name.replace(":", "_").replace(".", "_")
    return re.sub(r"[^A-Za-z0-9_]", "_", base).upper()

def text_of(el: ET.Element, tag: str):
    t = el.find(f"./cmf:{tag}", NS)
    return (t.text.strip() if t is not None and t.text else None)

def ref_of(el: ET.Element, tag: str):
    t = el.find(f"./cmf:{tag}", NS)
    if t is not None:
        return t.attrib.get(f"{{{STRUCT_NS}}}ref")
    return None

def build_prefix_map(root: ET.Element):
    """Collect prefix→URI bindings from CMF Namespace entries and return only those used later."""
    prefixes = {}
    for nsel in root.findall(".//cmf:Namespace", NS):
        p = nsel.find("./cmf:NamespacePrefixText", NS)
        u = nsel.find("./cmf:NamespaceURI", NS)
        if p is not None and u is not None and p.text and u.text:
            prefixes[p.text.strip()] = u.text.strip()
    return prefixes

def parse_classes(root: ET.Element):
    """Extract Classes with their namespace, base class, and child property associations."""
    classes_info = []
    for cl in root.findall(".//cmf:Class", NS):
        cid = cl.attrib.get(f"{{{STRUCT_NS}}}id") or cl.attrib.get("id")
        name = text_of(cl, "Name")
        nsref = ref_of(cl, "Namespace")
        subclass = ref_of(cl, "SubClassOf")
        props = []
        for cpa in cl.findall("./cmf:ChildPropertyAssociation", NS):
            op_ref = ref_of(cpa, "ObjectProperty")
            dp_ref = ref_of(cpa, "DataProperty")
            mino = text_of(cpa, "MinOccursQuantity")
            maxo = text_of(cpa, "MaxOccursQuantity")
            props.append({
                "objectProperty": op_ref,    # e.g., j.CrashDriver
                "dataProperty": dp_ref,      # simple property (not used here, but preserved)
                "min": mino,
                "max": maxo
            })
        classes_info.append({
            "id": cid, "name": name, "namespace_prefix": nsref,
            "subclass_of": subclass, "props": props
        })
    # Keep only meaningful entries
    return [c for c in classes_info if any([c["id"], c["name"], c["namespace_prefix"], c["subclass_of"], c["props"]])]

def build_element_to_class(root: ET.Element):
    """
    Map ObjectProperty id (element QName in dotted form like 'j.Crash') → Class id (e.g., 'j.CrashType').
    This lets us resolve association role participants to their object classes.
    """
    mapping = {}
    for el in root.findall(".//cmf:ObjectProperty", NS):
        classRef = el.find("./cmf:Class", NS)
        if classRef is not None:
            cref = classRef.attrib.get(f"{{{STRUCT_NS}}}ref")
            el_id = el.attrib.get(f"{{{STRUCT_NS}}}id")
            if cref and el_id:
                mapping[el_id] = cref
    return mapping

# --- Main transformation -------------------------------------------------------

def generate_mapping_from_cmf_file(cmf_path: str) -> dict:
    """
    Generate mapping dictionary from CMF XML file.

    Args:
        cmf_path: Path to CMF XML file

    Returns:
        Dictionary containing the mapping structure
    """
    root = ET.parse(cmf_path).getroot()
    return _generate_mapping_from_root(root)

def _generate_mapping_from_root(root: ET.Element) -> dict:
    """Internal function to generate mapping from parsed XML root."""
    prefixes_all = build_prefix_map(root)
    classes = parse_classes(root)
    class_index = {c["id"]: c for c in classes if c["id"]}
    element_to_class = build_element_to_class(root)
    class_to_element = {v: k for k, v in element_to_class.items()}

    # Partition classes into AssociationType and ObjectType (everything else)
    assoc_ids = set()
    objects, associations = [], []
    for cid, ci in class_index.items():
        if ci["subclass_of"] == "nc.AssociationType":
            assoc_ids.add(cid)
            associations.append({
                "class_id": cid,
                "element_qname": class_to_element.get(cid),
                "info": ci
            })
        else:
            objects.append({
                "class_id": cid,
                "element_qname": class_to_element.get(cid),
                "info": ci
            })

    # Restrict namespaces to those actually used by classes/properties
    used_prefixes = set()
    for ci in classes:
        if ci["namespace_prefix"]:
            used_prefixes.add(ci["namespace_prefix"])
        for p in ci["props"]:
            for ref in (p["objectProperty"], p["dataProperty"]):
                if ref and "." in ref:
                    used_prefixes.add(ref.split(".", 1)[0])
    used_ns_map = {k: v for k, v in prefixes_all.items() if k in used_prefixes}

    mapping = {
        "namespaces": used_ns_map,
        "objects": [],
        "associations": [],
        "references": [],
        "augmentations": [],  # reserved for future
        "polymorphism": {
            "strategy": "extraLabel",
            "store_actual_type_property": "xsiType"
        }
    }

    # Emit objects[]
    for obj in objects:
        qn = to_qname((obj["element_qname"] or obj["class_id"]))
        mapping["objects"].append({
            "qname": qn,
            "label": to_label(qn),
            "carries_structures_id": True,  # Most NIEM objects can; importer may synthesize ids when absent
            "scalar_props": []              # Populate manually if you want value-object flattening
        })

    # Helper for association & reference endpoints: compute label from class id
    def label_for_class(cid: str) -> str:
        el = class_to_element.get(cid)
        if el:
            return to_label(to_qname(el))
        return to_label(to_qname(cid.replace("Type", "")))

    # Emit associations[]
    for assoc in associations:
        ci = assoc["info"]
        base_rel_name = to_qname(assoc["element_qname"] or assoc["class_id"])
        endpoints = []
        for p in ci["props"]:
            op = p["objectProperty"]
            if not op:
                continue
            target_class_id = element_to_class.get(op)
            target_label = label_for_class(target_class_id) if target_class_id else to_label(to_qname(op))
            endpoints.append({
                "role_qname": to_qname(op),
                "maps_to_label": target_label,
                "direction": "source" if len(endpoints) == 0 else "target",
                "via": "structures:ref",
                "cardinality": f"{p['min'] or '0'}..{p['max'] or '*'}"
            })
        mapping["associations"].append({
            "qname": base_rel_name,
            "rel_type": to_rel_type(base_rel_name),
            "endpoints": endpoints,
            "rel_props": []  # add association scalar props here if needed
        })

    # Emit references[] (object-valued properties whose *target is not an association*)
    for obj in objects:
        owner_qn = to_qname(obj["element_qname"] or obj["class_id"])
        ci = obj["info"]
        for p in ci["props"]:
            op = p["objectProperty"]
            if not op:
                continue
            target_class_id = element_to_class.get(op)
            if target_class_id and target_class_id not in assoc_ids:
                mapping["references"].append({
                    "owner_object": owner_qn,
                    "field_qname": to_qname(op),
                    "target_label": label_for_class(target_class_id),
                    "rel_type": to_rel_type(op),
                    "via": "structures:ref",
                    "cardinality": f"{p['min'] or '0'}..{p['max'] or '*'}"
                })

    return mapping

def main(cmf_path: str, out_yaml: str):
    mapping = generate_mapping_from_cmf_file(cmf_path)

    with open(out_yaml, "w", encoding="utf-8") as f:
        yaml.safe_dump(mapping, f, sort_keys=False, allow_unicode=True)

    print(f"OK: wrote {out_yaml}")
    print(f"  namespaces: {len(mapping['namespaces'])}")
    print(f"  objects: {len(mapping['objects'])}")
    print(f"  associations: {len(mapping['associations'])}")
    print(f"  references: {len(mapping['references'])}")

# --- CLI ----------------------------------------------------------------------

if __name__ == "__main__":
    if len(sys.argv) != 2 and len(sys.argv) != 3:
        print("Usage: python cmf_to_mapping.documented.py <input.cmf.xml> <output.yaml>")
        sys.exit(2)
    cmf_path = sys.argv[1]
    out_yaml = sys.argv[2] if len(sys.argv) == 3 else "mapping.yaml"
    main(cmf_path, out_yaml)
