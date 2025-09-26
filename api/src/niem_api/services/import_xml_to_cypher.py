
#!/usr/bin/env python3
import argparse, re, yaml, hashlib
from pathlib import Path
import xml.etree.ElementTree as ET

STRUCT_NS = "https://docs.oasis-open.org/niemopen/ns/model/structures/6.0/"

def load_mapping(mapping_path: Path):
    m = yaml.safe_load(mapping_path.read_text(encoding="utf-8"))
    obj_qnames = {o["qname"]: o for o in m.get("objects", [])}
    associations = m.get("associations", [])
    references = m.get("references", [])
    ns = m.get("namespaces", {})
    return m, obj_qnames, associations, references, ns

def parse_ns(xml_text: str):
    ns_map = dict(re.findall(r'xmlns:([A-Za-z0-9_-]+)\s*=\s*"([^"]+)"', xml_text))
    m = re.search(r'xmlns\s*=\s*"([^"]+)"', xml_text)
    if m:
        ns_map[""] = m.group(1)
    return ns_map

def qname_from_tag(tag: str, ns_map: dict):
    if tag.startswith("{"):
        uri, local = tag[1:].split("}",1)
        for p,u in ns_map.items():
            if u == uri and p != "":
                return f"{p}:{local}"
        return f"ns:{local}"
    return tag

def local_from_qname(qn: str):
    return qn.split(":")[-1]

def synth_id(parent_id: str, elem_qn: str, ordinal_path: str):
    basis = f"{parent_id}|{elem_qn}|{ordinal_path}"
    return "syn_" + hashlib.sha1(basis.encode("utf-8")).hexdigest()[:16]

def build_refs_index(references):
    by_owner = {}
    for r in references:
        by_owner.setdefault(r["owner_object"], []).append(r)
    return by_owner

def build_assoc_index(associations):
    by_qn = {}
    for a in associations:
        by_qn[a["qname"]] = a
    return by_qn

def collect_scalar_setters(obj_rule, elem, ns_map):
    setters = []
    for prop in obj_rule.get("scalar_props", []) or []:
        path = prop["path"]  # e.g., "nc:PersonName/nc:PersonGivenName" or "@priv:foo"
        key = prop["prop"]
        ptype = prop.get("type","string")
        value = None

        # attribute path
        if path.startswith("@"):
            # attribute on the current element
            # allow "@structures:id" etc.
            attr_qn = path[1:]
            # resolve attr ns if prefixed
            if ":" in attr_qn:
                pref, local = attr_qn.split(":",1)
                # find attribute by URI
                uri = None
                for p,u in ns_map.items():
                    if p == pref:
                        uri = u
                        break
                if uri:
                    value = elem.attrib.get(f"{{{uri}}}{local}")
                else:
                    value = elem.attrib.get(local)
            else:
                value = elem.attrib.get(attr_qn)
        else:
            # nested element path relative to current element
            cur = elem
            ok = True
            for seg in path.split("/"):
                if not cur is None:
                    # find first child with matching qname
                    found = None
                    for ch in list(cur):
                        if qname_from_tag(ch.tag, ns_map) == seg:
                            found = ch
                            break
                    cur = found
                else:
                    ok = False
                    break
            if ok and cur is not None and (cur.text and cur.text.strip()):
                value = cur.text.strip()

        if value is not None:
            # naive type casting for date/bool/numeric can be added if needed
            # we generate Cypher to set property as string by default
            # escape single quotes
            v = value.replace("'", "\\'")
            setters.append((key, v))
    return setters

