#!/usr/bin/env python3
"""US diesel by region (PADD), 2024: what each region refines and uses, what it
ships to and receives from the other regions, and what it imports and exports.

Inputs (fetched from EIA):
  Supply and disposition by PADD, distillate fuel oil, annual, kb/d
      pet_sum_snd_a_epd0_mbblpd_a_cur-{n}.htm   (n = years before the latest)
  Movements between PADDs by pipeline, tanker, barge and rail, distillate,
      annual, thousand barrels      pet_move_ptb_a_EPD0_TNR_mbbl_a.htm
Outputs:
  data/eia/distillate_padd_balance_2024.csv
  data/eia/distillate_padd_movements_2024.csv
  maps/configs/padd-diesel-2024.json

Region-to-region flows are gross (each direction separately); the balance's
"net receipts" equal receipts minus shipments. Imports are counted in the
region where they entered the country.
"""

import csv
import html
import json
import re
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
YEAR, DAYS = 2024, 366
UA = {"User-Agent": "Mozilla/5.0"}
BAL = "https://www.eia.gov/dnav/pet/pet_sum_snd_a_epd0_mbblpd_a_cur{}.htm"
MOV = "https://www.eia.gov/dnav/pet/pet_move_ptb_a_EPD0_TNR_mbbl_a.htm"
PADD = {"PADD 1": "p1", "PADD 2": "p2", "PADD 3": "p3", "PADD 4": "p4", "PADD 5": "p5"}


def text(url):
    s = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120).read().decode("latin-1")
    return html.unescape(re.sub(r"(\s*\|\s*)+", " | ", re.sub(r"<[^>]+>", " | ", s)))


num = lambda c: float(c.replace(",", "")) if re.fullmatch(r"-?[\d,.]+", c.strip()) else 0.0

# ---- balance: EIA serves one year per page, newest as "_cur", then "_cur-1"...
def raw(url):
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120).read().decode("latin-1")


for back in range(6):
    url = BAL.format("" if back == 0 else f"-{back}")
    if re.search(rf"SELECTED>\s*Annual {YEAR}\b", raw(url)):
        t = text(url)
        break
else:
    raise SystemExit(f"no EIA balance page for {YEAR}")
bal = {}
for area, key in PADD.items():
    m = re.search(rf"\| {area} \|((?: [^|]* \|){{8}})", t)
    cells = [c.strip() for c in m.group(1).split("|")[:8]]
    # biofuels, refinery & blender production, imports, net receipts, adjustments,
    # stock change, exports, products supplied
    bal[key] = dict(zip(["bio", "refined", "imports", "net_receipts", "adj", "stock", "exports", "supplied"],
                        [num(c) * 1000 for c in cells]))

# ---- gross movements between regions -------------------------------------
t = text(MOV)
yrs = [int(y) for y in re.search(r"((?:\| \d{4} ){6})\|", t).group(1).split("|")[1:] if y.strip()]
col = yrs.index(YEAR)
mov = {}
for blk in re.finditer(r"From (PADD \d) to \|(.*?)(?=From PADD \d to|\| - \| = No Data)", t, re.S):
    src = PADD[blk.group(1)]
    for m in re.finditer(r"\| (PADD \d) \|((?: [^|]* \|){6})", blk.group(2)):
        v = num(m.group(2).split("|")[col]) * 1000 / DAYS
        if v > 0:
            mov[(src, PADD[m.group(1)])] = v

# check: receipts minus shipments reproduces the balance's net receipts
for k in PADD.values():
    net = sum(v for (a, b), v in mov.items() if b == k) - sum(v for (a, b), v in mov.items() if a == k)
    assert abs(net - bal[k]["net_receipts"]) < 5000, (k, net, bal[k]["net_receipts"])

d = ROOT / "data" / "eia"
d.mkdir(parents=True, exist_ok=True)
with (d / f"distillate_padd_balance_{YEAR}.csv").open("w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["region", "refined_bpd", "imports_bpd", "net_receipts_bpd", "stock_change_bpd",
                "exports_bpd", "consumed_bpd"])
    for area, k in PADD.items():
        b = bal[k]
        w.writerow([area, round(b["refined"]), round(b["imports"]), round(b["net_receipts"]),
                    round(b["stock"]), round(b["exports"]), round(b["supplied"])])
