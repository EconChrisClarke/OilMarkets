#!/usr/bin/env python3
"""US fuel and crude pipelines, with line width set by stated capacity.

Inputs:
  data/geo/pipelines_products.geojson   EIA refined-product pipeline routes
  data/geo/pipelines_crude.geojson      EIA crude-oil trunk pipeline routes
                                        (both from scripts/fetch_pipelines.py)
  data/pipelines/pipeline_capacity.csv  hand-curated capacity for the main
                                        lines, one row per line, with source,
                                        link and quote; use_width=Y rows set a
                                        route's width, the rest are listed but
                                        drawn thin
Outputs:
  maps/configs/pipelines-us.json
  data/pipelines/pipeline_capacity_sources.xlsx   the sourcing spreadsheet

A capacity row matches EIA route features by operator and pipeline name
(Opername, Pipename), or by feature id (fids) where one EIA name covers
several lines (Enbridge's Lakehead System, Keystone's legs). Capacity covers
every product a line carries (gasoline, diesel, jet fuel), not diesel alone.
"""

import csv
import json
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

ROOT = Path(__file__).resolve().parent.parent
GEO = ROOT / "data" / "geo"
CAP = ROOT / "data" / "pipelines" / "pipeline_capacity.csv"

RED, NAVY = "#C71E1D", "#1B3A5C"
LAYERS = {"refined": ("Refined products", RED, "pipelines_products.geojson"),
          "crude": ("Crude oil", NAVY, "pipelines_crude.geojson")}
# left off the map: Southern Lights carries diluent north to Alberta, not fuel
EXCLUDE = {("ENBRIDGE", "Southern Lights")}

rows = list(csv.DictReader(CAP.open()))
# features that change capacity part way along: split at the vertex nearest
# this point; "s" is the part from the feature's start to the split, "n" the rest
SPLIT = {40: (-79.85, 36.07),     # Colonial at Greensboro, NC
         181: (-112.1, 33.4)}      # Kinder Morgan SFPP at Phoenix: East Line / West Line


def split_at(ls, pt, part):
    """the part of a single-part line before ("s") or after ("n") its vertex nearest pt"""
    (l,) = ls
    i = min(range(len(l)), key=lambda k: (l[k][0] - pt[0]) ** 2 + (l[k][1] - pt[1]) ** 2)
    return [l[:i + 1]] if part == "s" else [l[i:]]


def lines_of(g):
    return g["coordinates"] if g["type"] == "MultiLineString" else [g["coordinates"]]


def rnd(ls):
    return [[[round(x, 3), round(y, 3)] for x, y in l] for l in ls]


layers, unmatched = [], []
for key, (label, color, fname) in LAYERS.items():
    feats = [f for f in json.load((GEO / fname).open())["features"] if f["geometry"]]
    used = set()
    out = []
    for r in [r for r in rows if r["layer"] == key and r["pipename"]]:
        names = r["pipename"].split(";")
        # "40:s" / "40:n": the part of feature 40 before / after its SPLIT point
        fids = {int(x.split(":")[0]): (x.split(":") + [""])[1] for x in r["fids"].split(";")} if r["fids"] else None
        hit = [f for f in feats
               if f["properties"]["Opername"] == r["operator"]
               and (names == ["*"] or f["properties"]["Pipename"] in names)
               and (fids is None or f["properties"]["FID"] in fids)]
        if not hit:
            unmatched.append(r["name"])
            continue
        used |= {f["properties"]["FID"] for f in hit}
        coords = []
        for f in hit:
            ls = lines_of(f["geometry"])
            part = fids.get(f["properties"]["FID"]) if fids else ""
            if part:
                ls = split_at(ls, SPLIT[f["properties"]["FID"]], part)
            coords += ls
        out.append({"name": r["name"], "route": r["route"],
                    "value": int(r["capacity_bpd"]) if r["use_width"] == "Y" else None,
                    "measure": r["measure"], "coords": rnd(coords)})
        r["_segments"] = len(hit)
    # every other route in the layer: thin, named by the EIA layer
    for f in feats:
        p = f["properties"]
        if p["FID"] in used or (p["Opername"], p["Pipename"]) in EXCLUDE:
            continue
        out.append({"name": f'{p["Pipename"]} ({p["Opername"].title()})', "route": "", "value": None,
                    "coords": rnd(lines_of(f["geometry"]))})
    layers.append({"id": key, "label": label, "color": color, "lines": out})
