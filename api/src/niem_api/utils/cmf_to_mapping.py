
import sys, re, yaml
import xml.etree.ElementTree as ET
CMF_NS = "https://docs.oasis-open.org/niemopen/ns/specification/cmf/1.0/"
STRUCT_NS = "https://docs.oasis-open.org/niemopen/ns/model/structures/6.0/"
NS = {"cmf": CMF_NS, "structures": STRUCT_NS}
def to_qname(dotted): return dotted.replace(".", ":")
def to_label(qn): return qn.replace(":", "_").replace(".", "_")
def to_rel_type(name): return re.sub(r"[^A-Za-z0-9_]", "_", name.replace(":","_").replace(".","_")).upper()
def text_of(el, tag):
    t = el.find(f"./cmf:{tag}", NS)
    return (t.text.strip() if t is not None and t.text else None)
def ref_of(el, tag):
    t = el.find(f"./cmf:{tag}", NS)
    if t is not None:
        return t.attrib.get(f"{{{STRUCT_NS}}}ref")
    return None
def build_prefix_map(root):
    prefixes = {}
    for nsel in root.findall(".//cmf:Namespace", NS):
        p = nsel.find("./cmf:NamespacePrefixText", NS)
        u = nsel.find("./cmf:NamespaceURI", NS)
        if p is not None and u is not None and p.text and u.text:
            prefixes[p.text.strip()] = u.text.strip()
    return prefixes
def parse_classes(root):
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
            props.append({"objectProperty": op_ref, "dataProperty": dp_ref, "min": mino, "max": maxo})
        classes_info.append({"id": cid, "name": name, "namespace_prefix": nsref, "subclass_of": subclass, "props": props})
    return [c for c in classes_info if any([c["id"], c["name"], c["namespace_prefix"], c["subclass_of"], c["props"]])]
def build_element_to_class(root):
    mapping = {}
    for el in root.findall(".//cmf:ObjectProperty", NS):
        classRef = el.find("./cmf:Class", NS)
        if classRef is not None:
            cref = classRef.attrib.get(f"{{{STRUCT_NS}}}ref")
            el_id = el.attrib.get(f"{{{STRUCT_NS}}}id")
            if cref and el_id:
                mapping[el_id] = cref
    return mapping
def main(cmf_path, out_yaml):
    root = ET.parse(cmf_path).getroot()
    prefixes = build_prefix_map(root)
    classes = parse_classes(root)
    class_index = {c["id"]: c for c in classes if c["id"]}
    element_to_class = build_element_to_class(root)
    class_to_element = {v:k for k,v in element_to_class.items()}
    assoc_ids = set()
    objects, associations = [], []
    for cid, ci in class_index.items():
        if ci["subclass_of"] == "nc.AssociationType":
            assoc_ids.add(cid)
            associations.append({"class_id": cid, "element_qname": class_to_element.get(cid), "info": ci})
        else:
            objects.append({"class_id": cid, "element_qname": class_to_element.get(cid), "info": ci})
    used_prefixes = set()
    for ci in classes:
        if ci["namespace_prefix"]:
            used_prefixes.add(ci["namespace_prefix"])
        for p in ci["props"]:
            for ref in (p["objectProperty"], p["dataProperty"]):
                if ref and "." in ref:
                    used_prefixes.add(ref.split(".",1)[0])
    used_ns_map = {k: v for k,v in prefixes.items() if k in used_prefixes}
    mapping = {"namespaces": used_ns_map, "objects": [], "associations": [], "references": [], "augmentations": [],
               "polymorphism": {"strategy": "extraLabel", "store_actual_type_property": "xsiType"}}
    for obj in objects:
        qn = (obj["element_qname"] or obj["class_id"]).replace(".", ":")
        mapping["objects"].append({"qname": qn, "label": qn.replace(":","_").replace(".","_"),
                                   "carries_structures_id": True, "scalar_props": []})
    def label_for_class(cid):
        el = class_to_element.get(cid)
        if el: 
            return (el.replace(".","_")).replace(":","_")
        return (cid.replace(".","_").replace("Type",""))
    for assoc in associations:
        ci = assoc["info"]
        base_rel_name = (assoc["element_qname"] or assoc["class_id"]).replace(".", ":")
        endpoints = []
        for p in ci["props"]:
            op = p["objectProperty"]
            if not op: continue
            target_class_id = element_to_class.get(op)
            target_label = label_for_class(target_class_id) if target_class_id else (op.replace(".","_"))
            endpoints.append({"role_qname": op.replace(".", ":"), "maps_to_label": target_label,
                              "direction": "source" if len(endpoints)==0 else "target",
                              "via": "structures:ref",
                              "cardinality": f"{p['min'] or '0'}..{p['max'] or '*'}"})
        mapping["associations"].append({"qname": base_rel_name, "rel_type": (base_rel_name.replace(":","_")).upper(),
                                        "endpoints": endpoints, "rel_props": []})
    for obj in objects:
        owner_qn = (obj["element_qname"] or obj["class_id"]).replace(".", ":")
        ci = obj["info"]
        for p in ci["props"]:
            op = p["objectProperty"]
            if not op: continue
            target_class_id = element_to_class.get(op)
            if target_class_id and target_class_id not in assoc_ids:
                mapping["references"].append({"owner_object": owner_qn, "field_qname": op.replace(".", ":"),
                                              "target_label": label_for_class(target_class_id),
                                              "rel_type": (op.replace(".","_")).upper(),
                                              "via": "structures:ref",
                                              "cardinality": f"{p['min'] or '0'}..{p['max'] or '*'}"})
    with open(out_yaml, "w", encoding="utf-8") as f:
        yaml.safe_dump(mapping, f, sort_keys=False, allow_unicode=True)
    print(f"OK: wrote {out_yaml}")
if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python cmf_to_mapping.py <input.cmf.xml> <output.yaml>")
        sys.exit(2)
    main(sys.argv[1], sys.argv[2])
