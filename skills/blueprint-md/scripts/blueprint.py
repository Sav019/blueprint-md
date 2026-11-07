#!/usr/bin/env python3
"""blueprint-md: turn one architecture.yaml into a diagram and an agent-ready ARCHITECTURE.md.

Usage:
  python3 blueprint.py build architecture.yaml [--out DIR] [--png] [--offline]
  python3 blueprint.py check architecture.yaml
  python3 blueprint.py catalog [words…] [--write PATH] [--check] [--no-links]
  python3 blueprint.py icons aws|azure|gcp [words…] [--update]

build   writes <name>.html (self-contained diagram), ARCHITECTURE.md and, with --png,
        <name>.png + <name>-dark.png (needs Playwright: pip install playwright &&
        python3 -m playwright install chromium)
check   parses, lays out and routes the diagram and prints warnings without writing files
catalog lists the building blocks (filter with words), writes them as a Markdown page,
        or checks entries, review dates and docs links
icons   searches the official cloud icon packs (downloaded once, cached in ~/.cache/blueprint-md)

Icons are fetched on first use and cached in .blueprint/icons/ next to the YAML file.
Requires PyYAML (pip install pyyaml).
"""
import argparse
import base64
import html
import json
import pathlib
import re
import sys
import urllib.parse
import urllib.request

try:
    import yaml
except ImportError:
    sys.exit("blueprint-md needs PyYAML: pip install pyyaml")

# ── geometry (px) ─────────────────────────────────────────────────────────────
TILE = 60                 # icon tile is TILE x TILE, at the top of a node
BOX_W, BOX_H = 136, 104   # a node = tile + name + kind; edges never cross this box
GAP = 5                   # space between an edge end and the node
PAD_SIDE, PAD_TOP, PAD_BOTTOM = 22, 46, 20   # group padding (label lives in PAD_TOP)
MARGIN = 36
DEFAULT_GRID = {"col": 200, "row": 190}

ARROW = re.compile(r"^\s*([\w.-]+)\s*(<\.\.>|\.\.>|<->|->|--)\s*([\w.-]+)\s*$")
OPS = {  # operator -> (dashed, arrow at end, arrow at start)
    "->": (False, True, False), "<->": (False, True, True),
    "..>": (True, True, False), "<..>": (True, True, True), "--": (False, False, False),
}
COLORS = {  # group color -> oklch hue, chroma
    "blue": (255, .16), "orange": (55, .15), "violet": (300, .15), "green": (150, .13),
    "teal": (195, .11), "red": (25, .16), "pink": (350, .14), "gray": (255, .015),
}


class BlueprintError(Exception):
    pass


# ── catalog ───────────────────────────────────────────────────────────────────
CATALOG_DIR = pathlib.Path(__file__).resolve().parent.parent / "catalog"
CATALOG_FIELDS = ("name", "kind", "category", "icon", "what", "use_when", "avoid_when",
                  "connects_with", "docs", "checked")


def load_catalog(extra_files=()):
    """Return {type: entry} from the bundled catalog/*.yaml plus any extra catalog files."""
    entries = {}
    files = sorted(CATALOG_DIR.glob("*.yaml")) + [pathlib.Path(f) for f in extra_files]
    for f in files:
        try:
            data = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
        except (OSError, yaml.YAMLError) as e:
            raise BlueprintError(f"error: catalog {f}: {e}")
        for type_id, entry in (data.get("entries") or {}).items():
            entry = dict(entry or {})
            unknown = set(entry) - set(CATALOG_FIELDS)
            if unknown:
                raise BlueprintError(f"error: catalog {f.name} '{type_id}': unknown field(s) {', '.join(sorted(unknown))}")
            entry.update(type=type_id, catalog=data.get("title", f.stem), file=f.name)
            entries[type_id] = entry
    return entries


def suggest(word, options):
    import difflib
    close = difflib.get_close_matches(word, options, n=3, cutoff=0.5)
    return f" (did you mean {', '.join(close)}?)" if close else ""


# ── model ─────────────────────────────────────────────────────────────────────
def load(path):
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as e:
        raise BlueprintError(f"{path}: invalid YAML\n{e}")
    errors, warnings = [], []
    grid = {**DEFAULT_GRID, **(data.get("grid") or {})}
    catalog = load_catalog(path.parent / f for f in (data.get("catalogs") or []))

    groups = {}
    for gid, g in (data.get("groups") or {}).items():
        g = g or {}
        color = g.get("color", "gray")
        if color not in COLORS:
            errors.append(f"group '{gid}': unknown color '{color}' (use {', '.join(COLORS)})")
        groups[gid] = {"id": gid, "label": str(g.get("label", gid)), "icon": g.get("icon"),
                       "color": color, "parent": g.get("parent"), "about": g.get("about", ""),
                       "dashed": bool(g.get("dashed"))}
    for g in groups.values():
        if g["parent"] and g["parent"] not in groups:
            errors.append(f"group '{g['id']}': parent '{g['parent']}' is not a group")

    comps = {}
    for cid, c in (data.get("components") or {}).items():
        c = c or {}
        at = c.get("at")
        if not (isinstance(at, (list, tuple)) and len(at) == 2):
            errors.append(f"component '{cid}': needs 'at: [column, row]'")
            continue
        if c.get("group") and c["group"] not in groups:
            errors.append(f"component '{cid}': group '{c['group']}' is not defined")
        block = {}
        if c.get("type"):
            block = catalog.get(c["type"], {})
            if not block:
                warnings.append(f"component '{cid}': type '{c['type']}' is not in the catalog"
                                f"{suggest(c['type'], list(catalog))}; run 'blueprint.py catalog' to list types")
        comps[cid] = {"id": cid, "name": str(c.get("name") or block.get("name") or cid),
                      "kind": str(c.get("kind") or block.get("kind") or ""),
                      "icon": c.get("icon") or block.get("icon"), "group": c.get("group"),
                      "tile": c.get("tile", ""), "col": float(at[0]), "row": float(at[1]),
                      "about": c.get("about", ""), "tech": c.get("tech", ""), "code": c.get("code", ""),
                      "type": c.get("type", ""), "block": block}

    conns = []
    for i, raw in enumerate(data.get("connections") or [], 1):
        if isinstance(raw, str):
            raw = {raw: ""}
        key = next((k for k in raw if isinstance(k, str) and ARROW.match(k)), None)
        if key is None:
            errors.append(f"connection #{i}: write it as 'from -> to: label' "
                          f"(operators: {', '.join(OPS)})")
            continue
        src, op, dst = ARROW.match(key).groups()
        for end in (src, dst):
            if end not in comps:
                errors.append(f"connection #{i} '{key}': unknown component '{end}'")
        dashed, end_arrow, start_arrow = OPS[op]
        conns.append({"n": i, "src": src, "dst": dst, "op": op,
                      "label": "" if raw[key] is None else str(raw[key]),
                      "primary": bool(raw.get("primary")), "dashed": dashed,
                      "end_arrow": end_arrow, "start_arrow": start_arrow,
                      "about": raw.get("about", ""), "protocol": raw.get("protocol", ""),
                      "data": raw.get("data", ""), "route": raw.get("route")})

    flows = []
    for name, steps in (data.get("flows") or {}).items():
        bad = [s for s in steps or [] if s not in comps]
        if bad:
            errors.append(f"flow '{name}': unknown component(s) {', '.join(bad)}")
        flows.append({"name": name, "steps": steps or []})

    if errors:
        raise BlueprintError("\n".join(f"error: {e}" for e in errors))
    return {"title": data.get("title", path.stem), "summary": data.get("summary", ""),
            "grid": grid, "groups": groups, "comps": comps, "conns": conns, "flows": flows,
            "decisions": data.get("decisions") or [], "notes": data.get("notes", ""),
            "legend": data.get("legend") or {}, "source": path.name, "warnings": warnings}