if unmatched:
    raise SystemExit(f"capacity rows with no EIA route: {unmatched}")

cfg = {
    "headline": "Fuel pipelines crowd the Gulf-to-East Coast corridor; the West has few",
    "subhead": "US refined-product and crude oil pipelines; line width shows capacity, barrels per day",
    "note": ("Capacity covers everything a line carries (gasoline, diesel, jet fuel), not diesel alone; "
             "some lines show their volume where capacity is not published. Thin lines: no figure published for "
             "that line. Each figure's source is in the accompanying spreadsheet."),
    "source": ("Routes: EIA (via HIFLD). Capacity: EIA regional transportation fuels studies and liquids pipeline "
               "projects database; company 10-K filings; company websites"),
    "sourceUrl": "https://github.com/EconChrisClarke/OilMarkets/blob/main/data/pipelines/pipeline_capacity_sources.xlsx",
    "units": "b/d",
    "style": "flows",
    "geoBBox": [-130, 20, -60, 56],
    "nodes": {},
    "flows": [],
    "lineLayers": layers,
    "lineWidthMax": 16,
    "lineLegend": [250000, 1000000, 2500000],
    "lineLegendTitle": "Capacity",
    "lineThinLabel": "Not published",
    "lineLabels": [
        {"text": "Colonial", "lonlat": [-83.6, 34.9], "layer": "refined", "align": "right"},
        {"text": "Products SE", "lonlat": [-86.4, 32.2], "layer": "refined", "align": "left"},
        {"text": "Explorer", "lonlat": [-95.2, 37.0], "layer": "refined", "align": "right"},
        {"text": "Enbridge Mainline", "lonlat": [-104.0, 49.9], "layer": "crude", "align": "left"},
        {"text": "Keystone", "lonlat": [-98.4, 44.5], "layer": "crude", "align": "right"},
        {"text": "Dakota Access", "lonlat": [-96.6, 44.6], "layer": "crude", "align": "left"},
        {"text": "Seaway", "lonlat": [-95.5, 33.0], "layer": "crude", "align": "left"},
    ],
    "frames": {
        "substack": {"bounds": [[-124.5, 25], [-67, 50]]},
        "vertical": {"bounds": [[-124.5, 25], [-67, 50]]},
        # a little more sea at the bottom, so the key sits below the Southwest's lines
        "square": {"bounds": [[-124.5, 21.2], [-67, 50]], "lineKeyAt": [-126.0, 24.6]},
    },
}
out = ROOT / "maps" / "configs" / "pipelines-us.json"
out.write_text(json.dumps(cfg, separators=(",", ":")) + "\n")
print(f"wrote {out.relative_to(ROOT)} ({sum(len(L['lines']) for L in layers)} routes, "
      f"{sum(1 for L in layers for l in L['lines'] if l['value'])} with width)")

# ---- sourcing spreadsheet ---------------------------------------------------
wb = Workbook()
ws = wb.active
ws.title = "Pipelines"
F = "Arial"
cols = [("Layer", 11), ("Pipeline", 38), ("Route", 40), ("Capacity (b/d)", 15), ("Measure", 24),
        ("As of", 8), ("Source type", 22), ("Source", 44), ("Link", 50), ("Quote from source", 60),
        ("Notes", 60), ("Width on map", 13), ("EIA route segments", 12)]
ws.append([c for c, _ in cols])
for r in rows:
    ws.append([
        "Refined products" if r["layer"] == "refined" else "Crude oil",
        r["name"], r["route"],
        int(r["capacity_bpd"]) if r["capacity_bpd"] else None,
        r["measure"], r["as_of"], r["source_type"], r["source"], r["source_url"], r["quote"], r["note"],
        {"Y": "Yes", "N": "No (thin)"}[r["use_width"]], r.get("_segments", ""),
    ])
head_fill = PatternFill("solid", fgColor="1B3A5C")
for i, (_, w) in enumerate(cols, 1):
    ws.column_dimensions[get_column_letter(i)].width = w
    c = ws.cell(1, i)
    c.font = Font(name=F, bold=True, color="FFFFFF")
    c.fill = head_fill
    c.alignment = Alignment(vertical="center", wrap_text=True)
