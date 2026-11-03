#!/usr/bin/env python3
"""Summarize differences between two workflow JSON files (before -> after).

Usage: python3 diff_workflows.py before.json after.json

Prints added / removed / changed nodes and edges, field by field, so you can
confirm an edit touched only what was intended and write the change summary.
Accepts bare {"nodes", "edges"} or objects wrapping it in "workflow_definition";
also reports changed top-level keys outside workflow_definition.
"""
import json
import sys

IGNORE = {"measured", "selected", "dragging"}


def load(path):
    with open(path, encoding="utf-8") as f:
        doc = json.load(f)
    wd = doc.get("workflow_definition", doc)
    outer = {k: v for k, v in doc.items() if k != "workflow_definition"} if "workflow_definition" in doc else {}
    return wd, outer


def short(v, n=90):
    s = json.dumps(v, ensure_ascii=False)
    return s if len(s) <= n else s[: n - 3] + "..."


def diff_obj(prefix, a, b, out):
    keys = list(dict.fromkeys(list(a) + list(b)))
    for k in keys:
        if k in IGNORE:
            continue
        p = f"{prefix}.{k}" if prefix else k
        if k not in a:
            out.append(f"    + {p} = {short(b[k])}")
        elif k not in b:
            out.append(f"    - {p} (was {short(a[k])})")
        elif isinstance(a[k], dict) and isinstance(b[k], dict):
            diff_obj(p, a[k], b[k], out)
        elif a[k] != b[k]:
            out.append(f"    ~ {p}: {short(a[k], 60)} -> {short(b[k], 60)}")


def section(kind, before, after, describe):
    a = {x.get("id"): x for x in before}
    b = {x.get("id"): x for x in after}
    lines = []
    for i in b:
        if i not in a:
            lines.append(f"  + added {kind} '{i}' {describe(b[i])}")
    for i in a:
        if i not in b:
            lines.append(f"  - removed {kind} '{i}' {describe(a[i])}")
    for i in a:
        if i in b and a[i] != b[i]:
            out = []
            diff_obj("", a[i], b[i], out)
            if out:
                lines.append(f"  ~ changed {kind} '{i}'")
                lines.extend(out)
    unchanged = sum(1 for i in a if i in b and a[i] == b[i])
    return lines, unchanged


def main(p1, p2):
    (w1, o1), (w2, o2) = load(p1), load(p2)
    nd = lambda n: f"({n.get('type')}, name={short((n.get('data') or {}).get('name'), 40)})"
    ed = lambda e: f"({e.get('source')} -> {e.get('target')}, label={short((e.get('data') or {}).get('label'), 30)})"
    n_lines, n_same = section("node", w1.get("nodes", []), w2.get("nodes", []), nd)
    e_lines, e_same = section("edge", w1.get("edges", []), w2.get("edges", []), ed)
    print("NODES")
    print("\n".join(n_lines) or "  (no changes)")
    print(f"  {n_same} node(s) unchanged")
    print("EDGES")
    print("\n".join(e_lines) or "  (no changes)")
    print(f"  {e_same} edge(s) unchanged")
    other = []
    diff_obj("", {k: v for k, v in w1.items() if k not in ("nodes", "edges")},
             {k: v for k, v in w2.items() if k not in ("nodes", "edges")}, other)
    diff_obj("(outer)", o1, o2, other)
    if other:
        print("OTHER")
        print("\n".join(other))


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(2)
    main(sys.argv[1], sys.argv[2])