# ── layout ────────────────────────────────────────────────────────────────────
def node_box(c):
    return (c["cx"] - BOX_W / 2, c["top"], c["cx"] + BOX_W / 2, c["top"] + BOX_H)


def group_children(m, gid):
    return [g for g in m["groups"].values() if g["parent"] == gid]


def layout(m):
    col, row = m["grid"]["col"], m["grid"]["row"]
    for c in m["comps"].values():
        c["cx"], c["top"] = c["col"] * col, c["row"] * row

    def box(g):
        rects = [node_box(c) for c in m["comps"].values() if c["group"] == g["id"]]
        rects += [box(ch) for ch in group_children(m, g["id"])]
        if not rects:
            raise BlueprintError(f"error: group '{g['id']}' has no components")
        g["rect"] = (min(r[0] for r in rects) - PAD_SIDE, min(r[1] for r in rects) - PAD_TOP,
                     max(r[2] for r in rects) + PAD_SIDE, max(r[3] for r in rects) + PAD_BOTTOM)
        return g["rect"]

    for g in m["groups"].values():
        if not g["parent"]:
            box(g)
    rects = [node_box(c) for c in m["comps"].values()] + [g["rect"] for g in m["groups"].values()]
    if not rects:
        raise BlueprintError("error: no components defined")
    dx, dy = MARGIN - min(r[0] for r in rects), MARGIN - min(r[1] for r in rects)
    for c in m["comps"].values():
        c["cx"] += dx
        c["top"] += dy
    for g in m["groups"].values():
        x0, y0, x1, y1 = g["rect"]
        g["rect"] = (x0 + dx, y0 + dy, x1 + dx, y1 + dy)
        g["label_rect"] = (x0 + dx + 10, y0 + dy + 8, x0 + dx + 30 + 7.2 * len(g["label"]), y0 + dy + 32)
    m["width"] = int(max(r[2] for r in rects) + dx + MARGIN)
    m["height"] = int(max(r[3] for r in rects) + dy + MARGIN)


def layout_warnings(m):
    warn = []
    comps = list(m["comps"].values())
    for i, a in enumerate(comps):
        for b in comps[i + 1:]:
            if overlap(node_box(a), node_box(b)):
                warn.append(f"components '{a['id']}' and '{b['id']}' overlap: move one of them")
    gs = list(m["groups"].values())

    def ancestors(g):
        while g["parent"]:
            g = m["groups"][g["parent"]]
            yield g["id"]
    for i, a in enumerate(gs):
        for b in gs[i + 1:]:
            related = a["id"] in ancestors(b) or b["id"] in ancestors(a)
            if not related and overlap(a["rect"], b["rect"]):
                warn.append(f"groups '{a['id']}' and '{b['id']}' overlap: leave an empty column/row "
                            f"between them or use half steps like 'at: [3.5, 1]'")
    for c in comps:
        for g in gs:
            inside = c["group"] == g["id"] or (c["group"] and g["id"] in ancestors(m["groups"][c["group"]]))
            if not inside and overlap(node_box(c), g["rect"]):
                warn.append(f"component '{c['id']}' sits inside group '{g['id']}' but is not a member")
    return warn


def overlap(a, b, pad=0):
    return a[0] < b[2] - pad and b[0] < a[2] - pad and a[1] < b[3] - pad and b[1] < a[3] - pad


def crosses_border(r, g):
    inside = g[0] <= r[0] and r[2] <= g[2] and g[1] <= r[1] and r[3] <= g[3]
    return overlap(r, g) and not inside


# ── edge routing ──────────────────────────────────────────────────────────────
def ports(c):
    cx, t = c["cx"], c["top"]
    return {"L": (cx - TILE / 2 - GAP, t + TILE / 2), "R": (cx + TILE / 2 + GAP, t + TILE / 2),
            "T": (cx, t - GAP), "B": (cx, t + BOX_H + GAP)}


def candidates(a, b, grid_col):
    pa, pb = ports(a), ports(b)
    ax, ay, bx, by = a["cx"], a["top"], b["cx"], b["top"]
    out = {}
    if abs(ax - bx) < 1:                                   # same column
        out["v"] = [pa["B"], pb["T"]] if by > ay else [pa["T"], pb["B"]]
        side = ax + BOX_W / 2 + 24
        out["detour-right"] = [pa["R"], (side, pa["R"][1]), (side, pb["R"][1]), pb["R"]]
        side = ax - BOX_W / 2 - 24
        out["detour-left"] = [pa["L"], (side, pa["L"][1]), (side, pb["L"][1]), pb["L"]]
        return out
    right = bx > ax
    s, e = (pa["R"], pb["L"]) if right else (pa["L"], pb["R"])
    if abs(ay - by) < 1:                                   # same row
        out["h"] = [s, e]
        for off, tag in ((0, ""), (16, "+"), (-16, "-")):  # shifted ports avoid sharing a line
            y = ay - PAD_TOP - 18
            out["detour-above" + tag] = [(ax + off, pa["T"][1]), (ax + off, y), (bx + off, y), (bx + off, pb["T"][1])]
            y = ay + BOX_H + PAD_BOTTOM + 22
            out["detour-below" + tag] = [(ax + off, pa["B"][1]), (ax + off, y), (bx + off, y), (bx + off, pb["B"][1])]
        return out
    down = by > ay
    sv, ev = (pa["B"], pb["T"]) if down else (pa["T"], pb["B"])
    if (ev[1] - s[1]) * (1 if down else -1) > 12:          # side, then into top/bottom
        out["hv"] = [s, (bx, s[1]), ev]
    if (e[1] - sv[1]) * (1 if down else -1) > 12:          # top/bottom, then into side
        out["vh"] = [sv, (ax, e[1]), e]
    for k, frac in enumerate((0.5, 0.3, 0.7)):             # side, corridor, side
        mx = ax + (bx - ax) * frac
        if abs(mx - s[0]) > 10 and abs(e[0] - mx) > 10 and (mx - s[0]) * (e[0] - mx) > 0:
            out[f"hvh{k}"] = [s, (mx, s[1]), (mx, e[1]), e]
    upper, lower = (ay, by) if down else (by, ay)
    if lower - (upper + BOX_H) > 24:                       # top/bottom, band between rows, top/bottom
        my = (upper + BOX_H + lower) / 2
        out["vhv"] = [sv, (ax, my), (bx, my), ev]
    return out


