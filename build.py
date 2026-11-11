#!/usr/bin/env python3
"""Build dataset-lineage pages from YAML.

Usage:
    python build.py                       # whole site: every data/maps/*.yaml, the
                                          # knowledge base (data/kb.yaml) and an index, into docs/
    python build.py --check               # validate everything, write nothing
    python build.py data/maps/data-quality.yaml out.html   # one standalone map page
    python build.py data/maps/data-quality.yaml --check

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
KB_TEMPLATE = HERE / "template" / "kb.html"
INDEX_TEMPLATE = HERE / "template" / "index.html"
MAPS_DIR = HERE / "data" / "maps"
KB_FILE = HERE / "data" / "kb.yaml"
DOCS = HERE / "docs"
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


def place(doc):
    """Auto-layout for maps with `year_columns` (optional; does nothing otherwise).

    Each node gets a column from its `year` (or `place_year` when the year is a
    range or unknown): the first year column whose `until` is >= the year, or a
    column listing the node's kind under `kinds`. A column without `until` or
    `kinds` takes every later year. Within each lane (`lane:` = a lanes[].id) the
    nodes of a column are stacked in file order, and lane bands are sized to fit.
    Nodes that already have `column` and `y` keep them.
    """
    yc = doc.get("year_columns")
    if not yc:
        return doc, []
    errors = []
    lay = {"node_height": 46, "top": 52, "row_height": 58, "lane_gap": 14,
           "lane_pad_top": 28, "lane_pad_bottom": 12, **(doc.get("layout") or {})}
    doc["columns"] = [c.get("label", "") for c in yc]

    def column_for(n):
        kind = n.get("kind")
        for i, c in enumerate(yc):
            if kind in (c.get("kinds") or []):
                return i
        year = n.get("place_year", n.get("year"))
        if not isinstance(year, int):
            return None
        for i, c in enumerate(yc):
            if c.get("kinds"):
                continue
            if c.get("until") is None or year <= c["until"]:
                return i
        return None

    lanes = doc.get("lanes") or []
    lane_ids = [l.get("id") for l in lanes]
    cells = {}
    for n in doc.get("nodes") or []:
        where = f"nodes ({n.get('id', '?')})"
        if n.get("column") is None:
            c = column_for(n)
            if c is None:
                errors.append(f"{where}: needs an integer year or place_year matching a year column")
                continue
            n["column"] = c
        if n.get("y") is None:
            if n.get("lane") not in lane_ids:
                errors.append(f"{where}: lane must be one of {lane_ids}")
                continue
            cells.setdefault((n["lane"], n["column"]), []).append(n)
    rows = {}  # node id -> row index within its lane
    for (lid, _), v in cells.items():
        for i, n in enumerate(v):
            rows[n["id"]] = i
    if lay.get("auto_rows"):
        rows = optimise_rows(doc, cells, rows, lay)
    y = lay["top"]
    for l in lanes:
        members = [n for (lid, _), v in cells.items() if lid == l.get("id") for n in v]
        stack = max([rows[n["id"]] + 1 for n in members] or [1])
        if l.get("y") is None:
            l["y"] = y
            l["h"] = lay["lane_pad_top"] + (stack - 1) * lay["row_height"] + lay["node_height"] + lay["lane_pad_bottom"]
            l.setdefault("label_y", l["y"] + 18)
        for n in members:
            n["y"] = l["y"] + lay["lane_pad_top"] + rows[n["id"]] * lay["row_height"]
        y = l["y"] + l["h"] + lay["lane_gap"]
    if lanes and not (doc.get("layout") or {}).get("height"):
        doc.setdefault("layout", {})["height"] = max(l["y"] + l["h"] for l in lanes) + 10
    return doc, errors


def _col_x(lay, c):
    return lay["first_x"] + (0 if c == 0 else lay["first_gap"] + (c - 1) * lay["col_gap"])


def optimise_rows(doc, cells, rows, lay):
    """Choose a row per node (within its lane and column) so that links (all but
    `quiet` link types) do not pass behind other boxes, using the same curves as the renderer. Local
    search from file order; deterministic. A node with `lane_row` is pinned."""
    W, H, RH = lay.get("node_width", 170), lay["node_height"], lay["row_height"]
    lt = doc.get("link_types") or {}
    nodes = {n["id"]: n for v in cells.values() for n in v}
    links = [(l["from"], l["to"]) for l in doc.get("links") or []
             if not (lt.get(l.get("how")) or {}).get("quiet")
             and l["from"] in nodes and l["to"] in nodes and nodes[l["from"]]["lane"] == nodes[l["to"]]["lane"]]
    for v in cells.values():
        for n in v:
            if n.get("lane_row") is not None:
                rows[n["id"]] = n["lane_row"]

    def cost(lane, r):
        ids = [i for i in nodes if nodes[i]["lane"] == lane]
        box = {i: (_col_x(lay, nodes[i]["column"]), r[i] * RH) for i in ids}
        c = 0.0
        for a, b in links:
            if nodes[a]["lane"] != lane:
                continue
            (xa, ya), (xb, yb) = box[a], box[b]
            if xa == xb:  # vertical link: target must sit right below
                c += (yb - ya) / RH if yb > ya else 1000
                c += 50 * sum(1 for i in ids if box[i][0] == xa and ya < box[i][1] < yb)
                continue
            if xa > xb:
                continue
            x1, y1, x2, y2 = xa + W, ya + H / 2, xb - 2, yb + H / 2
            dx = max(lay.get("min_curve", 40), (x2 - x1) / 2)
            hit = set()
            for k in range(1, 80):
                u = k / 80; m = 1 - u
                px = m**3 * x1 + 3 * m * m * u * (x1 + dx) + 3 * m * u * u * (x2 - dx) + u**3 * x2
                py = m**3 * y1 + 3 * m * m * u * y1 + 3 * m * u * u * y2 + u**3 * y2
                for i in ids:
                    if i not in (a, b):
                        bx, by = box[i]
                        if bx - 4 <= px <= bx + W + 4 and by - 3 <= py <= by + H + 3:
                            hit.add(i)
            c += 100 * len(hit) + abs(y2 - y1) / RH * 0.5
        return c + 3 * max(r[i] for i in ids) + 0.05 * sum(r[i] for i in ids)

    import random
    rng = random.Random(0)
    for lane in sorted({n["lane"] for n in nodes.values()}, key=str):
        ids = [i for i in nodes if nodes[i]["lane"] == lane]
        free = [i for i in ids if nodes[i].get("lane_row") is None]
        R = max(len(v) for (lid, _), v in cells.items() if lid == lane) + 2
        starts = [dict(rows)]
        for _ in range(int(lay.get("auto_rows_restarts", 24))):  # random row orders within each column
            st = dict(rows)
            for (lid, _), v in cells.items():
                if lid == lane:
                    fr = [n["id"] for n in v if n["id"] in free]
                    slots = sorted(st[i] for i in fr)
                    rng.shuffle(fr)
                    st.update(zip(fr, slots))
            starts.append(st)
        best_rows, best_cost = None, None
        for cur in starts:
            cur_cost = cost(lane, cur)
            improved = True
            while improved:
                improved = False
                for i in free:
                    for row in range(R):
                        if row == cur[i]:
                            continue
                        trial = dict(cur)
                        other = [j for j in ids if j != i and nodes[j]["column"] == nodes[i]["column"] and trial[j] == row]
                        if other and other[0] not in free:
                            continue
                        for j in other:
                            trial[j] = cur[i]
                        trial[i] = row
                        lo = min(trial[k] for k in ids)  # keep the top row used
                        for k in ids:
                            trial[k] -= lo
                        c = cost(lane, trial)
                        if c < cur_cost - 1e-9:
                            cur, cur_cost, improved = trial, c, True
            if best_cost is None or cur_cost < best_cost - 1e-9:
                best_rows, best_cost = cur, cur_cost
        rows = best_rows
    return rows


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
        if pf and pt and (pf[0] > pt[0] or (pf[0] == pt[0] and pt[1] <= pf[1])):
            warnings.append(f"{where}: doesn't run left to right (or downwards within a column)")
        elif pf and pt and pf[0] == pt[0]:
            between = [i for i, (x, y) in pos.items() if x == pf[0] and pf[1] < y < pt[1]]
            if between:
                warnings.append(f"{where}: vertical link passes behind {between}")
        lp = l.get("label_pos")
        if lp is not None and not 0 <= lp <= 1:
            errors.append(f"{where}: label_pos must be between 0 and 1")

    for n, t in enumerate(doc.get("toggles") or []):
        if not t.get("label") or not t.get("kinds"):
            errors.append(f"toggles[{n}]: needs label and kinds")
        for k in t.get("kinds") or []:
            if k not in kinds:
                errors.append(f"toggles[{n}]: unknown kind '{k}'")
        if t.get("default", "show") not in ("show", "grey", "hide"):
            errors.append(f"toggles[{n}]: default must be show, grey or hide")

    for k in sorted(ds_ids - used_ds - {None}):
        warnings.append(f"dataset '{k}' is not used by any link")
    return errors, warnings


def build(doc, template_path=TEMPLATE):
    template = Path(template_path).read_text(encoding="utf-8")
    if template.count(PLACEHOLDER) != 1:
        raise SystemExit(f"template must contain {PLACEHOLDER} exactly once")
    payload = json.dumps(doc, ensure_ascii=False, separators=(",", ":"))
    payload = payload.replace("</", "<\\/")  # keep '</script>' inside strings from closing the tag
    return template.replace(PLACEHOLDER, payload)


# Fields of a traced (left-column) dataset that the knowledge base shows per map.
MAP_DS_FIELDS = [("source_full", "Original source"), ("aka", "Also called"), ("real", "Real or synthetic"),
                 ("path", "Path to recent benchmarks"), ("sizes", "Sizes as reported"), ("get", "Where to get it"),
                 ("note", "Note"), ("url", "Source link")]


def validate_kb(kb):
    errors, warnings = [], []
    topics = set((kb.get("topics") or {}).keys())
    fields = {f.get("key") for f in kb.get("fields") or []}
    ids = set()
    for n, r in enumerate(kb.get("records") or []):
        where = f"kb records[{n}] ({r.get('id', '?')})"
        if not r.get("id") or not r.get("name"):
            errors.append(f"{where}: needs id and name")
        if r.get("id") in ids:
            errors.append(f"{where}: duplicate id")
        ids.add(r.get("id"))
        for t in r.get("topics") or []:
            if t not in topics:
                errors.append(f"{where}: unknown topic '{t}'")
        for k in r:
            if k not in fields | {"id", "name", "topics"}:
                warnings.append(f"{where}: field '{k}' is not declared in fields (won't be shown)")
    types = {f["key"]: f.get("type") for f in kb.get("fields") or []}
    for r in kb.get("records") or []:
        for k, t in types.items():
            if t == "ids":
                for i in r.get(k) or []:
                    if i not in ids:
                        errors.append(f"kb record {r['id']}: {k} names unknown record '{i}'")
    return errors, warnings


def build_site(check=False):
    """Build every map in data/maps/, the knowledge base and an index into docs/."""
    kb = yaml.safe_load(KB_FILE.read_text(encoding="utf-8")) if KB_FILE.exists() else None
    problems = 0
    if kb:
        errors, warnings = validate_kb(kb)
        for w in warnings:
            print(f"warning: kb: {w}", file=sys.stderr)
        for e in errors:
            print(f"error: kb: {e}", file=sys.stderr)
        problems += len(errors)
    records = {r["id"]: r for r in (kb or {}).get("records") or []}
    for r in records.values():
        r["maps"] = []
    nav = [{"label": "All maps", "href": "index.html"}] + ([{"label": "Knowledge base", "href": "kb.html"}] if kb else [])
    pages, outputs = [], {}
    for path in sorted(MAPS_DIR.glob("*.yaml")):
        doc, errors = place(load(path))
        warnings = []
        if not errors:
            errors, warnings = validate(doc)
        for w in warnings:
            print(f"warning: {path.name}: {w}", file=sys.stderr)
        for e in errors:
            print(f"error: {path.name}: {e}", file=sys.stderr)
        problems += len(errors)
        if errors:
            continue
        href = path.stem + ".html"
        kb_ids, unmatched = {}, []
        boxes = [("ds", d) for d in doc.get("datasets") or []] + [("node", n) for n in doc.get("nodes") or []]
        for sect, b in boxes:
            k = b.get("kb", b["id"])
            if k is False:
                continue
            if k in records:
                kb_ids[b["id"]] = k
                entry = {"title": doc["title"], "href": f"{href}#{b['id']}", "box": b["name"]}
                if sect == "ds":
                    entry["fields"] = [[lab, b[key]] for key, lab in MAP_DS_FIELDS if b.get(key)]
                records[k]["maps"].append(entry)
            elif sect == "ds" or b.get("kind") in (doc.get("kinds") or {}) and not any(
                    b.get("kind") in t.get("kinds", []) for t in doc.get("toggles") or []):
                unmatched.append(b["id"])
        if kb and unmatched:
            print(f"note: {path.name}: no knowledge-base record for {', '.join(unmatched)}", file=sys.stderr)
        doc["site"] = {"nav": nav, "kb_page": "kb.html" if kb else None, "kb_ids": kb_ids}
        n_boxes = len(boxes)
        pages.append({"href": href, "title": doc["title"], "intro": doc.get("intro", ""),
                      "counts": f"{n_boxes} boxes, {len(doc['links'])} links"})
        outputs[href] = (doc, TEMPLATE)
    # Records without their own `source` take the original source from the first map that traces them.
    if kb and any(f.get("key") == "source" for f in kb.get("fields") or []):
        for r in records.values():
            if not r.get("source"):
                for m in r["maps"]:
                    src = dict(m.get("fields") or []).get("Original source")
                    if src:
                        r["source"] = src
                        break
    if kb:
        kb["site"] = {"nav": nav, "maps": [{"href": p["href"], "title": p["title"]} for p in pages]}
        outputs["kb.html"] = (kb, KB_TEMPLATE)
    index = {"title": "Dataset lineage maps", "intro": "Interactive maps of where datasets come from and how they are reused, built from YAML.",
             "maps": pages, "kb": {"href": "kb.html", "count": len(records), "intro": kb.get("intro", "")} if kb else None}
    outputs["index.html"] = (index, INDEX_TEMPLATE)
    if problems:
        sys.exit(1)
    if check:
        print(f"OK: {len(pages)} maps" + (f", {len(records)} knowledge-base records" if kb else ""))
        return
    DOCS.mkdir(exist_ok=True)
    (DOCS / ".nojekyll").write_text("", encoding="utf-8")
    for name, (doc, tpl) in outputs.items():
        (DOCS / name).write_text(build(doc, tpl), encoding="utf-8")
        print(f"wrote docs/{name}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("data", type=Path, nargs="?", help="YAML map file (omit to build the whole site)")
    ap.add_argument("out", type=Path, nargs="?", help="output HTML file")
    ap.add_argument("--check", action="store_true", help="validate only, don't write")
    args = ap.parse_args()
    if args.data is None:
        build_site(check=args.check)
        return

    doc, errors = place(load(args.data))
    if not errors:
        errors, warnings = validate(doc)
    else:
        warnings = []
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
