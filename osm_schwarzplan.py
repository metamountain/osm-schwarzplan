#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OSM Schwarzplan
===============
Reads an ``.osm`` file (OSM XML), filters all ``building=*`` objects,
separates garages/carports onto their own layer, and shows a classic
figure-ground plan ("Schwarzplan": black building footprints on a white
background) as a live preview.

Export formats:
  - DXF with real area fill (HATCH) on two layers: BUILDINGS and GARAGES
  - SVG (dependency-free vector output)
  - PNG (requires the optional "Pillow" package)

Dependencies:
  - ``ezdxf`` is required only for DXF export (not part of the standard
    library). It is checked at export time and, if missing, installed via
    pip automatically (unless disabled with ``--no-install``).
  - ``Pillow`` is optional and only needed for PNG export.
  - ``tkinter``, ``xml.etree``, ``math``, ``os``, ``sys``, ``argparse`` are
    part of the Python standard library.

Usage:
  GUI (default):
    - Drag an ``.osm`` file onto the accompanying ``run.bat`` file, OR
    - Start the app and pick an ``.osm`` file via the "Open file..." button.

  Command line (headless, no window):
    python osm_schwarzplan.py input.osm -o output.dxf
    python osm_schwarzplan.py input.osm -o output.svg
    python osm_schwarzplan.py input.osm -o plan.png --no-gui