def segments(pts):
    return list(zip(pts, pts[1:]))


def seg_hits_rect(p, q, r, pad=2):
    x0, x1 = sorted((p[0], q[0]))
    y0, y1 = sorted((p[1], q[1]))
    return x0 < r[2] - pad and x1 > r[0] + pad and y0 < r[3] - pad and y1 > r[1] + pad


def collinear_overlap(s1, s2):
    (a, b), (c, d) = s1, s2
    if abs(a[1] - b[1]) < 1 and abs(c[1] - d[1]) < 1 and abs(a[1] - c[1]) < 4:
        lo, hi = max(min(a[0], b[0]), min(c[0], d[0])), min(max(a[0], b[0]), max(c[0], d[0]))
        return hi - lo > 6
    if abs(a[0] - b[0]) < 1 and abs(c[0] - d[0]) < 1 and abs(a[0] - c[0]) < 4:
        lo, hi = max(min(a[1], b[1]), min(c[1], d[1])), min(max(a[1], b[1]), max(c[1], d[1]))
        return hi - lo > 6
    return False


def obstacles(c):
    """A node blocks edges with its tile and with the text under it (not the empty space beside the tile)."""
    cx, t = c["cx"], c["top"]
    return [(cx - TILE / 2, t, cx + TILE / 2, t + TILE), (cx - BOX_W / 2, t + TILE + 2, cx + BOX_W / 2, t + BOX_H)]


def route_cost(pts, m, routed):
    hits, cost = [], 0.0
    for p, q in segments(pts):
        for c in m["comps"].values():
            if any(seg_hits_rect(p, q, r) for r in obstacles(c)):
                hits.append(f"component '{c['id']}'")
                cost += 1000
        for g in m["groups"].values():
            if seg_hits_rect(p, q, g["label_rect"]):
                hits.append(f"label of group '{g['id']}'")
                cost += 300
        for other in routed:
            if any(collinear_overlap((p, q), s) for s in segments(other)):
                cost += 80
    length = sum(abs(p[0] - q[0]) + abs(p[1] - q[1]) for p, q in segments(pts))
    return cost + 25 * (len(pts) - 2) + length / 100, hits


def route(m):
    warn, routed = [], []

    def priority(e):  # short, aligned edges first: they have the fewest alternatives
        a, b = m["comps"][e["src"]], m["comps"][e["dst"]]
        aligned = abs(a["cx"] - b["cx"]) < 1 or abs(a["top"] - b["top"]) < 1
        return (not aligned, abs(a["cx"] - b["cx"]) + abs(a["top"] - b["top"]))

    for e in sorted(m["conns"], key=priority):
        a, b = m["comps"][e["src"]], m["comps"][e["dst"]]
        cands = candidates(a, b, m["grid"]["col"])
        if e["route"]:
            if e["route"] not in cands:
                warn.append(f"connection #{e['n']} {e['src']} {e['op']} {e['dst']}: route "
                            f"'{e['route']}' not possible here (try {', '.join(cands)})")
            else:
                cands = {e["route"]: cands[e["route"]]}
        best = min(((route_cost(p, m, routed), name, p) for name, p in cands.items()),
                   key=lambda t: t[0][0])
        (cost, hits), name, pts = best
        e["points"] = pts
        routed.append(pts)
        if hits:
            warn.append(f"connection #{e['n']} {e['src']} {e['op']} {e['dst']} crosses "
                        f"{', '.join(sorted(set(hits)))}: rearrange components or set 'route:'")
    placed = []
    for e in m["conns"]:
        place_label(e, m, warn, placed)
    return warn


def place_label(e, m, warn, placed):
    if not e["label"]:
        return
    w = 6.3 * len(e["label"]) + 8
    others = [s for o in m["conns"] if o is not e for s in segments(o["points"])]
    segs = sorted(segments(e["points"]), key=lambda s: -(abs(s[0][0] - s[1][0]) + abs(s[0][1] - s[1][1])))
    spots = []
    for p, q in segs:
        if abs(p[1] - q[1]) < 1:                             # horizontal: centered above or below
            x = (p[0] + q[0]) / 2
            fits = abs(p[0] - q[0]) > w + 18
            spots += [(fits, x, p[1] - 7, "middle"), (fits, x, p[1] + 15, "middle")]
        else:                                                # vertical: right or left of the line
            fits = abs(p[1] - q[1]) > 30
            for frac in (0.5, 0.28, 0.72):                   # middle first, then higher / lower
                y = p[1] + (q[1] - p[1]) * frac + 4
                spots += [(fits, p[0] + 8, y, "start"), (fits, p[0] - 8, y, "end")]
    for fits, x, y, anchor in spots:
        x0 = {"middle": x - w / 2, "start": x, "end": x - w}[anchor]
        rect = (x0, y - 11, x0 + w, y + 3)
        clear = fits and \
            not any(overlap(rect, r) for c in m["comps"].values() for r in obstacles(c)) and \
            not any(crosses_border(rect, g["rect"]) or overlap(rect, g["label_rect"]) for g in m["groups"].values()) and \
            not any(seg_hits_rect(p, q, rect, pad=0) for p, q in others) and \
            not any(overlap(rect, r) for r in placed)
        if clear:
            e["label_pos"] = (x, y, anchor)
            placed.append(rect)
            return
    p, q = segs[0]
    e["label_pos"] = ((p[0] + q[0]) / 2, (p[1] + q[1]) / 2 - 7, "middle")
    warn.append(f"connection #{e['n']} {e['src']} {e['op']} {e['dst']}: no clear spot for label "
                f"'{e['label']}': shorten it or give the components more room")


# ── icons ─────────────────────────────────────────────────────────────────────
UA = {"User-Agent": "blueprint-md (+https://github.com/Sav019/blueprint-md)"}
INK = "#64708a"  # line-icon tint, readable on white tiles and dark group labels


def http_get(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=15) as r:
        return r.read()


def looks_like_image(data):
    head = data[:600].lstrip()
    return b"<svg" in head or head.startswith(b"<?xml") or data[:8] == b"\x89PNG\r\n\x1a\n"


def from_svgl(name):
    items = json.loads(http_get("https://api.svgl.app?search=" + urllib.parse.quote(name)))
    norm = lambda s: re.sub(r"[^a-z0-9]", "", s.lower())
    for item in items if isinstance(items, list) else []:
        if norm(item.get("title", "")) == norm(name):
            route = item.get("route")
            route = route.get("light") if isinstance(route, dict) else route
            return http_get(route)
    raise LookupError


