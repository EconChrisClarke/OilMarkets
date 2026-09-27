#!/usr/bin/env python3
"""Turn the raw 2024 Census distillate files into summary tables and the
map config for the export arrow map.

Inputs  (from fetch_distillate_2024.py): data/census_trade/*.csv
Outputs:
  data/census_trade/distillate_exports_by_district_2024.csv
      district x destination region, barrels per day (measured)
  data/census_trade/distillate_imports_by_district_2024.csv
      district x origin country, barrels per day (measured)
  data/census_trade/distillate_exports_by_port_2024_est.csv
      port-level ESTIMATE: district barrels split by each port's share of the
      district's HS 271019 export value (ports are published only at HS6)
  maps/configs/diesel-exports-2024.json
"""

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
D = ROOT / "data" / "census_trade"
DAYS = 366  # 2024 is a leap year


def region(code):
    c = int(code)
    if c == 2010: return "Mexico"
    if c == 1220: return "Canada"
    if 2010 < c <= 2250: return "Central America"
    if 2250 < c < 3000: return "Caribbean"
    if 3000 <= c < 4000: return "South America"
    if 4000 <= c < 5000: return "Europe"
    if 5000 <= c < 6000: return "Asia"
    if 6000 <= c < 7000: return "Oceania"
    if 7000 <= c < 8000: return "Africa"
    return "Other"


def detail(rows):
    """Country-level rows only: drop country groupings and both total rows."""
    return [r for r in rows if r["SUMMARY_LVL"] == "DET"
            and r["DISTRICT"] != "-" and r["CTY_CODE"] != "-"]


def write(path, header, rows):
    with path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)
    print(f"wrote {path.relative_to(ROOT)} ({len(rows)} rows)")


# ---- exports by district and region -------------------------------------
ex = detail(csv.DictReader(open(D / "distillate_exports_district_country_2024.csv")))
by_dr = Counter()
names = {}
for r in ex:
    by_dr[(r["DISTRICT"], region(r["CTY_CODE"]))] += int(r["QTY_1_YR"]) / DAYS
    names[r["DISTRICT"]] = r["DIST_NAME"]
write(D / "distillate_exports_by_district_2024.csv",
      ["district", "district_name", "destination_region", "barrels_per_day"],
      sorted([[d, names[d], g, round(v)] for (d, g), v in by_dr.items()],
             key=lambda x: -x[3]))
total_ex = sum(by_dr.values())

# ---- imports by district and country -------------------------------------
im = detail(csv.DictReader(open(D / "distillate_imports_district_country_2024.csv")))
by_dc = Counter()
for r in im:
    by_dc[(r["DISTRICT"], r["DIST_NAME"], r["CTY_NAME"])] += int(r["GEN_QY1_YR"]) / DAYS
write(D / "distillate_imports_by_district_2024.csv",
      ["district", "district_name", "origin_country", "barrels_per_day"],
      sorted([[d, n, c, round(v)] for (d, n, c), v in by_dc.items()], key=lambda x: -x[3]))
total_im = sum(by_dc.values())

# ---- port-level estimate --------------------------------------------------
ports = [r for r in csv.DictReader(open(D / "hs271019_exports_port_2024.csv"))
         if r["SUMMARY_LVL"] == "DET" and r["CTY_CODE"] == "-" and r["PORT"] != "-"]
dist_val = Counter()
for p in ports:
    dist_val[p["PORT"][:2]] += int(p["ALL_VAL_YR"])
dist_bpd = Counter()
for (d, _), v in by_dr.items():
    dist_bpd[d] += v
est = []
for p in ports:
    d = p["PORT"][:2]
    if dist_val[d] and dist_bpd[d]:
        share = int(p["ALL_VAL_YR"]) / dist_val[d]
        est.append([p["PORT"], p["PORT_NAME"], d, names.get(d, ""), round(share, 4),
                    round(dist_bpd[d] * share)])
write(D / "distillate_exports_by_port_2024_est.csv",
      ["port", "port_name", "district", "district_name", "share_of_district_hs271019_value",
       "barrels_per_day_est"],
      sorted([e for e in est if e[5] >= 500], key=lambda x: -x[5]))

