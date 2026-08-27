# Project structure

```
osm-schwarzplan/
├── osm_schwarzplan.py          # The entire application (GUI + CLI + exporters)
├── run.bat                     # Windows drag-and-drop launcher
├── sample.osm                  # Tiny test dataset (building, garage, courtyard)
├── requirements.txt            # Optional deps: ezdxf (DXF), Pillow (PNG)
├── README.md
├── LICENSE                     # MIT
├── .gitignore
└── docs/
    ├── PROJECT_STRUCTURE.md    # This file
    ├── PYTHON_SETUP.md         # Beginner guide: installing Python
    └── images/                 # README example images (WebP)
        ├── before-openstreetmap.webp
        ├── after-schwarzplan.webp
        └── originals/          # Uncompressed PNG sources
```

The whole tool is intentionally a **single file** — easy to read, copy, and run
without a build step.

## Processing pipeline

`osm_schwarzplan.py` is organized top-to-bottom as the data flow:

| Stage | Function(s) | Purpose |
| --- | --- | --- |
| Parse | `parse_osm` | Stream OSM XML with `iterparse` → nodes / ways / relations. |
| Filter | `is_building`, `classify_layer`, `extract_buildings` | Keep real `building=*`, drop `building=no`, split garages, stitch multipolygons. |
| Rings | `assemble_rings`, `_assign_holes_to_outers`, `_ring_contains_point` | Join partial ways into closed rings; assign each hole to its containing outer ring. |
| Project | `project_buildings`, `compute_bounds` | Lat/lon → local meters (equirectangular tangent plane at the map center). |
| Export | `export_dxf`, `export_svg`, `export_png`, `export_by_extension` | Write DXF (HATCH + polylines), SVG (even-odd holes), or PNG (Pillow). |
| UI | `run_gui` (class `App`) | Tkinter preview with zoom / pan / fit / garage toggle. |
| Entry | `main` | `argparse` CLI; headless export or launch the GUI. |

## Key design decisions

- **Streaming parse** (`iterparse` + `el.clear()`) keeps memory flat on large
  extracts.
- **Holes are geometric**, not painted: assigned to the correct outer ring by a
  point-in-polygon test, and cut out via DXF nested-island detection / SVG
  `fill-rule="evenodd"`.
- **Optional dependencies are lazy** — imported only inside the exporter that
  needs them, so SVG export and the GUI work with zero third-party packages.

## Verifying a change

There is no test framework; the fastest end-to-end check is headless export
against the bundled sample:

```bash
python osm_schwarzplan.py sample.osm -o out.svg --no-gui   # no deps needed
python osm_schwarzplan.py sample.osm -o out.dxf --no-gui   # exercises ezdxf
python osm_schwarzplan.py sample.osm -o out.png --no-gui   # exercises Pillow
```

`sample.osm` deliberately contains a plain building, a `building=garage`, a
`building=no` (must be ignored), and a `type=multipolygon` with a courtyard
(must produce one hole) — so a correct run yields **3 footprints**, one of them
with **1 hole**, one on the **GARAGES** layer.

## Developer tooling (Claude Code skills)

This repo was built with [Claude Code](https://claude.com/claude-code). Handy
built-in skills / slash commands for working on it:

| Skill / command | Use it to |
| --- | --- |
| `/init` | (Re)generate a `CLAUDE.md` with codebase notes for the agent. |
| `/code-review` | Review the current diff for correctness bugs and cleanups. |
| `/simplify` | Apply reuse / simplification / efficiency cleanups. |
| `/security-review` | Security pass over pending changes. |
| `verify` | Drive the change end-to-end and observe real behavior. |
| `compress-images` | Re-compress `docs/images/` to WebP (used for the examples). |
| `image-optimization` | General web image-size reduction guidance. |

These are optional conveniences — the application itself has no dependency on
them.