def from_urls(*urls):
    for url in urls:
        try:
            data = http_get(url)
            if looks_like_image(data):
                return data
        except Exception:
            pass
    raise LookupError


def fetch_icon(spec):
    """Return (bytes, extension) for an icon spec, or raise LookupError."""
    prefix, _, name = spec.partition(":") if re.match(r"^[a-z]+:", spec) and not spec.startswith("http") else ("", "", spec)
    jsd = "https://cdn.jsdelivr.net"
    devicon = lambda n: from_urls(f"{jsd}/gh/devicons/devicon/icons/{n}/{n}-original.svg",
                                  f"{jsd}/gh/devicons/devicon/icons/{n}/{n}-plain.svg")
    logos = lambda n: from_urls(f"{jsd}/gh/gilbarbara/logos/logos/{n}-icon.svg",
                                f"{jsd}/gh/gilbarbara/logos/logos/{n}.svg")
    if spec.startswith(("http://", "https://")):
        data = from_urls(spec)
    elif prefix == "lucide":
        data = from_urls(f"{jsd}/npm/lucide-static@latest/icons/{name}.svg")
        data = data.replace(b"currentColor", INK.encode())
    elif prefix == "svgl":
        data = from_svgl(name)
    elif prefix == "devicon":
        data = devicon(name)
    elif prefix == "logos":
        data = logos(name)
    elif prefix in PACK_SOURCES:
        data = pack_icon(prefix, name)
    else:
        for source in (from_svgl, devicon, logos):
            try:
                data = source(name)
                break
            except Exception:
                continue
        else:
            raise LookupError
    return data, "png" if data[:4] == b"\x89PNG" else "svg"


def resolve_icons(m, base_dir, offline, log):
    cache = base_dir / ".blueprint" / "icons"
    specs = {c["icon"] for c in m["comps"].values() if c["icon"]}
    specs |= {g["icon"] for g in m["groups"].values() if g["icon"]}
    uris = {}
    for spec in sorted(specs):
        local = (base_dir / spec)
        if not spec.startswith("http") and local.suffix.lower() in (".svg", ".png") and local.exists():
            data = local.read_bytes()
            ext = local.suffix.lstrip(".").lower()
        else:
            key = re.sub(r"[^a-zA-Z0-9_.-]", "_", spec)[:80]
            hit = next((p for p in (cache / f"{key}.svg", cache / f"{key}.png") if p.exists()), None)
            if hit:
                data, ext = hit.read_bytes(), hit.suffix.lstrip(".")
            elif offline:
                log(f"warning: icon '{spec}' not cached (offline): showing a monogram")
                continue
            else:
                try:
                    data, ext = fetch_icon(spec)
                except Exception as err:
                    detail = f" ({err})" if isinstance(err, LookupError) and str(err) else ""
                    log(f"warning: icon '{spec}' not found{detail}: showing a monogram. Try another name, "
                        f"'lucide:<icon>', a URL or a local .svg/.png path")
                    continue
                cache.mkdir(parents=True, exist_ok=True)
                (cache / f"{key}.{ext}").write_bytes(data)
        mime = "image/png" if ext == "png" else "image/svg+xml"
        uris[spec] = f"data:{mime};base64,{base64.b64encode(data).decode()}"
    return uris


# ── official cloud icon packs ─────────────────────────────────────────────────
# Each vendor publishes an official icon package for architecture diagrams. The package is
# downloaded once into a shared cache and indexed by name; icons are never stored in this repo.
import io
import os
import zipfile

PACK_SOURCES = {
    "aws": {"label": "AWS Architecture Icons", "page": "https://aws.amazon.com/architecture/icons/",
            "find": r"https://d1\.awsstatic\.com/[^\"'\s]+Icon-package[^\"'\s]*\.zip"},
    "azure": {"label": "Azure Public Service Icons", "page": "https://learn.microsoft.com/en-us/azure/architecture/icons/",
              "find": r"https://arch-center\.azureedge\.net/icons/Azure_Public_Service_Icons_V\d+\.zip"},
    "gcp": {"label": "Google Cloud icons", "page": "https://cloud.google.com/icons",
            "zips": ["https://services.google.com/fh/files/misc/core-products-icons.zip",
                     "https://services.google.com/fh/files/misc/category-icons.zip"]},
}
VENDOR_WORDS = {"aws": ("aws", "amazon"), "azure": ("azure", "microsoft"), "gcp": ("google", "cloud", "gcp")}


def pack_dir(vendor):
    base = pathlib.Path(os.environ.get("XDG_CACHE_HOME") or pathlib.Path.home() / ".cache")
    return base / "blueprint-md" / "packs" / vendor


def norm(s):
    return re.sub(r"[^a-z0-9]", "", s.lower())


def index_pack(vendor, members):
    """Map normalized icon names to zip member paths for one vendor's package."""
    index = {}

    def add(name, member, prefer=False):
        for key in {norm(name), norm(re.sub(r"(?i)^(%s)[-_ ]+" % "|".join(VENDOR_WORDS[vendor]), "", name))}:
            if key and (prefer or key not in index):
                index[key] = member
    for zip_name, member in members:
        path = f"{zip_name}::{member}"
        if not member.lower().endswith(".svg") or "__MACOSX" in member:
            continue
        file = member.rsplit("/", 1)[-1][:-4]
        if vendor == "aws":
            if m := re.match(r"Arch_(.+)_64$", file):                       # service icons
                add(m[1], path, prefer=True)
            elif m := re.match(r"(.+?)_32$", file):                         # group icons (AWS Cloud, Region, VPC…)
                add(m[1], path)
            elif m := re.match(r"Res_(.+?)_48(_Light)?$", file):            # general resources (user, client…)
                add(m[1], path, prefer=bool(m[2]))
        elif vendor == "azure":
            if m := re.match(r"\d+-icon-service-(.+)$", file):
                add(m[1].replace("-", " "), path)
        elif vendor == "gcp":
            folder = member.split("/")[-3] if member.count("/") >= 2 else file
            add(folder, path, prefer="Unique" in member)
    return index


def load_pack(vendor, update=False, log=print):
    folder = pack_dir(vendor)
    index_file = folder / "index.json"
    if index_file.exists() and not update:
        return json.loads(index_file.read_text())
    src = PACK_SOURCES[vendor]
    urls = src.get("zips")
    if not urls:
        page = http_get(src["page"]).decode("utf-8", "replace")
        found = sorted(set(re.findall(src["find"], page)))
        if not found:
            raise LookupError(f"could not find the {src['label']} download on {src['page']}")
        urls = [max(found, key=lambda u: [int(n) for n in re.findall(r"\d+", u)])]
    log(f"downloading {src['label']} (one time, cached in {folder})…")
    folder.mkdir(parents=True, exist_ok=True)
    members, meta = [], {"source": src["page"], "zips": []}
    for i, url in enumerate(urls):
        data = http_get(url)
        (folder / f"pack{i}.zip").write_bytes(data)
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            members += [(f"pack{i}.zip", n) for n in z.namelist()]
        meta["zips"].append(url)
    index = {"meta": meta, "icons": index_pack(vendor, members)}
    index_file.write_text(json.dumps(index, indent=1))
    log(f"indexed {len(index['icons'])} {vendor} icon names")
    return index


