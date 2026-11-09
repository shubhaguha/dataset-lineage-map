#!/usr/bin/env python3
"""Build a self-contained dataset-lineage HTML page from a YAML file.

Usage:
    python build.py data/data-quality.yaml data-quality-lineage.html
    python build.py data/data-quality.yaml --check      # validate only

A data file may start with `extends: other.yaml` to build on another map
(see load()).

Requires PyYAML (pip install pyyaml). The output is a single HTML file that
opens directly from disk; the template lives in template/lineage.html.
"""
import argparse
import json
import sys
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
TEMPLATE = HERE / "template" / "lineage.html"
PLACEHOLDER = "/*__LINEAGE_DATA__*/"
COLORS = {"series-1", "series-2", "series-3", "series-4", "neutral"}
HOW = {"paper", "inferred"}


LIST_KEYS = ("datasets", "papers", "nodes")
DICT_KEYS = ("kinds", "statuses", "link_types", "layout", "links_legend")


def load(path, _seen=()):
    """Load a YAML file, resolving `extends:` (path relative to the file).

    In the extending file, list entries (datasets/papers/nodes) whose id already
    exists patch the base entry field by field; new ids are appended. Links are
    appended. Dict sections (kinds, statuses, ...) are merged; other keys override.
    """
    path = Path(path).resolve()
    if path in _seen:
        raise SystemExit(f"extends cycle at {path}")
    doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    base_ref = doc.pop("extends", None)
    if not base_ref:
        return doc
    base = load(path.parent / base_ref, _seen + (path,))
    for k, v in doc.items():
        if k in LIST_KEYS:
            items = base.setdefault(k, [])
            index = {it.get("id"): it for it in items}
            for it in v or []:
                if it.get("id") in index:
                    index[it["id"]].update(it)
                else:
                    items.append(it)
        elif k == "links":
            base.setdefault("links", []).extend(v or [])
        elif k in DICT_KEYS and isinstance(v, dict):
            base.setdefault(k, {}).update(v)
        else:
            base[k] = v
    return base


