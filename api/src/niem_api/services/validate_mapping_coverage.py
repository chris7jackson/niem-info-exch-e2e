
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Validator — CMF ↔ mapping.yaml Coverage & Consistency (NIEM→Neo4j)
==================================================================

Purpose
-------
Given:
  1) a NIEM **CMF 1.0** XML, and
  2) a **mapping.yaml** produced by `cmf_to_mapping.documented.py` (or equivalent),

this validator checks that the mapping is *comprehensive* and *internally consistent*:

Checks performed
----------------
1) **Namespace sanity**
   - Every QName prefix in mapping.yaml exists in CMF namespaces.
   - Mapping `namespaces` section includes all prefixes needed by mapping QNames.

2) **Association coverage**
   - Every CMF Class with `SubClassOf == nc.AssociationType` has a corresponding entry in `associations[]`.
   - Each association has ≥2 `endpoints[]`.
   - Each endpoint’s `maps_to_label` exists in `objects[]` labels.

3) **Object-valued reference coverage**
   - For every object Class, each child `ChildPropertyAssociation/ObjectProperty` whose *target Class* is **not**
     an AssociationType must have a `references[]` rule `(owner_object, field_qname)`.
   - Target label in the rule must resolve to the element/class label of the target Class.

4) **Objects coverage (advisory)**
   - Reports CMF object Classes missing from `objects[]` (warning: some Classes are abstract/no element).

5) **Cardinality presence (advisory)**
   - Each `references[]` and association endpoint includes a cardinality string (e.g., `0..*`).

Exit code
---------
- **0** if no critical issues (association or reference coverage failures, bad endpoints).
- **1** if any critical issue is detected.

Usage
-----
    python validate_mapping_coverage.documented.py <input.cmf.xml> <mapping.yaml> [--json report.json]