def pack_icon(vendor, name):
    icons = load_pack(vendor)["icons"]
    key = norm(name)
    path = icons.get(key) or icons.get(norm(re.sub(r"(?i)^(%s)[-_ ]+" % "|".join(VENDOR_WORDS[vendor]), "", name)))
    if not path:
        raise LookupError(f"no {vendor} icon named '{name}'{suggest(key, list(icons))}")
    zip_name, member = path.split("::", 1)
    with zipfile.ZipFile(pack_dir(vendor) / zip_name) as z:
        return z.read(member)


def pack_search(vendor, words):
    icons = load_pack(vendor)["icons"]
    names = sorted({p.split("::", 1)[1].rsplit("/", 1)[-1] for p in icons.values()})
    wanted = [norm(w) for w in words]
    return [n for n in names if all(w in norm(n) for w in wanted)]


# ── HTML ──────────────────────────────────────────────────────────────────────
def css():
    groups = []
    for name, (h, c) in COLORS.items():
        groups.append(
            f".g-{name}{{--line:oklch(66% {c} {h});--tint:oklch(97% {c / 8:.3f} {h} / .55);--ink:oklch(48% {c} {h})}}"
            f"[data-theme=dark] .g-{name}{{--line:oklch(62% {c * .85:.3f} {h});--tint:oklch(28% {c / 4:.3f} {h} / .45);--ink:oklch(80% {c * .8:.3f} {h})}}")
    return """
:root{--paper:#f6f7f9;--dots:#d9dde4;--ink:#1c2230;--muted:#687083;--edge:#5d6577;--accent:#2f6fea;
--tile:#fff;--tile-line:#d6dae2;--veil:rgba(246,247,249,.82);
--sans:"Inter",-apple-system,BlinkMacSystemFont,"Segoe UI",system-ui,sans-serif;
--mono:ui-monospace,"SF Mono","JetBrains Mono",Menlo,Consolas,monospace}
[data-theme=dark]{--paper:#141821;--dots:#2a303c;--ink:#e8ebf1;--muted:#9aa2b3;--edge:#a3abba;--accent:#6c9cff;
--tile-line:#3a4150;--veil:rgba(20,24,33,.82)}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--paper);color:var(--ink);font-family:var(--sans);padding:40px 20px 56px}
.page{width:fit-content;max-width:100%;margin:0 auto}
header{display:flex;justify-content:space-between;align-items:flex-end;gap:24px;margin-bottom:20px}
h1{font-size:26px;font-weight:700;letter-spacing:-.01em}
.summary{max-width:560px;margin-top:6px;font-size:13px;line-height:1.6;color:var(--muted)}
.theme{border:1px solid var(--tile-line);background:none;color:var(--muted);border-radius:8px;padding:6px 10px;font:12px var(--mono);cursor:pointer}
.frame{overflow-x:auto;border:1px solid var(--tile-line);border-radius:12px}
.canvas{position:relative;background-color:var(--paper);background-image:radial-gradient(var(--dots) 1px,transparent 1.3px);background-size:20px 20px}
.group{position:absolute;border:1.5px solid var(--line);background:var(--tint);border-radius:14px}
.group.dashed{border-style:dashed;background:none}
.glabel{position:absolute;top:10px;left:12px;display:flex;gap:7px;align-items:center;font-size:12.5px;font-weight:650;color:var(--ink);white-space:nowrap}
.group>.glabel{color:var(--ink)}
.glabel img{width:16px;height:16px;object-fit:contain}
.node{position:absolute;width:136px;text-align:center}
.tile{width:60px;height:60px;margin:0 auto;display:grid;place-items:center;background:var(--tile);border:1px solid var(--tile-line);border-radius:14px;box-shadow:0 1px 2px rgba(20,30,50,.06)}
.tile img{width:34px;height:34px;object-fit:contain}
.tile.wide img{width:46px}
.tile.dark{background:#1f2430;border-color:#1f2430}
.tile.bare{background:none;border:none;box-shadow:none}.tile.bare img{width:52px;height:52px}
.mono{font:600 18px var(--mono);color:var(--muted)}
.node:hover .tile{border-color:var(--accent)}
.name{margin-top:8px;font-size:13px;font-weight:650;line-height:1.25}
.kind{margin-top:3px;font:10px var(--mono);letter-spacing:.03em;color:var(--muted)}
.name span,.kind span{background:var(--veil);border-radius:4px;padding:0 4px;-webkit-box-decoration-break:clone;box-decoration-break:clone}
svg.edges{position:absolute;inset:0;pointer-events:none}
.edge{fill:none;stroke:var(--edge);stroke-width:1.4}
.edge.primary{stroke:var(--accent);stroke-width:1.7}
.edge.dashed{stroke-dasharray:5 5}
.elabel{font:10.5px var(--mono);letter-spacing:.02em;fill:var(--muted);paint-order:stroke;stroke:var(--paper);stroke-width:4px;stroke-linejoin:round}
.elabel.primary{fill:var(--accent)}
.legend{display:flex;flex-wrap:wrap;gap:22px;margin-top:14px;font:11px var(--mono);color:var(--muted)}
.legend i{display:inline-block;width:28px;margin-right:7px;vertical-align:middle;border-top:1.6px solid var(--edge)}
.legend i.primary{border-color:var(--accent)}.legend i.dashed{border-top-style:dashed}
footer{margin-top:28px;font:11px var(--mono);color:var(--muted)}
""" + "\n".join(groups)


def esc(s):
    return html.escape(str(s), quote=True)


