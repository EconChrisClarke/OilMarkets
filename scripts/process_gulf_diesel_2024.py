#!/usr/bin/env python3
"""Where Gulf Coast (PADD 3) diesel goes: abroad vs the rest of the US, 2024.

Fetches EIA's annual distillate movements out of PADD 3 by mode, keeps a
tidy copy, and writes the map config for the Gulf diesel map.

Inputs:
  EIA, "Movements by Pipeline, Tanker, Barge and Rail between PAD Districts"
      (fetched; pages named pet_move_<mode>_dc_<to>-<from>_mbbl_a.htm)
  data/census_trade/distillate_exports_district_country_2024.csv
      (from fetch_distillate_2024.py)
Outputs:
  data/eia/distillate_padd3_outflows_2020_2025.csv
      destination PADD x mode x year, thousand barrels and barrels per day
  data/census_trade/distillate_exports_padd3_by_region_2024.csv
  maps/configs/gulf-diesel-2024.json
"""

import csv
import html
import json
import re
import urllib.request
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EIA_DIR = ROOT / "data" / "eia"
CT = ROOT / "data" / "census_trade"
URL = "https://www.eia.gov/dnav/pet/pet_move_{mode}_dc_{to}-R30_mbbl_a.htm"
DEST = {"R10": "East Coast (PADD 1)", "R20": "Midwest (PADD 2)",
        "R40": "Rockies (PADD 4)", "R50": "West Coast (PADD 5)"}
MODES = {"ptb": "all", "pipe": "pipeline", "tb": "tanker and barge"}
YEAR = 2024
DAYS = {2020: 366, 2021: 365, 2022: 365, 2023: 365, 2024: 366, 2025: 365}


def fetch_row(mode, to):
    """The Distillate Fuel Oil row of one EIA movement table, {year: kbbl}."""
    req = urllib.request.Request(URL.format(mode=mode, to=to), headers={"User-Agent": "Mozilla/5.0"})
    try:
        s = urllib.request.urlopen(req, timeout=30).read().decode("latin-1")
    except urllib.error.HTTPError as e:
        if e.code == 404:          # EIA has no table for this mode and route
            return {}
        raise
    t = html.unescape(re.sub(r"(\s*\|\s*)+", " | ", re.sub(r"<[^>]+>", " | ", s)))
    years = [int(y) for y in re.search(r"((?:\| \d{4} ){6})\|", t).group(1).split("|")[1:] if y.strip()]
    cells = re.search(r"\| Distillate Fuel Oil \|((?: [^|A-Za-z]* \|){6})", t).group(1).split("|")[:6]
    return {y: int(c.replace(",", "")) for y, c in zip(years, cells) if c.strip().replace(",", "").isdigit()}


rows = []
for to, dname in DEST.items():
    for mode, mname in MODES.items():
        for y, kb in fetch_row(mode, to).items():
            rows.append([y, "Gulf Coast (PADD 3)", dname, mname, kb, round(kb * 1000 / DAYS[y])])
