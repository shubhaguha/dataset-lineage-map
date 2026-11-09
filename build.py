#!/usr/bin/env python3
"""Build a self-contained dataset-lineage HTML page from a YAML file.

Usage:
    python build.py data/data-quality.yaml data-quality-lineage.html
    python build.py data/data-quality.yaml --check      # validate only

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


def validate(doc):
    """Return (errors, warnings) as lists of strings."""
    errors, warnings = [], []
    for key in ("title", "columns", "kinds", "datasets", "papers", "links"):
        if key not in doc:
            errors.append(f"missing top-level key: {key}")
    if errors:
        return errors, warnings

    kinds = doc["kinds"]
    for k, v in kinds.items():
        if not isinstance(v, dict) or "label" not in v or "color" not in v:
            errors.append(f"kinds.{k}: needs label and color")
        elif v["color"] not in COLORS:
            errors.append(f"kinds.{k}: color must be one of {sorted(COLORS)}")
    if "paper" not in kinds:
        errors.append("kinds: a 'paper' kind is required")

    ncols = len(doc["columns"])
    ids, col_of, row_of = set(), {}, {}

    def add_id(i, where):
        if i in ids:
            errors.append(f"{where}: duplicate id '{i}'")
        ids.add(i)

    for n, d in enumerate(doc["datasets"]):
        where = f"datasets[{n}] ({d.get('id', '?')})"
        for f in ("id", "name", "kind"):
            if not d.get(f):
                errors.append(f"{where}: missing {f}")
        if d.get("kind") and d["kind"] not in kinds:
            errors.append(f"{where}: unknown kind '{d['kind']}'")
        if d.get("id"):
            add_id(d["id"], where)
            col_of[d["id"]], row_of[d["id"]] = 0, n

    for n, p in enumerate(doc["papers"]):
        where = f"papers[{n}] ({p.get('id', '?')})"
        for f in ("id", "name", "column", "row"):
            if p.get(f) is None:
                errors.append(f"{where}: missing {f}")
        c = p.get("column")
        if isinstance(c, int) and not 1 <= c < ncols:
            errors.append(f"{where}: column {c} outside 1..{ncols - 1}")
        if p.get("kind") and p["kind"] not in kinds:
            errors.append(f"{where}: unknown kind '{p['kind']}'")
        if p.get("id"):
            add_id(p["id"], where)
            col_of[p["id"]], row_of[p["id"]] = c, p.get("row")

    # boxes in the same column must not overlap (box height is ~0.8 row)
    by_col = {}
    for i in ids:
        if isinstance(row_of.get(i), (int, float)):
            by_col.setdefault(col_of[i], []).append((row_of[i], i))
    for c, items in by_col.items():
        items.sort()
        for (r1, a), (r2, b) in zip(items, items[1:]):
            if r2 - r1 < 0.8:
                warnings.append(f"column {c}: '{a}' (row {r1}) and '{b}' (row {r2}) overlap")

    ds_ids = {d.get("id") for d in doc["datasets"]}
    used_ds = set()
    for n, l in enumerate(doc["links"]):
        where = f"links[{n}] ({l.get('from', '?')} -> {l.get('to', '?')})"
        for f in ("from", "to", "label", "datasets"):
            if not l.get(f):
                errors.append(f"{where}: missing {f}")
        for end in ("from", "to"):
            if l.get(end) and l[end] not in ids:
                errors.append(f"{where}: unknown {end} '{l[end]}'")
        if l.get("to") in ds_ids:
            errors.append(f"{where}: 'to' must be a paper, not a dataset")
        if l.get("how", "paper") not in HOW:
            errors.append(f"{where}: how must be one of {sorted(HOW)}")
        for k in l.get("datasets") or []:
            if k not in ds_ids:
                errors.append(f"{where}: unknown dataset '{k}'")
            used_ds.add(k)
        if l.get("from") in ds_ids and l["from"] not in (l.get("datasets") or []):
            warnings.append(f"{where}: starts at dataset '{l['from']}' but doesn't list it in datasets")
        cf, ct = col_of.get(l.get("from")), col_of.get(l.get("to"))
        if isinstance(cf, int) and isinstance(ct, int) and cf >= ct:
            warnings.append(f"{where}: runs from column {cf} to {ct} (not left to right)")
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

    doc = yaml.safe_load(args.data.read_text(encoding="utf-8"))
    errors, warnings = validate(doc)
    for w in warnings:
        print(f"warning: {w}", file=sys.stderr)
    for e in errors:
        print(f"error: {e}", file=sys.stderr)
    if errors:
        sys.exit(1)
    summary = f"{len(doc['datasets'])} datasets, {len(doc['papers'])} papers, {len(doc['links'])} links"
    if args.check or not args.out:
        print(f"OK: {summary}")
        return
    args.out.write_text(build(doc), encoding="utf-8")
    print(f"wrote {args.out} ({summary})")


if __name__ == "__main__":
    main()