def render_html(m, icons):
    out = []
    for g in sorted(m["groups"].values(), key=lambda g: depth(m, g)):
        x0, y0, x1, y1 = g["rect"]
        img = f'<img src="{icons[g["icon"]]}" alt="">' if g["icon"] in icons else ""
        out.append(f'<div class="group g-{g["color"]}{" dashed" if g["dashed"] else ""}" '
                   f'style="left:{x0:.0f}px;top:{y0:.0f}px;width:{x1 - x0:.0f}px;height:{y1 - y0:.0f}px" '
                   f'title="{esc(g["about"])}"><div class="glabel">{img}{esc(g["label"])}</div></div>')
    w, h = m["width"], m["height"]
    svg = [f'<svg class="edges" width="{w}" height="{h}" viewBox="0 0 {w} {h}" aria-hidden="true"><defs>'
           '<marker id="arrow" viewBox="0 0 10 10" refX="8.5" refY="5" markerWidth="7" markerHeight="7" '
           'orient="auto-start-reverse"><path d="M0 0L10 5L0 10z" fill="context-stroke"/></marker></defs>']
    for e in m["conns"]:
        d = "M" + " L".join(f"{x:.0f} {y:.0f}" for x, y in e["points"])
        cls = "edge" + (" primary" if e["primary"] else "") + (" dashed" if e["dashed"] else "")
        marks = (' marker-end="url(#arrow)"' if e["end_arrow"] else "") + \
                (' marker-start="url(#arrow)"' if e["start_arrow"] else "")
        svg.append(f'<path class="{cls}" d="{d}"{marks}><title>{esc(edge_title(m, e))}</title></path>')
        if e.get("label_pos"):
            x, y, anchor = e["label_pos"]
            svg.append(f'<text class="elabel{" primary" if e["primary"] else ""}" x="{x:.0f}" y="{y:.0f}" '
                       f'text-anchor="{anchor}">{esc(e["label"])}</text>')
    svg.append("</svg>")
    out.append("".join(svg))
    for c in m["comps"].values():
        if c["icon"] in icons:
            inner = f'<img src="{icons[c["icon"]]}" alt="">'
        else:
            inner = f'<span class="mono">{esc(monogram(c["name"]))}</span>'
        tile = "tile" + "".join(f" {t}" for t in str(c["tile"]).split() if t in ("dark", "wide", "bare"))
        kind = f'<div class="kind"><span>{esc(c["kind"])}</span></div>' if c["kind"] else ""
        out.append(f'<div class="node" style="left:{c["cx"] - BOX_W / 2:.0f}px;top:{c["top"]:.0f}px" '
                   f'data-id="{esc(c["id"])}" title="{esc(c["about"] or c["block"].get("what", ""))}"><div class="{tile}">{inner}</div>'
                   f'<div class="name"><span>{esc(c["name"])}</span></div>{kind}</div>')

    used = {("primary" if e["primary"] else "dashed" if e["dashed"] else "default") for e in m["conns"]}
    names = {"primary": "main flow", "default": "connection", "dashed": "async / batch", **m["legend"]}
    legend = "".join(f'<span><i class="{k}"></i>{esc(names[k])}</span>'
                     for k in ("primary", "default", "dashed") if k in used)
    summary = f'<p class="summary">{esc(m["summary"])}</p>' if m["summary"] else ""
    return f"""<!doctype html>
<html lang="en" data-theme="light"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(m["title"])}</title>
<script>try{{if(matchMedia('(prefers-color-scheme: dark)').matches)document.documentElement.dataset.theme='dark'}}catch(e){{}}</script>
<style>{css()}</style></head><body><div class="page">
<header><div><h1>{esc(m["title"])}</h1>{summary}</div>
<button class="theme" onclick="var d=document.documentElement;d.dataset.theme=d.dataset.theme==='dark'?'light':'dark'">light / dark</button></header>
<div class="frame"><div class="canvas" style="width:{w}px;height:{h}px">
{chr(10).join(out)}
</div></div>
<div class="legend">{legend}</div>
<footer>Generated from {esc(m["source"])} by blueprint-md · hover a component for details</footer>
</div></body></html>
"""


def depth(m, g):
    d = 0
    while g["parent"]:
        g, d = m["groups"][g["parent"]], d + 1
    return d


def monogram(name):
    words = re.findall(r"[A-Za-z0-9]+", name)
    return ("".join(w[0] for w in words[:2]) or "?").upper()


def edge_title(m, e):
    a, b = m["comps"][e["src"]]["name"], m["comps"][e["dst"]]["name"]
    return f"{a} {e['op']} {b}" + (f": {e['label']}" if e["label"] else "") + (f" · {e['about']}" if e["about"] else "")


# ── Markdown ──────────────────────────────────────────────────────────────────
def group_path(m, gid):
    parts = []
    while gid:
        g = m["groups"][gid]
        parts.insert(0, g["label"])
        gid = g["parent"]
    return " › ".join(parts)