def generate_for_xml(xml_path: Path, mapping, obj_rules, associations, references, ns_map):
    # Prepare reference and association indices
    refs_by_owner = build_refs_index(references)
    assoc_by_qn = build_assoc_index(associations)

    xml_text = xml_path.read_text(encoding="utf-8", errors="replace")
    root = ET.fromstring(xml_text)
    xml_ns_map = parse_ns(xml_text)

    nodes = {}   # id -> (label, qname, props_dict)
    edges = []   # (from_id, from_label, to_id, to_label, rel_type, rel_props)
    contains = []# (parent_id, parent_label, child_id, child_label, HAS_REL)

    # Traversal with containment edge creation and synthetic ids
    def traverse(elem, parent_info=None, path_stack=None, counters=None):
        nonlocal nodes, contains, edges
        if path_stack is None: path_stack=[]
        if counters is None: counters=[]
        elem_qn = qname_from_tag(elem.tag, xml_ns_map)

        # Count siblings of same qn at this level for ordinal path
        if not counters or counters[-1].get(elem_qn) is None:
            if counters:
                counters[-1][elem_qn] = 1
            else:
                counters.append({elem_qn:1})
        else:
            counters[-1][elem_qn] += 1
        idx = counters[-1][elem_qn]

        # If element is an Association element (in mapping), produce association edges and do not create a node for it
        assoc_rule = assoc_by_qn.get(elem_qn)
        if assoc_rule:
            # resolve endpoints via child role elements that carry @structures:ref
            endpoints = assoc_rule.get("endpoints", [])
            # find ids per role order
            role_refs = []
            for ep in endpoints:
                role_qn = ep["role_qname"]
                # find matching children with structures:ref
                to_id = None
                for ch in list(elem):
                    if qname_from_tag(ch.tag, xml_ns_map) == role_qn:
                        to_id = ch.attrib.get(f"{{{STRUCT_NS}}}ref")
                        break
                role_refs.append((ep, to_id))
            # If both ends found, produce edge
            if len(role_refs) >= 2 and all(rid for (_, rid) in role_refs[:2]):
                # Map role target ids to labels via nodes table (later merge) or unknown label from maps_to_label
                epA, idA = role_refs[0]
                epB, idB = role_refs[1]
                labelA = None
                labelB = None
                # labelA/labelB: prefer maps_to_label from mapping
                labelA = epA["maps_to_label"]
                labelB = epB["maps_to_label"]
                rel = assoc_rule.get("rel_type")
                # We'll add the edge; actual node creation/merge happens elsewhere
                edges.append((idA, labelA, idB, labelB, rel, {}))
            # Associations are not nodes; still traverse children (in case nested objects exist under)
            for ch in list(elem):
                traverse(ch, parent_info, path_stack, counters)
            return

        # If element is an Object (node)
        obj_rule = obj_rules.get(elem_qn)
        node_id = None
        node_label = None
        props = {}
        if obj_rule:
            node_label = obj_rule["label"]
            sid = elem.attrib.get(f"{{{STRUCT_NS}}}id")
            if sid:
                node_id = sid
            else:
                parent_id = parent_info[0] if parent_info else "root"
                # Ordinal path includes indices to keep stability
                chain = [qname_from_tag(e.tag, xml_ns_map) for e in path_stack] + [elem_qn]
                # Build a parallel index chain
                # We'll recompute a simple index chain by counting occurrences in siblings up the stack
                ordinal_path = "/".join(chain)
                node_id = synth_id(parent_id, elem_qn, ordinal_path)
            # collect scalar props if configured
            setters = collect_scalar_setters(obj_rule, elem, xml_ns_map)
            if setters:
                for k,v in setters:
                    props[k] = v
            # register node
            # merge props if same id appears again
            if node_id in nodes:
                # keep existing label, but extend props (don't overwrite)
                nodes[node_id][2].update({k:v for k,v in props.items() if k not in nodes[node_id][2]})
            else:
                nodes[node_id] = [node_label, elem_qn, props]
            # containment edge
            if parent_info:
                p_id, p_label = parent_info
                rel = "HAS_" + re.sub(r'[^A-Za-z0-9]', '_', local_from_qname(elem_qn)).upper()
                contains.append((p_id, p_label, node_id, node_label, rel))
            parent_ctx = (node_id, node_label)
        else:
            parent_ctx = parent_info

        # Reference edges from mapping.references (owner element → field elements with @structures:ref)
        if elem_qn in refs_by_owner:
            for rule in refs_by_owner[elem_qn]:
                # search children with matching field_qname and @structures:ref
                for ch in list(elem):
                    if qname_from_tag(ch.tag, xml_ns_map) == rule["field_qname"]:
                        to_id = ch.attrib.get(f"{{{STRUCT_NS}}}ref")
                        if to_id:
                            from_id = None
                            if parent_ctx and parent_ctx[0]:
                                from_id = parent_ctx[0] if obj_rule else elem.attrib.get(f"{{{STRUCT_NS}}}id")
                            else:
                                from_id = elem.attrib.get(f"{{{STRUCT_NS}}}id")
                            if from_id:
                                edges.append((from_id, rule["owner_object"].replace(":","_"),
                                              to_id, rule["target_label"],
                                              rule["rel_type"], {}))

        # Recurse
        path_stack.append(elem)
        counters.append({})
        for ch in list(elem):
            traverse(ch, parent_ctx, path_stack, counters)
        counters.pop()
        path_stack.pop()

    # Build refs index once
    refs_by_owner = build_refs_index(references)

    traverse(root, None, [], [])

    # Build Cypher lines
    lines = []
    lines.append(f"// Generated for {xml_path.name} using mapping")
    lines.append("CALL db.tx.ensureStarted();")

    # MERGE nodes
    for nid, (label, qn, props) in nodes.items():
        lines.append(f"MERGE (n:`{label}` {{id:'{nid}'}})")
        setbits = [f"n.qname='{qn}'", f"n.sourceDoc='{xml_path.name}'"]
        for k,v in sorted(props.items()):
            setbits.append(f"n.{k}='{v}'")
        lines.append("  ON CREATE SET " + ", ".join(setbits) + ";")

    # MERGE containment edges
    for a_label in set([x[1] for x in contains]):
        pass
    for pid, plabel, cid, clabel, rel in contains:
        lines.append(f"MATCH (p:`{plabel}` {{id:'{pid}'}}), (c:`{clabel}` {{id:'{cid}'}}) MERGE (p)-[:`{rel}`]->(c);")

    # MERGE reference/association edges
    for fid, flabel, tid, tlabel, rel, rprops in edges:
        # Use backticks for safety
        lines.append(f"MATCH (a:`{flabel}` {{id:'{fid}'}}), (b:`{tlabel}` {{id:'{tid}'}}) MERGE (a)-[:`{rel}`]->(b);")

    lines.append("CALL db.tx.commit();")
    return "\n".join(lines), nodes, contains, edges

def main():
    ap = argparse.ArgumentParser(description="Universal NIEM→Neo4j importer (XML→Cypher) driven by CMF-derived mapping.yaml")
    ap.add_argument("--mapping", required=True, help="Path to mapping.yaml")
    ap.add_argument("--xml", nargs="+", required=True, help="One or more XML files to import")
    ap.add_argument("--out", required=True, help="Output Cypher file")
    args = ap.parse_args()

    mapping, obj_rules, associations, references, ns = load_mapping(Path(args.mapping))

    all_lines = []
    for xml in args.xml:
        xml_path = Path(xml)
        ns_map = ns  # not used directly; kept for future
        cypher, nodes, contains, edges = generate_for_xml(xml_path, mapping, obj_rules, associations, references, ns_map)
        all_lines.append(cypher)

    Path(args.out).write_text("\n\n".join(all_lines), encoding="utf-8")
    print(f"OK: wrote Cypher to {args.out}")

if __name__ == "__main__":
    main()