# ---- map config -----------------------------------------------------------
# Export gateways: districts grouped so origins on the map sit far enough
# apart to read. Land crossings stay separate because they are far apart.
GATEWAYS = {
    "txgulf": {"label": "Texas Gulf Coast", "short": "Texas Gulf", "districts": ["53", "21"], "lonlat": [-94.9, 29.4], "sides": ["left", "above"]},
    # The Mobile district's distillate mostly leaves from Pascagoula, MS
    # (Chevron's refinery), so it joins the New Orleans district here.
    "la":     {"label": "Louisiana & Mississippi", "short": "LA & MS", "districts": ["20", "19"], "lonlat": [-90.2, 29.8], "sides": ["above", "nw", "ne", "right"]},
    "laredo": {"label": "Laredo", "districts": ["23"], "lonlat": [-99.5, 27.5], "sides": ["nw", "above", "left", "sw", "below"]},
    "elpaso": {"label": "El Paso", "districts": ["24"], "lonlat": [-106.45, 31.75], "sides": ["ne", "above", "nw"]},
    "nogales": {"label": "Nogales", "districts": ["26"], "lonlat": [-110.94, 31.34], "sides": ["sw", "ne", "nw", "left", "below"]},
    "pnw":    {"label": "Puget Sound", "districts": ["30"], "lonlat": [-123.2, 48.2]},
    "calif":  {"label": "California", "districts": ["27", "28"], "lonlat": [-120.9, 35.2]},
    "nyh":    {"label": "New York Harbor", "districts": ["10", "11"], "lonlat": [-74.1, 40.6]},
    "usvi":   {"label": "St. Croix", "districts": ["51"], "lonlat": [-64.75, 17.7], "sides": ["nw", "left", "above", "sw"]},
}
# Latin America merges Central, South America and the Caribbean: most of it
# heads for Panama (Chile, Peru and Ecuador are Pacific-coast buyers).
DEST_GROUP = {"Mexico": "mexico", "Central America": "latam", "South America": "latam",
              "Caribbean": "latam", "Europe": "europe"}
flows = Counter()
for (d, g), v in by_dr.items():
    for k, gw in GATEWAYS.items():
        if d in gw["districts"] and g in DEST_GROUP:
            flows[(k, DEST_GROUP[g])] += v
MIN = 3000
shown = sum(v for v in flows.values() if v >= MIN)

# Per-flow aim points, so arrows follow the sea route rather than crossing land.
TOWARD = {
    ("txgulf", "europe"): [-60, 24.5], ("la", "europe"): [-60, 24.5],
    ("nyh", "europe"): [-40, 41],
    ("pnw", "mexico"): [-125.5, 30], ("pnw", "latam"): [-124.5, 28],
    ("calif", "mexico"): [-116, 24], ("calif", "latam"): [-112, 14],
    ("txgulf", "mexico"): [-96.5, 20.5],
}
cfg = {
    "headline": "The US exports 1.2 million barrels of diesel a day, mostly from the Gulf",
    "subhead": "Distillate fuel oil exports by exporting region and destination, 2024, barrels per day",
    # Kept deliberately short; the definitions live in the data README.
    "note": f"Map covers {shown/total_ex:.0%} of exports.",
    "source": "US Census Bureau, International Trade API (exports by customs district, HS10)",
    "sourceUrl": "https://api.census.gov/data/timeseries/intltrade/exports/hs",
    "units": "b/d",
    "draft": False,
    "style": "fan",
    "arrowStyle": "swoosh",
    "arrowLength": 150,
    "maxArrowWidth": 32,
    "legendTitle": "Arrow width",
    "legend": [50000, 200000],
    "geoBBox": [-170, -25, -20, 75],
    "nodes": {k: {kk: g[kk] for kk in ("label", "short", "lonlat", "sides") if kk in g} for k, g in GATEWAYS.items()},
    "flows": [],
    "frames": {
        "substack": {"bounds": [[-126, 14], [-62, 50]]},
        "vertical": {"bounds": [[-125, 14], [-63, 49]], "labelMin": 30000, "shortLabels": True,
                     # on 9:16 the St. Croix arrow crowds the Caribbean: label over Panama
                     "nodes": {"latam": {"labelAt": [-80, 10], "sides": ["below", "se", "right"]}}},
        "square": {"bounds": [[-124, 14], [-66, 50]]},
    },
}
cfg["nodes"].update({
    "mexico": {"label": "Mexico", "color": "#7A1712", "lonlat": [-101.5, 21.5], "labelAt": [-102, 20.2], "sides": ["below", "sw", "se", "right", "left"]},
    "latam": {"label": "Latin America", "color": "#C71E1D", "lonlat": [-80, 11], "labelAt": [-86, 16.5], "sides": ["below", "se", "right", "sw", "left"]},
    "europe": {"label": "Europe", "color": "#E8A33D", "textColor": "#9A5B0C", "lonlat": [-40, 38]},
})
for (k, dest), v in sorted(flows.items(), key=lambda x: -x[1]):
    if v < MIN:
        continue
    f = {"from": k, "to": dest, "value": round(v, -3)}
    if (k, dest) in TOWARD:
        f["toward"] = TOWARD[(k, dest)]
    cfg["flows"].append(f)

out = ROOT / "maps" / "configs" / "diesel-exports-2024.json"
out.write_text(json.dumps(cfg, indent=2) + "\n")
print(f"wrote {out.relative_to(ROOT)} ({len(cfg['flows'])} flows)")
print(f"exports {total_ex:,.0f} b/d, imports {total_im:,.0f} b/d, arrows cover {shown/total_ex:.1%}")
for (k, dest), v in sorted(flows.items(), key=lambda x: -x[1]):
    print(f"  {k:8s} -> {dest:7s} {v:9,.0f}")