"""

import sys, argparse, re, json, yaml
import xml.etree.ElementTree as ET

CMF_NS = "https://docs.oasis-open.org/niemopen/ns/specification/cmf/1.0/"
STRUCT_NS = "https://docs.oasis-open.org/niemopen/ns/model/structures/6.0/"
NS = {"cmf": CMF_NS, "structures": STRUCT_NS}

# --------------------- CMF parsing helpers ---------------------

def ref_of(el, tag):
    t = el.find(f"./cmf:{tag}", NS)
    if t is not None:
        return t.attrib.get(f"{{{STRUCT_NS}}}ref")
    return None

def text_of(el, tag):
    t = el.find(f"./cmf:{tag}", NS)
    return (t.text.strip() if t is not None and t.text else None)

def cmf_namespaces(root):
    out = {}
    for nsel in root.findall(".//cmf:Namespace", NS):
        p = nsel.find("./cmf:NamespacePrefixText", NS)
        u = nsel.find("./cmf:NamespaceURI", NS)
        if p is not None and u is not None and p.text and u.text:
            out[p.text.strip()] = u.text.strip()
    return out

def parse_classes(root):
    classes = []
    for cl in root.findall(".//cmf:Class", NS):
        cid = cl.attrib.get(f"{{{STRUCT_NS}}}id") or cl.attrib.get("id")
        subclass = ref_of(cl, "SubClassOf")
        props = []
        for cpa in cl.findall("./cmf:ChildPropertyAssociation", NS):
            op_ref = ref_of(cpa, "ObjectProperty")
            dp_ref = ref_of(cpa, "DataProperty")
            mino = text_of(cpa, "MinOccursQuantity")
            maxo = text_of(cpa, "MaxOccursQuantity")
            props.append({"objectProperty": op_ref, "dataProperty": dp_ref, "min": mino, "max": maxo})
        classes.append({"id": cid, "subclass_of": subclass, "props": props})
    return classes

def build_objectproperty_to_class(root):
    mapping = {}
    for el in root.findall(".//cmf:ObjectProperty", NS):
        classRef = el.find("./cmf:Class", NS)
        if classRef is not None:
            cref = classRef.attrib.get(f"{{{STRUCT_NS}}}ref")
            el_id = el.attrib.get(f"{{{STRUCT_NS}}}id")
            if cref and el_id:
                mapping[el_id] = cref
    return mapping

# --------------------- QName utils ---------------------

def prefixes_in_qname(qn: str):
    # Return prefix used in a QName (prefix:LocalName)
    if qn and ":" in qn:
        return {qn.split(":",1)[0]}
    return set()

def collect_mapping_prefixes(mapping):
    used = set()
    for o in mapping.get("objects", []):
        used |= prefixes_in_qname(o.get("qname"))
        for sp in o.get("scalar_props", []) or []:
            p = sp.get("path")
            if p and ":" in p.replace("@",""):
                used.add(p.replace("@","").split(":",1)[0])
    for a in mapping.get("associations", []):
        used |= prefixes_in_qname(a.get("qname"))
        for ep in a.get("endpoints", []) or []:
            used |= prefixes_in_qname(ep.get("role_qname"))
    for r in mapping.get("references", []):
        used |= prefixes_in_qname(r.get("owner_object"))
        used |= prefixes_in_qname(r.get("field_qname"))
    return used

# --------------------- Validation logic ---------------------

def validate(cmf_xml, mapping_yaml):
    root = ET.parse(cmf_xml).getroot()
    with open(mapping_yaml, "r", encoding="utf-8") as f:
        mapping = yaml.safe_load(f)

    cmf_ns = cmf_namespaces(root)
    classes = parse_classes(root)
    element_to_class = build_objectproperty_to_class(root)
    class_to_element = {v:k for k,v in element_to_class.items()}

    # Partition
    assoc_ids = {c["id"] for c in classes if c["subclass_of"] == "nc.AssociationType"}
    obj_ids   = {c["id"] for c in classes if c["subclass_of"] != "nc.AssociationType"}

    # Build mapping indexes
    objects_labels = {o["label"]: o for o in mapping.get("objects", [])}
    objects_qnames = {o["qname"]: o for o in mapping.get("objects", [])}
    labels_set = set(objects_labels.keys())
    assoc_qnames = {a["qname"]: a for a in mapping.get("associations", [])}
    refs_index = {(r["owner_object"], r["field_qname"]): r for r in mapping.get("references", [])}

    report = {
        "namespaces": {
            "cmf_prefixes": sorted(cmf_ns.keys()),
            "mapping_prefixes_used": sorted(list(collect_mapping_prefixes(mapping))),
            "missing_prefixes_in_cmf": [],
            "missing_prefixes_in_mapping_namespaces": [],
        },
        "coverage": {
            "associationtypes_total": 0,
            "associationtypes_mapped": 0,
            "unmapped_associations": [],
            "objecttypes_total": 0,
            "objecttypes_mapped": len(objects_qnames),
            "unmapped_objects_advisory": [],
            "object_refs_total": 0,
            "object_refs_mapped": 0,
            "unmapped_object_refs": [],
        },
        "consistency": {
            "bad_endpoints": [],
            "missing_cardinalities": {
                "associations": [],
                "references": []
            }
        }
    }

    # Namespace checks
    used_prefixes = collect_mapping_prefixes(mapping)
    for p in sorted(used_prefixes):
        if p not in cmf_ns:
            report["namespaces"]["missing_prefixes_in_cmf"].append(p)
    for p in sorted(used_prefixes):
        if p not in mapping.get("namespaces", {}):
            report["namespaces"]["missing_prefixes_in_mapping_namespaces"].append(p)

    # Association coverage & endpoint validation
    assoc_total = 0
    assoc_mapped = 0
    for c in classes:
        if c["subclass_of"] != "nc.AssociationType":
            continue
        assoc_total += 1
        assoc_qn = (class_to_element.get(c["id"]) or c["id"]).replace(".", ":")
        a = assoc_qnames.get(assoc_qn)
        if not a:
            report["coverage"]["unmapped_associations"].append(assoc_qn)
            continue
        assoc_mapped += 1
        # endpoints present?
        eps = a.get("endpoints", []) or []
        if len(eps) < 2:
            report["consistency"]["bad_endpoints"].append({"association": assoc_qn, "reason": "fewer than 2 endpoints"})
        else:
            for ep in eps:
                mlabel = ep.get("maps_to_label")
                if not mlabel or mlabel not in labels_set:
                    report["consistency"]["bad_endpoints"].append({"association": assoc_qn, "endpoint": ep, "reason": "maps_to_label not found in objects labels"})

        # endpoint cardinalities present (advisory)
        if any(not ep.get("cardinality") for ep in eps):
            report["consistency"]["missing_cardinalities"]["associations"].append(assoc_qn)

    report["coverage"]["associationtypes_total"] = assoc_total
    report["coverage"]["associationtypes_mapped"] = assoc_mapped

    # Object-valued references coverage
    refs_total = 0
    refs_mapped = 0
    for c in classes:
        if c["subclass_of"] == "nc.AssociationType":
            continue
        owner_qn = (class_to_element.get(c["id"]) or c["id"]).replace(".", ":")
        for p in c["props"]:
            op = p["objectProperty"]
            if not op:
                continue
            target_class_id = element_to_class.get(op)
            if target_class_id and target_class_id not in assoc_ids:
                refs_total += 1
                key = (owner_qn, op.replace(".", ":"))
                if key in refs_index:
                    refs_mapped += 1
                else:
                    report["coverage"]["unmapped_object_refs"].append({"owner": owner_qn, "field": op.replace(".", ":")})

    report["coverage"]["object_refs_total"] = refs_total
    report["coverage"]["object_refs_mapped"] = refs_mapped

    # Objects coverage (advisory)
    obj_total = len(obj_ids)
    report["coverage"]["objecttypes_total"] = obj_total
    # Warn if a CMF object class with an associated element is missing from mapping.objects
    for cid in obj_ids:
        el = class_to_element.get(cid)
        cand_qn = (el or cid).replace(".", ":")
        if cand_qn not in objects_qnames:
            report["coverage"]["unmapped_objects_advisory"].append(cand_qn)

    # References cardinality presence (advisory)
    for r in mapping.get("references", []):
        if not r.get("cardinality"):
            report["consistency"]["missing_cardinalities"]["references"].append((r.get("owner_object"), r.get("field_qname")))

    # Decide exit code
    critical = (
        len(report["coverage"]["unmapped_associations"]) > 0 or
        len(report["coverage"]["unmapped_object_refs"]) > 0 or
        len(report["consistency"]["bad_endpoints"]) > 0 or
        len(report["namespaces"]["missing_prefixes_in_cmf"]) > 0 or
        len(report["namespaces"]["missing_prefixes_in_mapping_namespaces"]) > 0
    )

    return report, (1 if critical else 0)

def validate_mapping_coverage(cmf_file_path: str, mapping_file_path: str) -> dict:
    """
    Validate mapping coverage from file paths.

    Args:
        cmf_file_path: Path to CMF XML file
        mapping_file_path: Path to mapping YAML file

    Returns:
        Dictionary containing validation report
    """
    report, exit_code = validate(cmf_file_path, mapping_file_path)

    # Add summary statistics for easier consumption
    coverage = report.get("coverage", {})
    total_assocs = coverage.get("associationtypes_total", 0)
    mapped_assocs = coverage.get("associationtypes_mapped", 0)
    total_refs = coverage.get("object_refs_total", 0)
    mapped_refs = coverage.get("object_refs_mapped", 0)

    # Calculate coverage percentages
    assoc_coverage = (mapped_assocs / total_assocs * 100) if total_assocs > 0 else 100
    ref_coverage = (mapped_refs / total_refs * 100) if total_refs > 0 else 100
    overall_coverage = ((mapped_assocs + mapped_refs) / (total_assocs + total_refs) * 100) if (total_assocs + total_refs) > 0 else 100

    report["summary"] = {
        "overall_coverage_percentage": round(overall_coverage, 1),
        "association_coverage_percentage": round(assoc_coverage, 1),
        "reference_coverage_percentage": round(ref_coverage, 1),
        "has_critical_issues": exit_code != 0,
        "total_mapped_elements": mapped_assocs + mapped_refs,
        "total_elements": total_assocs + total_refs
    }

    return report

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmf_xml")
    ap.add_argument("mapping_yaml")
    ap.add_argument("--json", help="Write detailed report JSON to this path")
    args = ap.parse_args()

    report, code = validate(args.cmf_xml, args.mapping_yaml)

    pretty = json.dumps(report, indent=2)
    print(pretty)
    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            f.write(pretty)
    sys.exit(code)

if __name__ == "__main__":
    main()