"""

import sys
import os
import subprocess
import math
import argparse
import xml.etree.ElementTree as ET

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# building=* values that count as a "garage" and go onto the GARAGES layer.
# Extend/adjust here as needed.
GARAGE_VALUES = {"garage", "garages", "carport", "car_port"}

# building=* values that mean "this is NOT a building" and must be ignored.
NON_BUILDING_VALUES = {"no", "false", "0"}

LAYER_BUILDINGS = "BUILDINGS"
LAYER_GARAGES = "GARAGES"

COLOR_BUILDINGS_HEX = "#1a1a1a"   # near-black, for the preview
COLOR_GARAGES_HEX = "#b23b2e"     # dark red, for the preview (distinction only)

DXF_COLOR_BUILDINGS = 0    # 0 = "black" in most CAD templates (ByBlock-ish)
DXF_COLOR_GARAGES = 1      # AutoCAD color index 1 = red


# ---------------------------------------------------------------------------
# Dependency handling
# ---------------------------------------------------------------------------

def ensure_dependency(module_name, pip_name=None, auto_install=True):
    """Return True if ``module_name`` is importable, installing it via pip if
    missing and ``auto_install`` is set. Never raises; returns False on failure.
    """
    pip_name = pip_name or module_name
    try:
        __import__(module_name)
        return True
    except ImportError:
        if not auto_install:
            return False
        print(f"[Setup] Module '{module_name}' is missing, installing "
              f"'{pip_name}' ...")
        try:
            subprocess.check_call(
                [sys.executable, "-m", "pip", "install", "--quiet", pip_name]
            )
            __import__(module_name)
            print(f"[Setup] '{pip_name}' installed successfully.")
            return True
        except Exception as e:  # noqa: BLE001 - report and continue
            print(f"[Error] Could not install '{pip_name}': {e}")
            return False


# ---------------------------------------------------------------------------
# OSM parsing
# ---------------------------------------------------------------------------

def parse_osm(path):
    """Read an ``.osm`` XML file and return ``(nodes, ways, relations)`` dicts.

    Uses ``iterparse`` and clears processed elements so that large extracts do
    not keep the whole DOM in memory.
    """
    nodes = {}      # id -> (lat, lon)
    ways = {}       # id -> {"nds": [node_ids...], "tags": {...}}
    relations = {}  # id -> {"members": [(type, ref, role), ...], "tags": {...}}

    context = ET.iterparse(path, events=("end",))
    for _event, el in context:
        tag = el.tag
        if tag == "node":
            nid = el.get("id")
            lat = el.get("lat")
            lon = el.get("lon")
            if nid is not None and lat is not None and lon is not None:
                nodes[nid] = (float(lat), float(lon))
            el.clear()
        elif tag == "way":
            wid = el.get("id")
            nds = [nd.get("ref") for nd in el.findall("nd")]
            tags = {t.get("k"): t.get("v") for t in el.findall("tag")}
            ways[wid] = {"nds": nds, "tags": tags}
            el.clear()
        elif tag == "relation":
            rid = el.get("id")
            members = [
                (m.get("type"), m.get("ref"), m.get("role"))
                for m in el.findall("member")
            ]
            tags = {t.get("k"): t.get("v") for t in el.findall("tag")}
            relations[rid] = {"members": members, "tags": tags}
            el.clear()

    return nodes, ways, relations


def is_building(tags):
    """True if the tag set describes an actual building footprint."""
    value = tags.get("building")
    if not value:
        return False
    return value.strip().lower() not in NON_BUILDING_VALUES


def classify_layer(building_value):
    if building_value and building_value.strip().lower() in GARAGE_VALUES:
        return LAYER_GARAGES
    return LAYER_BUILDINGS


def assemble_rings(way_ids, ways, nodes):
    """Join a list of way IDs (segments) into closed rings.

    Multipolygon relations may describe a ring as several partial ways; this
    stitches matching endpoints together. Returns a list of rings, each a list
    of ``(lat, lon)`` tuples.
    """
    segments = []
    for wid in way_ids:
        w = ways.get(wid)
        if w and len(w["nds"]) >= 2:
            segments.append(list(w["nds"]))

    rings = []
    while segments:
        current = segments.pop(0)
        changed = True
        while changed and current[0] != current[-1]:
            changed = False
            for i, seg in enumerate(segments):
                if seg[0] == current[-1]:
                    current += seg[1:]
                    segments.pop(i)
                    changed = True
                    break
                elif seg[-1] == current[-1]:
                    current += list(reversed(seg))[1:]
                    segments.pop(i)
                    changed = True
                    break
                elif seg[-1] == current[0]:
                    current = seg[:-1] + current
                    segments.pop(i)
                    changed = True
                    break
                elif seg[0] == current[0]:
                    current = list(reversed(seg))[:-1] + current
                    segments.pop(i)
                    changed = True
                    break
        coords = [nodes[nid] for nid in current if nid in nodes]
        if len(coords) >= 3:
            rings.append(coords)

    return rings


def _ring_contains_point(ring, point):
    """Ray-casting point-in-polygon test. ``ring`` is a list of ``(lat, lon)``
    tuples and ``point`` is a ``(lat, lon)`` tuple; lat is treated as y and lon
    as x (planar approximation, fine at building scale)."""
    py, px = point           # (lat, lon)
    inside = False
    n = len(ring)
    j = n - 1
    for i in range(n):
        yi, xi = ring[i]     # (lat, lon)
        yj, xj = ring[j]
        if ((yi > py) != (yj > py)) and \
                (px < (xj - xi) * (py - yi) / (yj - yi) + xi):
            inside = not inside
        j = i
    return inside


def _assign_holes_to_outers(outer_rings, inner_rings):
    """Return a list of building dicts pairing each outer ring with the inner
    rings that fall inside it. Fixes the naive "all holes on every outer"
    behaviour for relations that contain several separate outer rings."""
    result = []
    for outer in outer_rings:
        holes = []
        for inner in inner_rings:
            if inner and _ring_contains_point(outer, inner[0]):
                holes.append(inner)
        result.append({"outer": outer, "holes": holes})
    return result


def extract_buildings(nodes, ways, relations):
    """Return a list of buildings:
    ``[{"outer": [(lat, lon), ...], "holes": [ring, ...], "layer": ...}]``
    """
    buildings = []
    used_way_ids = set()

    # 1. Multipolygon relations with building=*
    for _rid, rel in relations.items():
        tags = rel["tags"]
        if not is_building(tags):
            continue
        if tags.get("type") != "multipolygon":
            continue

        outer_way_ids = [ref for (typ, ref, role) in rel["members"]
                         if typ == "way" and role in ("outer", "")]
        inner_way_ids = [ref for (typ, ref, role) in rel["members"]
                         if typ == "way" and role == "inner"]

        outer_rings = assemble_rings(outer_way_ids, ways, nodes)
        inner_rings = assemble_rings(inner_way_ids, ways, nodes)

        used_way_ids.update(outer_way_ids)
        used_way_ids.update(inner_way_ids)

        layer = classify_layer(tags.get("building"))
        for pair in _assign_holes_to_outers(outer_rings, inner_rings):
            pair["layer"] = layer
            buildings.append(pair)

    # 2. Standalone ways with building=*
    for wid, w in ways.items():
        if wid in used_way_ids:
            continue
        tags = w["tags"]
        if not is_building(tags):
            continue
        coords = [nodes[nid] for nid in w["nds"] if nid in nodes]
        if len(coords) < 3:
            continue
        layer = classify_layer(tags.get("building"))
        buildings.append({"outer": coords, "holes": [], "layer": layer})

    return buildings


# ---------------------------------------------------------------------------
# Projection: degrees -> local meters (tangent plane at the map center)
# ---------------------------------------------------------------------------

def project_buildings(buildings):
    """Project every coordinate from ``(lat, lon)`` to local meters ``(x, y)``.
    Returns ``(projected_buildings, (lat0, lon0))``."""
    all_lats = []
    all_lons = []
    for b in buildings:
        for lat, lon in b["outer"]:
            all_lats.append(lat)
            all_lons.append(lon)

    if not all_lats:
        return buildings, (0, 0)

    lat0 = sum(all_lats) / len(all_lats)
    lon0 = sum(all_lons) / len(all_lons)

    cos_lat0 = math.cos(math.radians(lat0))

    def to_xy(lat, lon):
        x = (lon - lon0) * cos_lat0 * 111320.0
        y = (lat - lat0) * 110540.0
        return (x, y)

    projected = []
    for b in buildings:
        outer_xy = [to_xy(lat, lon) for lat, lon in b["outer"]]
        holes_xy = [[to_xy(lat, lon) for lat, lon in hole] for hole in b["holes"]]
        projected.append({"outer": outer_xy, "holes": holes_xy, "layer": b["layer"]})

    return projected, (lat0, lon0)


def compute_bounds(buildings_xy):
    """Return ``(minx, miny, maxx, maxy)`` over all outer rings, or None."""
    xs = [p[0] for b in buildings_xy for p in b["outer"]]
    ys = [p[1] for b in buildings_xy for p in b["outer"]]
    if not xs or not ys:
        return None
    return min(xs), min(ys), max(xs), max(ys)


# ---------------------------------------------------------------------------
# DXF export with area fill
# ---------------------------------------------------------------------------

def export_dxf(buildings_xy, output_path, auto_install=True):
    if not ensure_dependency("ezdxf", auto_install=auto_install):
        raise RuntimeError(
            "The 'ezdxf' package is required for DXF export. "
            "Install it with: pip install ezdxf"
        )
    import ezdxf
    from ezdxf import const as dxf_const

    doc = ezdxf.new(dxfversion="R2010", setup=True)
    msp = doc.modelspace()

    doc.layers.add(name=LAYER_BUILDINGS, color=DXF_COLOR_BUILDINGS)
    doc.layers.add(name=LAYER_GARAGES, color=DXF_COLOR_GARAGES)

    for b in buildings_xy:
        layer = b["layer"]
        color = DXF_COLOR_BUILDINGS if layer == LAYER_BUILDINGS else DXF_COLOR_GARAGES

        outer = b["outer"]
        holes = b["holes"]
        if len(outer) < 3:
            continue

        # Solid area fill. Nested-island detection (the default hatch style)
        # cuts the inner rings out of the outer ring.
        hatch = msp.add_hatch(color=color, dxfattribs={"layer": layer})
        hatch.set_solid_fill(color=color)
        hatch.paths.add_polyline_path(
            outer, is_closed=True,
            flags=dxf_const.BOUNDARY_PATH_EXTERNAL | dxf_const.BOUNDARY_PATH_POLYLINE,
        )
        for hole in holes:
            if len(hole) >= 3:
                hatch.paths.add_polyline_path(
                    hole, is_closed=True,
                    flags=dxf_const.BOUNDARY_PATH_OUTERMOST | dxf_const.BOUNDARY_PATH_POLYLINE,
                )

        # Also add the outline as an LWPOLYLINE (for CAD editing / snapping).
        msp.add_lwpolyline(outer, close=True, dxfattribs={"layer": layer})
        for hole in holes:
            if len(hole) >= 3:
                msp.add_lwpolyline(hole, close=True, dxfattribs={"layer": layer})

    doc.saveas(output_path)


# ---------------------------------------------------------------------------
# SVG export (no external dependencies)
# ---------------------------------------------------------------------------

def export_svg(buildings_xy, output_path, width=1600, margin=20):
    bounds = compute_bounds(buildings_xy)
    if bounds is None:
        raise RuntimeError("No buildings to export.")
    minx, miny, maxx, maxy = bounds
    w = max(maxx - minx, 1e-6)
    h = max(maxy - miny, 1e-6)
    scale = (width - 2 * margin) / w
    height = h * scale + 2 * margin

    def to_svg(pt):
        x, y = pt
        sx = margin + (x - minx) * scale
        sy = height - margin - (y - miny) * scale  # flip Y (SVG grows downward)
        return f"{sx:.2f},{sy:.2f}"

    parts = [
        f'<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width:.0f}" '
        f'height="{height:.0f}" viewBox="0 0 {width:.0f} {height:.0f}">',
        f'<rect width="100%" height="100%" fill="#ffffff"/>',
    ]
    for b in buildings_xy:
        if len(b["outer"]) < 3:
            continue
        color = COLOR_BUILDINGS_HEX if b["layer"] == LAYER_BUILDINGS else COLOR_GARAGES_HEX
        # Even-odd fill rule renders holes as white cut-outs.
        d = "M " + " L ".join(to_svg(p) for p in b["outer"]) + " Z"
        for hole in b["holes"]:
            if len(hole) >= 3:
                d += " M " + " L ".join(to_svg(p) for p in hole) + " Z"
        parts.append(f'<path d="{d}" fill="{color}" fill-rule="evenodd"/>')
    parts.append("</svg>")

    with open(output_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(parts))


# ---------------------------------------------------------------------------
# PNG export (requires Pillow)
# ---------------------------------------------------------------------------

def export_png(buildings_xy, output_path, width=1600, margin=20, auto_install=True):
    if not ensure_dependency("PIL", pip_name="Pillow", auto_install=auto_install):
        raise RuntimeError(
            "The 'Pillow' package is required for PNG export. "
            "Install it with: pip install Pillow"
        )
    from PIL import Image, ImageDraw

    bounds = compute_bounds(buildings_xy)
    if bounds is None:
        raise RuntimeError("No buildings to export.")
    minx, miny, maxx, maxy = bounds
    w = max(maxx - minx, 1e-6)
    h = max(maxy - miny, 1e-6)
    scale = (width - 2 * margin) / w
    height = int(h * scale + 2 * margin)

    def to_px(pt):
        x, y = pt
        px = margin + (x - minx) * scale
        py = height - margin - (y - miny) * scale
        return (px, py)

    img = Image.new("RGB", (int(width), height), "white")
    draw = ImageDraw.Draw(img)

    for b in buildings_xy:
        if len(b["outer"]) < 3:
            continue
        color = COLOR_BUILDINGS_HEX if b["layer"] == LAYER_BUILDINGS else COLOR_GARAGES_HEX
        draw.polygon([to_px(p) for p in b["outer"]], fill=color)
        # Paint holes back to white on top of the footprint.
        for hole in b["holes"]:
            if len(hole) >= 3:
                draw.polygon([to_px(p) for p in hole], fill="white")

    img.save(output_path)


# ---------------------------------------------------------------------------
# Export dispatch
# ---------------------------------------------------------------------------

def export_by_extension(buildings_xy, output_path, auto_install=True):
    ext = os.path.splitext(output_path)[1].lower()
    if ext == ".dxf":
        export_dxf(buildings_xy, output_path, auto_install=auto_install)
    elif ext == ".svg":
        export_svg(buildings_xy, output_path)
    elif ext == ".png":
        export_png(buildings_xy, output_path, auto_install=auto_install)
    else:
        raise ValueError(f"Unsupported output format: '{ext}'. Use .dxf, .svg or .png.")


def process_file(path):
    """Parse -> extract -> project. Returns projected buildings (may be empty)."""
    nodes, ways, relations = parse_osm(path)
    buildings = extract_buildings(nodes, ways, relations)
    projected, _ = project_buildings(buildings)
    return projected


# ---------------------------------------------------------------------------
# GUI
# ---------------------------------------------------------------------------

def run_gui(initial_path=None, auto_install=True):
    import tkinter as tk
    from tkinter import filedialog, messagebox

    class App:
        def __init__(self, root):
            self.root = root
            self.root.title("OSM Schwarzplan")
            self.root.geometry("900x700")

            self.buildings_xy = []
            self.current_path = None
            self.show_garages = tk.BooleanVar(value=True)

            # View transform for zoom/pan (screen = world*scale + offset).
            self.scale = 1.0
            self.offset = (0.0, 0.0)
            self._drag_start = None
            self._fit_pending = True

            top = tk.Frame(root)
            top.pack(fill="x", padx=8, pady=6)

            self.path_label = tk.Label(top, text="No file loaded.", anchor="w")
            self.path_label.pack(side="left", fill="x", expand=True)

            tk.Checkbutton(top, text="Show garages", variable=self.show_garages,
                           command=self.render_preview).pack(side="right", padx=4)
            tk.Button(top, text="Fit view", command=self.fit_view).pack(side="right", padx=4)
            tk.Button(top, text="Open file...",
                      command=self.open_file_dialog).pack(side="right", padx=4)

            self.canvas = tk.Canvas(root, bg="white", highlightthickness=0)
            self.canvas.pack(fill="both", expand=True, padx=8, pady=4)
            self.canvas.bind("<Configure>", self._on_resize)
            self.canvas.bind("<ButtonPress-1>", self._on_pan_start)
            self.canvas.bind("<B1-Motion>", self._on_pan_move)
            self.canvas.bind("<MouseWheel>", self._on_zoom)          # Windows/macOS
            self.canvas.bind("<Button-4>", self._on_zoom)            # Linux up
            self.canvas.bind("<Button-5>", self._on_zoom)            # Linux down

            bottom = tk.Frame(root)
            bottom.pack(fill="x", padx=8, pady=6)

            self.status_label = tk.Label(bottom, text="Ready.", anchor="w")
            self.status_label.pack(side="left", fill="x", expand=True)

            self.btn_export = tk.Button(bottom, text="Export...",
                                        command=self.export_clicked, state="disabled")
            self.btn_export.pack(side="right", padx=4)

        # -- status ------------------------------------------------------
        def set_status(self, text):
            self.status_label.config(text=text)
            self.root.update_idletasks()

        # -- file loading ------------------------------------------------
        def open_file_dialog(self):
            path = filedialog.askopenfilename(
                title="Choose an OSM file",
                filetypes=[("OSM XML", "*.osm"), ("All files", "*.*")]
            )
            if path:
                self.load_and_process(path)

        def load_and_process(self, path):
            self.current_path = path
            self.path_label.config(text=path)
            self.set_status("Loading and parsing OSM file ...")
            try:
                nodes, ways, relations = parse_osm(path)
                self.set_status(
                    f"Found {len(nodes)} nodes, {len(ways)} ways, "
                    f"{len(relations)} relations. Filtering buildings ..."
                )
                buildings = extract_buildings(nodes, ways, relations)
                if not buildings:
                    messagebox.showinfo(
                        "No buildings",
                        "No building=* objects were found in this file.")
                    self.set_status("No buildings found.")
                    self.btn_export.config(state="disabled")
                    return
                self.buildings_xy, _ = project_buildings(buildings)
                n_garages = sum(1 for b in self.buildings_xy
                                if b["layer"] == LAYER_GARAGES)
                n_buildings = len(self.buildings_xy) - n_garages
                self.set_status(
                    f"{len(self.buildings_xy)} footprints loaded "
                    f"({n_buildings} buildings, {n_garages} garages).")
                self._fit_pending = True
                self.fit_view()
                self.btn_export.config(state="normal")
            except Exception as e:  # noqa: BLE001 - surfaced in a dialog
                messagebox.showerror("Error while reading", str(e))
                self.set_status("Error while reading.")
                self.btn_export.config(state="disabled")

        # -- view transform ---------------------------------------------
        def _visible(self):
            if self.show_garages.get():
                return self.buildings_xy
            return [b for b in self.buildings_xy if b["layer"] != LAYER_GARAGES]

        def fit_view(self):
            bounds = compute_bounds(self._visible() or self.buildings_xy)
            if bounds is None:
                return
            cw = max(self.canvas.winfo_width(), 1)
            ch = max(self.canvas.winfo_height(), 1)
            margin = 20
            minx, miny, maxx, maxy = bounds
            w = max(maxx - minx, 1e-6)
            h = max(maxy - miny, 1e-6)
            self.scale = min((cw - 2 * margin) / w, (ch - 2 * margin) / h)
            # Center the drawing.
            cx = (minx + maxx) / 2
            cy = (miny + maxy) / 2
            self.offset = (cw / 2 - cx * self.scale, ch / 2 + cy * self.scale)
            self._fit_pending = False
            self.render_preview()

        def _to_canvas(self, pt):
            x, y = pt
            ox, oy = self.offset
            return (x * self.scale + ox, oy - y * self.scale)

        def _on_resize(self, _event):
            if self._fit_pending:
                self.fit_view()
            else:
                self.render_preview()

        def _on_pan_start(self, event):
            self._drag_start = (event.x, event.y, self.offset)

        def _on_pan_move(self, event):
            if not self._drag_start:
                return
            sx, sy, (ox, oy) = self._drag_start
            self.offset = (ox + (event.x - sx), oy + (event.y - sy))
            self.render_preview()

        def _on_zoom(self, event):
            if not self.buildings_xy:
                return
            factor = 1.1 if getattr(event, "delta", 0) > 0 or event.num == 4 else 1 / 1.1
            ox, oy = self.offset
            # Keep the point under the cursor fixed while zooming.
            self.offset = (
                event.x - (event.x - ox) * factor,
                event.y - (event.y - oy) * factor,
            )
            self.scale *= factor
            self.render_preview()

        # -- rendering ---------------------------------------------------
        def render_preview(self):
            self.canvas.delete("all")
            for b in self._visible():
                color = (COLOR_BUILDINGS_HEX if b["layer"] == LAYER_BUILDINGS
                         else COLOR_GARAGES_HEX)
                outer_pts = [self._to_canvas(p) for p in b["outer"]]
                if len(outer_pts) >= 3:
                    flat = [c for pt in outer_pts for c in pt]
                    self.canvas.create_polygon(flat, fill=color, outline="")
                for hole in b["holes"]:
                    hole_pts = [self._to_canvas(p) for p in hole]
                    if len(hole_pts) >= 3:
                        flat_hole = [c for pt in hole_pts for c in pt]
                        self.canvas.create_polygon(flat_hole, fill="white", outline="")

        # -- export ------------------------------------------------------
        def export_clicked(self):
            if not self.buildings_xy:
                return
            base, _ = os.path.splitext(self.current_path or "schwarzplan")
            default_name = base + "_schwarzplan.dxf"
            out_path = filedialog.asksaveasfilename(
                title="Save as",
                defaultextension=".dxf",
                initialfile=os.path.basename(default_name),
                initialdir=os.path.dirname(default_name) or None,
                filetypes=[("DXF file", "*.dxf"), ("SVG file", "*.svg"),
                           ("PNG image", "*.png")]
            )
            if not out_path:
                return
            try:
                self.set_status(f"Exporting {os.path.basename(out_path)} ...")
                export_by_extension(self.buildings_xy, out_path,
                                    auto_install=auto_install)
                self.set_status(f"Saved: {out_path}")
                messagebox.showinfo("Done", f"File saved:\n{out_path}")
            except Exception as e:  # noqa: BLE001 - surfaced in a dialog
                messagebox.showerror("Export error", str(e))
                self.set_status("Export error.")

    root = tk.Tk()
    app = App(root)
    if initial_path and os.path.isfile(initial_path):
        root.after(200, lambda: app.load_and_process(initial_path))
    root.mainloop()


# ---------------------------------------------------------------------------
# Command line entry point
# ---------------------------------------------------------------------------

def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Create a Schwarzplan (figure-ground plan) from OSM data.")
    parser.add_argument("input", nargs="?", help="Input .osm file (OSM XML).")
    parser.add_argument("-o", "--output",
                        help="Output file (.dxf, .svg or .png). Enables headless export.")
    parser.add_argument("--no-gui", action="store_true",
                        help="Do not open the window; requires --input and --output.")
    parser.add_argument("--no-install", action="store_true",
                        help="Do not auto-install missing packages (ezdxf/Pillow).")
    args = parser.parse_args(argv)
    auto_install = not args.no_install

    # Headless export path.
    if args.output:
        if not args.input or not os.path.isfile(args.input):
            parser.error("A valid --input .osm file is required for export.")
        print(f"[1/3] Parsing {args.input} ...")
        buildings_xy = process_file(args.input)
        if not buildings_xy:
            print("[Done] No building=* objects found.")
            return 1
        print(f"[2/3] {len(buildings_xy)} footprints extracted.")
        print(f"[3/3] Exporting {args.output} ...")
        export_by_extension(buildings_xy, args.output, auto_install=auto_install)
        print(f"[Done] Saved: {args.output}")
        if args.no_gui:
            return 0

    if args.no_gui:
        parser.error("--no-gui requires --output.")

    run_gui(initial_path=args.input, auto_install=auto_install)
    return 0


if __name__ == "__main__":
    sys.exit(main())