def render_markdown(m, image):
    comps, conns = m["comps"], m["conns"]
    nm = lambda cid: f"**{comps[cid]['name']}** (`{cid}`)"
    L = [f"# {m['title']}", ""]
    if m["summary"]:
        L += [str(m["summary"]).strip(), ""]
    L += [f"> Generated by blueprint-md from `{m['source']}`. Edit the YAML and rebuild instead of editing this file.", ""]
    if image:
        L += [f"![{m['title']} architecture diagram]({image})", ""]
    count = lambda n, word: f"{n} {word}{'' if n == 1 else 's'}"
    glance = [count(len(comps), "component"), count(len(m["groups"]), "group"), count(len(conns), "connection")]
    glance += [count(len(m["flows"]), "flow")] if m["flows"] else []
    glance += [count(len(m["decisions"]), "decision")] if m["decisions"] else []
    L += ["## At a glance", "", "- " + ", ".join(glance), ""]

    L += ["## Structure", ""]
    order = []   # components in the same order as the structure tree

    def tree(gid, indent):
        for g in [g for g in m["groups"].values() if g["parent"] == gid]:
            L.append(f"{'  ' * indent}- **{g['label']}**" + (f": {g['about']}" if g["about"] else ""))
            for c in sorted((c for c in comps.values() if c["group"] == g["id"]), key=lambda c: (c["row"], c["col"])):
                L.append(f"{'  ' * (indent + 1)}- {nm(c['id'])}" + (f": {c['kind']}" if c["kind"] else ""))
                order.append(c)
            tree(g["id"], indent + 1)
    tree(None, 0)
    for c in [c for c in comps.values() if not c["group"]]:
        L.append(f"- {nm(c['id'])}" + (f": {c['kind']}" if c["kind"] else "") + " (outside all groups)")
        order.append(c)
    L.append("")

    def describe(e, other):
        bits = [e["label"]] if e["label"] else []
        bits += [x for x in (e["protocol"], e["data"]) if x]
        style = "async / batch" if e["dashed"] else ""
        text = f"{nm(other)}" + (f": {', '.join(map(str, bits))}" if bits else "")
        text += f" ({style})" if style else ""
        return text + (f". {e['about']}" if e["about"] else "")

    L += ["## Components", ""]
    for c in order:
        L += [f"### {c['name']} (`{c['id']}`)", ""]
        if c["about"]:
            L += [str(c["about"]).strip(), ""]
        b = c["block"]
        block = ""
        if b:
            label = f"[{b['name']}]({b['docs']})" if b.get("docs") else b["name"]
            block = f"{label} (`{c['type']}`)" + (f": {b['what']}" if b.get("what") else "")
        facts = [("Building block", block), ("Role", c["kind"]), ("Technology", c["tech"]),
                 ("Part of", group_path(m, c["group"]) if c["group"] else ""), ("Code", f"`{c['code']}`" if c["code"] else ""),
                 ("Not meant for", b.get("avoid_when", ""))]
        L += [f"- **{k}:** {v}" for k, v in facts if v]
        mine = [e for e in conns if c["id"] in (e["src"], e["dst"])]
        other = lambda e: e["dst"] if e["src"] == c["id"] else e["src"]
        one_way = [e for e in mine if e["end_arrow"] and not e["start_arrow"]]
        sections = (("Sends to", [e for e in one_way if e["src"] == c["id"]]),
                    ("Receives from", [e for e in one_way if e["dst"] == c["id"]]),
                    ("Two-way with", [e for e in mine if e["start_arrow"]]),
                    ("Linked with", [e for e in mine if not e["end_arrow"]]))
        for title, items in sections:
            if items:
                L.append(f"- **{title}:**")
                L += [f"  - {describe(e, other(e))}" for e in items]
        L.append("")

    if conns:
        L += ["## Connections", "", "| # | From | To | What | Style | Details |", "|---|---|---|---|---|---|"]
        for e in conns:
            style = ("main flow, " if e["primary"] else "") + \
                    {"->": "one-way", "<->": "two-way", "..>": "async / batch", "<..>": "async, two-way", "--": "link"}[e["op"]]
            details = "; ".join(str(x) for x in (e["protocol"], e["data"], e["about"]) if x)
            L.append(f"| {e['n']} | {comps[e['src']]['name']} | {comps[e['dst']]['name']} | "
                     f"{cell(e['label'])} | {style} | {cell(details)} |")
        L.append("")

    if m["flows"]:
        L += ["## Flows", ""]
        for f in m["flows"]:
            L += [f"### {f['name']}", ""]
            for i, (a, b) in enumerate(zip(f["steps"], f["steps"][1:]), 1):
                e = next((e for e in conns if (e["src"], e["dst"]) == (a, b)), None) or \
                    next((e for e in conns if (e["src"], e["dst"]) == (b, a)), None)
                what = f": {e['label']}" if e and e["label"] else ("" if e else " (no direct connection in the diagram)")
                L.append(f"{i}. {comps[a]['name']} → {comps[b]['name']}{what}")
            L.append("")

    if m["decisions"]:
        L += ["## Decisions", ""]
        for i, d in enumerate(m["decisions"], 1):
            d = d if isinstance(d, dict) else {"title": str(d)}
            status = f" ({d['status']})" if d.get("status") else ""
            L += [f"### D{i}. {d.get('title', 'Untitled')}{status}", ""]
            for key, label in (("context", "Context"), ("decision", "Decision"), ("why", "Why"),
                               ("alternatives", "Alternatives considered"), ("consequences", "Consequences")):
                val = d.get(key)
                if isinstance(val, list):
                    L.append(f"- **{label}:**")
                    L += [f"  - {v}" for v in val]
                elif val:
                    L.append(f"- **{label}:** {str(val).strip()}")
            L.append("")

    L += ["## Notes for coding agents", ""]
    if m["notes"]:
        L += [str(m["notes"]).strip(), ""]
    L += ["- Component ids (in backticks) are stable names: reuse them for modules, services, folders and config keys.",
          "- A component should only talk to the components listed in its **Sends to**, **Receives from**, **Two-way with** and **Linked with** entries. "
          "If the code needs a new connection, add it to the YAML first.",
          "- Decisions above are binding unless the user changes them.", ""]
    return "\n".join(L)


def cell(s):
    return str(s).replace("|", "\\|").replace("\n", " ")


# ── PNG ───────────────────────────────────────────────────────────────────────
def render_png(html_path, png_path, width, height):
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        raise BlueprintError("--png needs Playwright: pip install playwright && python3 -m playwright install chromium")
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(device_scale_factor=2, viewport={"width": width + 120, "height": height + 400})
        page.goto(html_path.resolve().as_uri())
        written = []
        for theme, suffix in (("light", ""), ("dark", "-dark")):
            page.evaluate(f"document.documentElement.dataset.theme='{theme}'")
            target = png_path.with_name(png_path.stem + suffix + ".png")
            page.locator(".canvas").screenshot(path=str(target))
            written.append(target)
        browser.close()
    return written


# ── catalog command ───────────────────────────────────────────────────────────
def catalog_matches(entry, query):
    if not query:
        return True
    hay = " ".join(str(entry.get(k, "")) for k in ("type", "name", "kind", "category", "what", "use_when")).lower()
    return all(word in hay for word in query.lower().split())


def catalog_list(entries, query):
    current = None
    shown = 0
    for e in sorted(entries.values(), key=lambda e: (e["catalog"], e.get("category", ""), e["type"])):
        if not catalog_matches(e, query):
            continue
        heading = f"{e['catalog']} · {e.get('category', 'Other')}"
        if heading != current:
            print(f"\n{heading}")
            current = heading
        print(f"  {e['type']:34} {e.get('name', '')}: {e.get('what', '')}")
        if e.get("use_when"):
            print(f"  {'':34} use when: {e['use_when']}")
        shown += 1
    print(f"\n{shown} building block(s). Use them as 'type: <type>' on a component.")


def catalog_markdown(entries):
    L = ["# Building block catalog", "",
         "Generated by `blueprint.py catalog --write`. Edit the YAML files in this folder, not this page.", "",
         "Use a building block on a component with `type:`; its name, role, icon and description are filled in automatically.", ""]
    by_catalog = {}
    for e in entries.values():
        by_catalog.setdefault(e["catalog"], {}).setdefault(e.get("category", "Other"), []).append(e)
    for title, cats in sorted(by_catalog.items()):
        L += [f"## {title}", ""]
        for cat, items in cats.items():
            L += [f"### {cat}", "", "| Type | Name | What it is | Use when | Avoid when | Docs |", "|---|---|---|---|---|---|"]
            for e in items:
                docs = f"[docs]({e['docs']})" + (f" ({e['checked']})" if e.get("checked") else "") if e.get("docs") else ""
                L.append(f"| `{e['type']}` | {cell(e.get('name', ''))} | {cell(e.get('what', ''))} | "
                         f"{cell(e.get('use_when', ''))} | {cell(e.get('avoid_when', ''))} | {docs} |")
            L.append("")
    return "\n".join(L)


SOFT_404 = ("couldn't find that page", "page not found", "page you requested", "this page does not exist")