with (d / f"distillate_padd_movements_{YEAR}.csv").open("w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["from", "to", "barrels_per_day"])
    inv = {v: k for k, v in PADD.items()}
    for (a, b), v in sorted(mov.items(), key=lambda x: -x[1]):
        w.writerow([inv[a], inv[b], round(v)])
print("balance (k b/d):", {k: {kk: round(v / 1000) for kk, v in b.items() if kk in
                                ("refined", "imports", "exports", "supplied")} for k, b in bal.items()})
print("movements (k b/d):", {f"{a}>{b}": round(v / 1000) for (a, b), v in mov.items()})

# ---- map config -----------------------------------------------------------
NAVY, TEAL, RED = "#1B3A5C", "#2E8B7A", "#C71E1D"
M = lambda v: f"{v/1e6:.1f}M" if v >= 995000 else f"{v/1e3:.0f}k"
# no dots: each region's name and bars sit on its own area, and the arrows
# stop around that block ("hub"), aimed at it, instead of meeting at a point
REGION = {"p1": ("East Coast", [-78.5, 37.8]), "p2": ("Midwest", [-91.0, 41.8]),
          "p3": ("Gulf Coast", [-97.0, 31.3]), "p4": ("Rockies", [-109.0, 44.0]),
          "p5": ("West Coast", [-119.8, 38.2])}
nodes = {k: {"label": n, "lonlat": ll, "hub": True,
             "sub": ""}   # refined and consumed are on the bars beside the name
         for k, (n, ll) in REGION.items()}


# PADD membership (EIA definitions); pale fills for the areas, darker shades
# of the same hues for each region's label and refining bar
PADD_STATES = {
    "p1": ["Connecticut", "Maine", "Massachusetts", "New Hampshire", "Rhode Island", "Vermont",
           "Delaware", "District of Columbia", "Maryland", "New Jersey", "New York", "Pennsylvania",
           "Florida", "Georgia", "North Carolina", "South Carolina", "Virginia", "West Virginia"],
    "p2": ["Illinois", "Indiana", "Iowa", "Kansas", "Kentucky", "Michigan", "Minnesota", "Missouri",
           "Nebraska", "North Dakota", "South Dakota", "Ohio", "Oklahoma", "Tennessee", "Wisconsin"],
    "p3": ["Alabama", "Arkansas", "Louisiana", "Mississippi", "New Mexico", "Texas"],
    "p4": ["Colorado", "Idaho", "Montana", "Utah", "Wyoming"],
    "p5": ["Arizona", "California", "Nevada", "Oregon", "Washington"],   # + Alaska, Hawaii (off map)
}
FILL = {"p1": "#D9E2EE", "p2": "#D5E8E0", "p3": "#F2E0C4", "p4": "#E3DBEC", "p5": "#F3D5D3"}
DARK = {"p1": "#3F5F86", "p2": "#2F7560", "p3": "#A8711E", "p4": "#6C5A94", "p5": "#B0443F"}
BG = "#FFF1F2"


def mix(a, b, t):
    """a blended toward b by t (0..1), as #rrggbb"""
    ca = [int(a[i:i + 2], 16) for i in (1, 3, 5)]
    cb = [int(b[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(x + (y - x) * t):02X}" for x, y in zip(ca, cb))


# two skinny bars beside each region's name: refined (dark) and consumed (light)
for k in REGION:
    nodes[k].update({"textColor": DARK[k], "labelBars": [
        {"value": round(bal[k]["refined"], -3), "color": DARK[k]},
        {"value": round(bal[k]["supplied"], -3), "color": mix(DARK[k], BG, 0.5), "textColor": DARK[k]}]})
# where each region's foreign trade goes to or comes from, placed off the coast or border
EXP_AT = {"p1": [-66, 34], "p3": [-89, 23.5], "p5": [-124.5, 30.0]}
# where each region's imports come from: the East Coast's off the Atlantic, the
# other three just across the Canadian border, so their small arrows come in short
IMP_AT = {"p1": [-64.5, 45.5], "p2": [-91.0, 51.5], "p4": [-110.0, 51.5], "p5": [-123.5, 50.8]}
IMP_MIN = 5000
flows = [{"from": a, "to": b, "value": round(v, -3), "color": NAVY} for (a, b), v in mov.items() if v >= 5000]
MIN = 5000
for k, at in EXP_AT.items():
    v = bal[k]["exports"]
    if v >= MIN:
        nodes[f"x{k}"] = {"label": "Exports", "sub": M(v), "textColor": RED, "lonlat": at}
        flows.append({"from": k, "to": f"x{k}", "value": round(v, -3), "color": RED})
for k, at in IMP_AT.items():
    v = bal[k]["imports"]
    if v >= IMP_MIN:
        nodes[f"m{k}"] = {"label": "Imports", "sub": M(v), "textColor": TEAL, "lonlat": at, "dot": False}
        flows.append({"from": f"m{k}", "to": k, "value": round(v, -3), "color": TEAL})
shown_dom = sum(f["value"] for f in flows if f["color"] == NAVY)
us_ref = sum(b["refined"] for b in bal.values())
us_use = sum(b["supplied"] for b in bal.values())
us_exp = sum(b["exports"] for b in bal.values())
all_dom = sum(mov.values())
cfg = {
    "headline": "Most regions refine their own diesel; the East Coast relies on the Gulf Coast",
    "subhead": f"Distillate fuel oil by region (PADD), {YEAR}, barrels per day: domestic shipments, imports and exports",
    "note": (f"US totals: refined {us_ref/1e6:.2f}M b/d, consumed {us_use/1e6:.2f}M, exported {us_exp/1e6:.2f}M. "
             "Imports are counted where they enter the country. Region-to-region arrows are gross shipments "
             f"by pipeline, tanker, barge and rail; flows under {MIN//1000}k b/d are not drawn."),
    "source": "EIA, Supply and Disposition by PAD District; Movements by Pipeline, Tanker, Barge and Rail between PAD Districts",
    "sourceUrl": "https://www.eia.gov/dnav/pet/pet_move_ptb_a_EPD0_TNR_mbbl_a.htm",
    "units": "b/d",
    "style": "flows",
    "arrowStyle": "swoosh",
    "hubPad": 8,           # arrows stop this far from a region's name and bars
    "keyCompact": True,
    "maxArrowWidth": 40,
    "legendTitle": "Arrow width",
    "legend": [100000, 500000],
    "colorKey": False,
    "geoBBox": [-170, -25, -20, 75],
    "regions": {k: {"color": FILL[k], "states": PADD_STATES[k]} for k in PADD_STATES},
    # bars beside each region's name: 3M b/d would stand 60 design units tall
    "labelBars": {"max": 3000000, "height": 80, "width": 10, "gap": 1, "pad": 4, "values": False,
                  "legend": 1000000,
                  "legendLabel": "1M b/d",
                  "keys": [{"label": "dark: refined", "color": "#5B6470"},
                           {"label": "light: used", "color": "#B5BAC2"}]},
    "nodes": nodes,
    "flows": flows,
    "frames": {
        "substack": {"bounds": [[-128, 22], [-62, 52]]},
        # shorter bars in the smaller frames, same scale within each frame
        "vertical": {"bounds": [[-127, 22], [-63, 52]], "shortLabels": True, "labelBarsHeight": 55,
                     # narrower map: East Coast block onto the coast, clear of the
                     # Midwest; West Coast block south, so the Rockies arrow shows
                     # exports pointed further offshore, so the arrows keep some length
                     "nodes": {"p1": {"lonlat": [-76.8, 36.4]}, "p5": {"lonlat": [-119.5, 36.6]},
                               "xp1": {"lonlat": [-68.5, 30.5]}, "xp5": {"lonlat": [-123.0, 28.0]}}},
        "square": {"bounds": [[-127, 22], [-63, 52]], "labelBarsHeight": 60,
                   # West Coast exports out to sea, above the key
                   "nodes": {"xp5": {"lonlat": [-127.0, 33.5], "sides": ["below", "above"]}}},
    },
}
out = ROOT / "maps" / "configs" / f"padd-diesel-{YEAR}.json"
out.write_text(json.dumps(cfg, indent=2) + "\n")
print(f"wrote {out.relative_to(ROOT)} ({len(flows)} flows; domestic drawn {shown_dom/all_dom:.0%})")