EIA_DIR.mkdir(parents=True, exist_ok=True)
out = EIA_DIR / "distillate_padd3_outflows_2020_2025.csv"
with out.open("w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["year", "from", "to", "mode", "thousand_barrels", "barrels_per_day"])
    w.writerows(sorted(rows, key=lambda r: (r[0], r[2], r[3])))
print(f"wrote {out.relative_to(ROOT)} ({len(rows)} rows)")
dom = {(r[2], r[3]): r[5] for r in rows if r[0] == YEAR}

# ---- exports from PADD 3 customs districts --------------------------------
# Houston-Galveston, Port Arthur, New Orleans, Mobile, Laredo, El Paso. All sit
# in PADD 3 (Texas, Louisiana, Mississippi, Alabama, New Mexico, ...).
PADD3_DISTRICTS = {"53", "21", "20", "19", "23", "24"}


def region(code):
    c = int(code)
    if c == 2010: return "Mexico"
    if c == 1220: return "Canada"
    if 2010 < c < 4000: return "Latin America"      # Central, Caribbean, South
    if 4000 <= c < 5000: return "Europe"
    return "Other"


ex = Counter()
for r in csv.DictReader(open(CT / "distillate_exports_district_country_2024.csv")):
    if r["SUMMARY_LVL"] == "DET" and r["DISTRICT"] in PADD3_DISTRICTS and r["CTY_CODE"] != "-":
        ex[region(r["CTY_CODE"])] += int(r["QTY_1_YR"]) / 366
out = CT / "distillate_exports_padd3_by_region_2024.csv"
with out.open("w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["from", "destination_region", "barrels_per_day"])
    for g, v in ex.most_common():
        w.writerow(["Gulf Coast (PADD 3) customs districts", g, round(v)])
print(f"wrote {out.relative_to(ROOT)}")

abroad = sum(ex.values())
home = sum(v for (d, m), v in dom.items() if m == "all")
east, east_pipe = dom[(DEST["R10"], "all")], dom[(DEST["R10"], "pipeline")]
west, west_pipe = dom[(DEST["R50"], "all")], dom.get((DEST["R50"], "pipeline"), 0)
print(f"{YEAR}: abroad {abroad:,.0f} b/d, rest of US {home:,.0f} b/d")
print(f"  East Coast {east:,.0f} ({east_pipe/east:.0%} pipeline), West {west:,.0f} ({west_pipe/west:.0%} pipeline)")
for (d, m), v in sorted(dom.items()):
    print(f"  {d:22s} {m:17s} {v:9,.0f}")
print("  exports:", {g: round(v) for g, v in ex.most_common()})

# ---- map config -----------------------------------------------------------
NAVY = "#1B3A5C"
MIN = 10000
flows = [
    {"from": "gulf", "to": "east", "value": east, "toward": [-76, 39], "length": 330},
    {"from": "gulf", "to": "midwest", "value": dom[(DEST["R20"], "all")], "toward": [-91, 40]},
    {"from": "gulf", "to": "west", "value": west, "toward": [-112, 33.4]},
    {"from": "gulf", "to": "latam", "value": ex["Latin America"]},
    {"from": "gulf", "to": "europe", "value": ex["Europe"], "toward": [-60, 24.5]},
    {"from": "gulf", "to": "mexico", "value": ex["Mexico"], "toward": [-99, 22]},
]
flows = [dict(f, value=round(f["value"], -3)) for f in flows if f["value"] >= MIN]
shown = sum(f["value"] for f in flows)
cfg = {
    "headline": "The Gulf Coast sends more diesel abroad than to the rest of the US",
    "subhead": f"Distillate fuel oil leaving the Gulf Coast (PADD 3) by destination, {YEAR}, barrels per day",
    "note": (f"{east_pipe/east:.0%} of East Coast deliveries go by pipeline. None went to the West Coast "
             "by ship; the Arizona flow is by pipeline."),
    "source": "EIA, Movements by Pipeline, Tanker, Barge and Rail between PAD Districts; US Census Bureau, International Trade API (HS10)",
    "sourceUrl": "https://www.eia.gov/dnav/pet/pet_move_ptb_a_EPD0_TNR_mbbl_a.htm",
    "units": "b/d",
    "draft": False,
    "style": "fan",
    "arrowStyle": "swoosh",
    # less curve than the house default: at this width a full swoosh bends
    # the East Coast arrow into a quarter-disc
    "swooshBend": 0.05,
    "arrowLength": 170,
    # Same width scale and key as the export and import maps (320k b/d drawn
    # 32 wide), so the three maps can be compared arrow for arrow.
    "maxArrowWidth": 32,
    "widthMaxValue": 320000,
    "legendTitle": "Arrow width",
    "legend": [50000, 200000],
    "geoBBox": [-170, -25, -20, 75],
    "nodes": {
        "gulf": {"label": "Gulf Coast", "lonlat": [-93.0, 29.9], "labelAt": [-97.2, 28.6],
                 "sides": ["left", "above", "below"]},
        "east": {"label": "East Coast", "arrowLabel": "To the East Coast", "color": NAVY, "lonlat": [-74.2, 40.6], "labelAt": [-71.5, 37.5], "sides": ["right", "above", "below"]},
        "midwest": {"label": "Midwest", "arrowLabel": "To the Midwest", "color": NAVY, "lonlat": [-90, 40]},
        "west": {"label": "West", "arrowLabel": "To Arizona", "color": NAVY, "lonlat": [-112, 33.4]},
        "latam": {"label": "Latin America", "color": "#C71E1D", "lonlat": [-80, 11]},
        "mexico": {"label": "Mexico", "color": "#7A1712", "lonlat": [-101.5, 21.5]},
        "europe": {"label": "Europe", "color": "#E8A33D", "textColor": "#9A5B0C", "lonlat": [-40, 38]},
    },
    "flows": flows,
    # Same frames as the export map.
    "frames": {
        "substack": {"bounds": [[-126, 14], [-62, 50]]},
        # narrower frames have no sea east of the arrowhead: label it over Maine
        "vertical": {"bounds": [[-125, 14], [-63, 49]], "shortLabels": True,
                     "nodes": {"east": {"labelAt": [-69.5, 45], "sides": ["above", "left"]}}},
        "square": {"bounds": [[-124, 14], [-66, 50]],
                   "nodes": {"east": {"labelAt": [-69.5, 45], "sides": ["above", "left"]}}},
    },
}
out = ROOT / "maps" / "configs" / "gulf-diesel-2024.json"
out.write_text(json.dumps(cfg, indent=2) + "\n")
print(f"wrote {out.relative_to(ROOT)} ({len(flows)} flows, {shown/(abroad+home):.0%} of outflows drawn)")