ws.row_dimensions[1].height = 30
band = PatternFill("solid", fgColor="F7F0F1")
for ri in range(2, ws.max_row + 1):
    for ci in range(1, len(cols) + 1):
        c = ws.cell(ri, ci)
        c.font = Font(name=F, size=10)
        c.alignment = Alignment(vertical="top", wrap_text=True)
        if ri % 2 == 0:
            c.fill = band
    ws.cell(ri, 4).number_format = "#,##0"
    link = ws.cell(ri, 9)
    if link.value:
        link.hyperlink = link.value
        link.font = Font(name=F, size=10, color="1155CC", underline="single")
ws.freeze_panes = "C2"
ws.auto_filter.ref = f"A1:{get_column_letter(len(cols))}{ws.max_row}"

n = ws.max_row
about = wb.create_sheet("About")
lines = [
    ("US fuel pipelines: capacity and sources", True),
    ("", False),
    ("What this is", True),
    ("The main US refined-product and crude oil trunk pipelines on the map, with the capacity used for each "
     "line's width and where that number comes from.", False),
    ("", False),
    ("How to read it", True),
    ("Capacity (b/d): barrels per day. For refined-product lines it covers every product the line carries "
     "(gasoline, diesel, jet fuel), not diesel alone.", False),
    ("Measure: 'Capacity' unless stated. Where no capacity is published, a line is drawn at its throughput "
     "(actual volume, with the year); one figure is derived from two published figures, with the arithmetic "
     "in its notes.", False),
    ("Source type: Official (EIA) or Official (EIA study), Company SEC filing (10-K), Company website, Derived, or "
     "Press. EIA studies are its regional Transportation Fuels Markets reports (West Coast 2015, East and Gulf "
     "Coasts 2016, Midwest and Rocky Mountains 2017), which list capacity by pipeline segment. Press figures "
     "could not be confirmed from an operator or official document; they are the best available and are drawn "
     "at the reported value.", False),
    ("Width on map: 'No (thin)' lines have no capacity figure from any source and appear at a fixed thin width.", False),
    ("", False),
    ("Summary", True),
    ("Lines listed", False), ("Drawn with width", False), ("Refined-product capacity drawn (b/d)", False),
    ("Crude capacity drawn (b/d)", False),
    ("", False),
    ("Routes: EIA refined-product and crude oil trunk pipeline layers, as republished on the federal HIFLD "
     "open-data service (scripts/fetch_pipelines.py).", False),
    ("Built by scripts/process_pipeline_map.py from data/pipelines/pipeline_capacity.csv.", False),
]
for i, (t, bold) in enumerate(lines, 1):
    c = about.cell(i, 1, t)
    c.font = Font(name=F, size=14 if i == 1 else 10, bold=bold)
    c.alignment = Alignment(wrap_text=True, vertical="top")
about.column_dimensions["A"].width = 100
about.column_dimensions["B"].width = 18
start = [i for i, (t, _) in enumerate(lines, 1) if t == "Lines listed"][0]
about.cell(start, 2, f"=COUNTA(Pipelines!B2:B{n})")
about.cell(start + 1, 2, f'=COUNTIF(Pipelines!L2:L{n},"Yes")')
about.cell(start + 2, 2, f'=SUMIFS(Pipelines!D2:D{n},Pipelines!A2:A{n},"Refined products",Pipelines!L2:L{n},"Yes")')
about.cell(start + 3, 2, f'=SUMIFS(Pipelines!D2:D{n},Pipelines!A2:A{n},"Crude oil",Pipelines!L2:L{n},"Yes")')
for k in range(4):
    c = about.cell(start + k, 2)
    c.font = Font(name=F, size=10)
    c.number_format = "#,##0"
wb.move_sheet("About", offset=-1)
wb.calculation.fullCalcOnLoad = True           # summary formulas compute when the file opens
xo = ROOT / "data" / "pipelines" / "pipeline_capacity_sources.xlsx"
wb.save(xo)
print(f"wrote {xo.relative_to(ROOT)} ({len(rows)} pipelines)")