def check_links(urls, log):
    """Return {url: problem} for links that look broken. Uses a headless browser when Playwright is installed."""
    problems = {}
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        sync_playwright = None
        log("note: Playwright not installed, checking links without a browser (some sites block this)")
    if sync_playwright:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                                               "(KHTML, like Gecko) Chrome/130.0 Safari/537.36")
            for url in urls:
                try:
                    resp = page.goto(url, wait_until="domcontentloaded", timeout=30000)
                    page.wait_for_timeout(3500)       # let single-page docs sites render
                    text = page.locator("body").inner_text(timeout=5000)[:4000].lower()
                    status = resp.status if resp else 0
                    if status == 404 or status >= 500 or any(s in text for s in SOFT_404):
                        problems[url] = f"broken (HTTP {status})"
                    elif status == 403:                # bot protection: a plain request is a second opinion
                        try:
                            http_get(url)
                        except Exception:
                            problems[url] = "blocked automated access (HTTP 403): open it by hand once"
                    log(f"  {'ok ' if url not in problems else '!! '} {url}")
                except Exception as e:
                    problems[url] = f"could not load ({type(e).__name__})"
                    log(f"  !!  {url}")
            browser.close()
        return problems
    for url in urls:
        try:
            http_get(url)
        except urllib.error.HTTPError as e:
            problems[url] = f"HTTP {e.code}" + (": site blocks scripts, check by hand" if e.code == 403 else "")
        except Exception as e:
            problems[url] = f"could not load ({type(e).__name__})"
    return problems


def catalog_check(entries, links, log):
    import datetime
    today = datetime.date.today()
    errors, warnings = [], []
    for e in entries.values():
        where = f"{e['file']} '{e['type']}'"
        for field in ("name", "what"):
            if not e.get(field):
                errors.append(f"{where}: missing '{field}'")
        if len(str(e.get("kind", ""))) > 19:
            warnings.append(f"{where}: kind '{e['kind']}' is longer than 19 characters and wraps under the icon")
        if not e["type"].startswith("generic/"):
            if not e.get("docs"):
                warnings.append(f"{where}: no 'docs' link")
            checked = str(e.get("checked", ""))
            m = re.match(r"^(\d{4})-(\d{2})$", checked)
            if not m:
                warnings.append(f"{where}: 'checked' should be YYYY-MM, got '{checked}'")
            else:
                age = (today.year - int(m[1])) * 12 + today.month - int(m[2])
                if age > 6:
                    warnings.append(f"{where}: last checked {checked} ({age} months ago): review it")
        for other in e.get("connects_with") or []:
            if other not in entries:
                errors.append(f"{where}: connects_with '{other}' is not in the catalog{suggest(other, list(entries))}")
    if links:
        specs = sorted({e["icon"] for e in entries.values() if e.get("icon")})
        log(f"checking {len(specs)} icons…")
        for spec in specs:
            try:
                fetch_icon(spec)
            except Exception as err:
                users = ", ".join(e["type"] for e in entries.values() if e.get("icon") == spec)
                errors.append(f"icon '{spec}' ({users}) not found" + (f": {err}" if str(err) else ""))
        urls = sorted({e["docs"] for e in entries.values() if e.get("docs")})
        log(f"checking {len(urls)} links…")
        for url, problem in check_links(urls, log).items():
            users = ", ".join(e["type"] for e in entries.values() if e.get("docs") == url)
            (warnings if "403" in problem else errors).append(f"{url} ({users}): {problem}")
    return errors, warnings


# ── CLI ───────────────────────────────────────────────────────────────────────
def main(argv=None):
    ap = argparse.ArgumentParser(prog="blueprint.py", description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="command", required=True)
    b = sub.add_parser("build", help="write the diagram and ARCHITECTURE.md")
    b.add_argument("yaml", type=pathlib.Path)
    b.add_argument("--out", type=pathlib.Path, help="output folder (default: next to the YAML)")
    b.add_argument("--png", action="store_true", help="also write light and dark PNGs")
    b.add_argument("--offline", action="store_true", help="use cached icons only")
    c = sub.add_parser("check", help="validate and lay out without writing files")
    c.add_argument("yaml", type=pathlib.Path)
    ic = sub.add_parser("icons", help="search the official AWS / Azure / Google Cloud icon packs")
    ic.add_argument("vendor", choices=sorted(PACK_SOURCES))
    ic.add_argument("words", nargs="*", help="only show icon files containing these words")
    ic.add_argument("--update", action="store_true", help="download the newest package again")
    k = sub.add_parser("catalog", help="list, document or check the building block catalog")
    k.add_argument("query", nargs="*", help="only show entries matching these words")
    k.add_argument("--file", action="append", default=[], type=pathlib.Path, help="extra catalog file to include")
    k.add_argument("--write", type=pathlib.Path, metavar="PATH", help="write the catalog as a Markdown page")
    k.add_argument("--check", action="store_true", help="validate entries, dates and links")
    k.add_argument("--no-links", action="store_true", help="with --check: skip the icon and link checks (offline)")
    args = ap.parse_args(argv)

    try:
        if args.command == "icons":
            try:
                if args.update:
                    load_pack(args.vendor, update=True)
                hits = pack_search(args.vendor, args.words)
            except (LookupError, OSError) as e:
                raise BlueprintError(f"error: {e}")
            for name in hits[:200]:
                print(f"  {name}")
            print(f"{len(hits)} icon file(s). Use them as 'icon: {args.vendor}:<name>' (the name part is enough, "
                  f"e.g. {args.vendor}:{'lambda' if args.vendor == 'aws' else 'function apps' if args.vendor == 'azure' else 'bigquery'}).")
            return 0
        if args.command == "catalog":
            entries = load_catalog(args.file)
            if args.check:
                errors, warnings = catalog_check(entries, not args.no_links, print)
                for w in warnings:
                    print(f"warning: {w}")
                for e in errors:
                    print(f"error: {e}")
                print(f"{len(entries)} entries, {len(errors)} errors, {len(warnings)} warnings")
                return 1 if errors else 0
            if args.write:
                args.write.write_text(catalog_markdown(entries), encoding="utf-8")
                print(f"wrote {args.write} ({len(entries)} entries)")
                return 0
            catalog_list(entries, " ".join(args.query))
            return 0

        m = load(args.yaml)
        layout(m)
        warnings = m["warnings"] + layout_warnings(m) + route(m)
        for w in warnings:
            print(f"warning: {w}")
        if args.command == "check":
            print(f"ok: {len(m['comps'])} components, {len(m['conns'])} connections, {len(warnings)} warnings")
            return 0
        out = args.out or args.yaml.parent
        out.mkdir(parents=True, exist_ok=True)
        icons = resolve_icons(m, args.yaml.parent, args.offline, print)
        stem = args.yaml.stem
        html_path = out / f"{stem}.html"
        html_path.write_text(render_html(m, icons), encoding="utf-8")
        print(f"wrote {html_path}")
        image = None
        if args.png:
            for p in render_png(html_path, out / f"{stem}.png", m["width"], m["height"]):
                print(f"wrote {p}")
            image = f"{stem}.png"
        md_path = out / "ARCHITECTURE.md"
        md_path.write_text(render_markdown(m, image), encoding="utf-8")
        print(f"wrote {md_path}")
        print(f"done: {len(m['comps'])} components, {len(m['conns'])} connections, {len(warnings)} warnings")
        return 0
    except BlueprintError as e:
        print(e, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