def validate(doc):
    """Return (errors, warnings) as lists of strings."""
    errors, warnings = [], []
    for key in ("title", "columns", "kinds", "links"):
        if key not in doc:
            errors.append(f"missing top-level key: {key}")
    if not any(doc.get(k) for k in LIST_KEYS):
        errors.append("need at least one of: datasets, papers, nodes")
    if errors:
        return errors, warnings

    kinds = doc["kinds"]
    for k, v in kinds.items():
        if not isinstance(v, dict) or "label" not in v or "color" not in v:
            errors.append(f"kinds.{k}: needs label and color")
        elif v["color"] not in COLORS:
            errors.append(f"kinds.{k}: color must be one of {sorted(COLORS)}")
    statuses = doc.get("statuses")
    link_types = set(doc.get("link_types") or HOW)
    field_keys = {f.get("key") for f in doc.get("node_fields") or []}
    lay = {"node_width": 170, "node_height": 46, "top": 52, "row_height": 58,
           "first_x": 24, "first_gap": 276, "col_gap": 220, **(doc.get("layout") or {})}
    ncols = len(doc["columns"])
    col_x = [lay["first_x"] + (0 if i == 0 else lay["first_gap"] + (i - 1) * lay["col_gap"]) for i in range(ncols)]
    ids, pos = set(), {}

    def add_id(i, where):
        if i in ids:
            errors.append(f"{where}: duplicate id '{i}'")
        ids.add(i)

    for n, d in enumerate(doc.get("datasets") or []):
        where = f"datasets[{n}] ({d.get('id', '?')})"
        for f in ("id", "name", "kind"):
            if not d.get(f):
                errors.append(f"{where}: missing {f}")
        if d.get("kind") and d["kind"] not in kinds:
            errors.append(f"{where}: unknown kind '{d['kind']}'")
        if d.get("id"):
            add_id(d["id"], where)
            y = d.get("y", lay["top"] + d.get("row", n) * lay["row_height"])
            pos[d["id"]] = (d.get("x", col_x[0]), y)

    nodes = [("papers", p) for p in doc.get("papers") or []] + [("nodes", p) for p in doc.get("nodes") or []]
    for n, (sect, p) in enumerate(nodes):
        where = f"{sect} ({p.get('id', '?')})"
        for f in ("id", "name", "column"):
            if p.get(f) is None:
                errors.append(f"{where}: missing {f}")
        if p.get("row") is None and p.get("y") is None:
            errors.append(f"{where}: needs row or y")
        c = p.get("column")
        if isinstance(c, int) and not 0 <= c < ncols:
            errors.append(f"{where}: column {c} outside 0..{ncols - 1}")
        kind = p.get("kind", "paper")
        if kind not in kinds:
            errors.append(f"{where}: unknown kind '{kind}'")
        if p.get("status") is not None and statuses is not None and p["status"] not in statuses:
            errors.append(f"{where}: unknown status '{p['status']}'")
        for k in (p.get("attrs") or {}):
            if k not in field_keys:
                warnings.append(f"{where}: attrs.{k} is not declared in node_fields (won't be shown)")
        for r in p.get("refs") or []:
            if not r.get("url") or not r.get("label"):
                errors.append(f"{where}: each ref needs label and url")
        if p.get("id"):
            add_id(p["id"], where)
            if isinstance(c, int) and 0 <= c < ncols:
                y = p["y"] if p.get("y") is not None else lay["top"] + (p.get("row") or 0) * lay["row_height"]
                pos[p["id"]] = (p.get("x", col_x[c]), y)

    # boxes at the same x must not overlap
    by_x = {}
    for i, (x, y) in pos.items():
        by_x.setdefault(x, []).append((y, i))
    for x, items in by_x.items():
        items.sort()
        for (y1, a), (y2, b) in zip(items, items[1:]):
            if y2 - y1 < lay["node_height"] + 2:
                warnings.append(f"x={x}: '{a}' and '{b}' overlap")

    ds_ids = {d.get("id") for d in doc.get("datasets") or []}
    used_ds = set()
    for n, l in enumerate(doc["links"]):
        where = f"links[{n}] ({l.get('from', '?')} -> {l.get('to', '?')})"
        for f in ("from", "to"):
            if not l.get(f):
                errors.append(f"{where}: missing {f}")
        if ds_ids and not l.get("datasets"):
            errors.append(f"{where}: missing datasets")
        for end in ("from", "to"):
            if l.get(end) and l[end] not in ids:
                errors.append(f"{where}: unknown {end} '{l[end]}'")
        if l.get("to") in ds_ids:
            errors.append(f"{where}: 'to' must be a paper/node, not a dataset")
        how = l.get("how", next(iter(link_types)) if doc.get("link_types") else "paper")
        if how not in link_types:
            errors.append(f"{where}: how must be one of {sorted(link_types)}")
        for k in l.get("datasets") or []:
            if k not in ds_ids:
                errors.append(f"{where}: unknown dataset '{k}'")
            used_ds.add(k)
        if l.get("from") in ds_ids and l["from"] not in (l.get("datasets") or []):
            warnings.append(f"{where}: starts at dataset '{l['from']}' but doesn't list it in datasets")
        pf, pt = pos.get(l.get("from")), pos.get(l.get("to"))
        if pf and pt and pf[0] >= pt[0]:
            warnings.append(f"{where}: doesn't run left to right")
        lp = l.get("label_pos")
        if lp is not None and not 0 <= lp <= 1:
            errors.append(f"{where}: label_pos must be between 0 and 1")

    for k in sorted(ds_ids - used_ds - {None}):
        warnings.append(f"dataset '{k}' is not used by any link")
    return errors, warnings


def build(doc):
    template = TEMPLATE.read_text(encoding="utf-8")
    if template.count(PLACEHOLDER) != 1:
        raise SystemExit(f"template must contain {PLACEHOLDER} exactly once")
    payload = json.dumps(doc, ensure_ascii=False, separators=(",", ":"))
    payload = payload.replace("</", "<\\/")  # keep '</script>' inside strings from closing the tag
    return template.replace(PLACEHOLDER, payload)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("data", type=Path, help="YAML data file")
    ap.add_argument("out", type=Path, nargs="?", help="output HTML file")
    ap.add_argument("--check", action="store_true", help="validate only, don't write")
    args = ap.parse_args()

    doc = load(args.data)
    errors, warnings = validate(doc)
    for w in warnings:
        print(f"warning: {w}", file=sys.stderr)
    for e in errors:
        print(f"error: {e}", file=sys.stderr)
    if errors:
        sys.exit(1)
    summary = ", ".join(f"{len(doc[k])} {k}" for k in LIST_KEYS + ("links",) if doc.get(k))
    if args.check or not args.out:
        print(f"OK: {summary}")
        return
    args.out.write_text(build(doc), encoding="utf-8")
    print(f"wrote {args.out} ({summary})")


if __name__ == "__main__":
    main()
