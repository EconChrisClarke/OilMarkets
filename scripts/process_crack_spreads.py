#!/usr/bin/env python3
"""Diesel and gasoline refining margins over crude, US Gulf Coast, monthly.

Margin = product spot price x 42 gallons - Brent, in dollars per barrel: the
simple "crack spread", what a barrel of each product fetches over the crude
it is made from. Gulf Coast prices, because the Gulf is where US prices are
set (it is the export hub); Brent, because it is the world crude benchmark
that Gulf refiners pay for imported crude and get for exported crude.

Inputs (fetched): EIA spot price history, monthly averages of daily closes
  RBRTE                      Brent spot, $/bbl
  EER_EPD2DXL0_PF4_RGC_DPG   Gulf Coast ultra-low-sulfur No. 2 diesel, $/gal (from Jun 2006)
  EER_EPMRU_PF4_RGC_DPG      Gulf Coast conventional regular gasoline, $/gal
Outputs:
  data/eia/gulf_crack_spreads_monthly.csv
  charts/diesel-gasoline-margins.json
"""

import csv
import json
import urllib.request
from pathlib import Path

import xlrd  # pip install xlrd (EIA history files are .xls)

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"            # git-ignored
URL = "https://www.eia.gov/dnav/pet/hist_xls/{}m.xls"
SERIES = {"brent": "RBRTE", "diesel": "EER_EPD2DXL0_PF4_RGC_DPG", "gasoline": "EER_EPMRU_PF4_RGC_DPG"}


def monthly(key):
    """{'YYYY-MM': value} from an EIA monthly history workbook."""
    RAW.mkdir(parents=True, exist_ok=True)
    path = RAW / f"{key}m.xls"
    req = urllib.request.Request(URL.format(key), headers={"User-Agent": "Mozilla/5.0"})
    path.write_bytes(urllib.request.urlopen(req, timeout=120).read())
    sh = xlrd.open_workbook(path).sheet_by_name("Data 1")
    out = {}
    for i in range(3, sh.nrows):
        d, v = sh.row_values(i)[:2]
        if v == "":
            continue
        y, m = xlrd.xldate_as_tuple(d, 0)[:2]
        out[f"{y}-{m:02d}"] = float(v)
    return out


p = {k: monthly(s) for k, s in SERIES.items()}
months = sorted(set(p["brent"]) & set(p["diesel"]) & set(p["gasoline"]))
rows = []
for mo in months:
    b = p["brent"][mo]
    rows.append([mo, round(b, 2), p["diesel"][mo], p["gasoline"][mo],
                 round(p["diesel"][mo] * 42 - b, 2), round(p["gasoline"][mo] * 42 - b, 2)])

out = ROOT / "data" / "eia" / "gulf_crack_spreads_monthly.csv"
out.parent.mkdir(parents=True, exist_ok=True)
with out.open("w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["month", "brent_usd_bbl", "gulf_ulsd_usd_gal", "gulf_gasoline_usd_gal",
                "diesel_margin_usd_bbl", "gasoline_margin_usd_bbl"])
    w.writerows(rows)
print(f"wrote {out.relative_to(ROOT)} ({len(rows)} months, {months[0]} to {months[-1]})")

dm = {r[0]: r[4] for r in rows}
gm = {r[0]: r[5] for r in rows}
pre = [dm[m] for m in months if "2010" <= m < "2020"]
gpre = [gm[m] for m in months if "2010" <= m < "2020"]
peak22 = max((m for m in months if m.startswith("2022")), key=dm.get)
peak26 = max((m for m in months if m >= "2026"), key=dm.get)
last = months[-1]
print(f"2010-19 average: diesel {sum(pre)/len(pre):.0f}, gasoline {sum(gpre)/len(gpre):.0f} $/bbl")
print(f"2022 peak {peak22}: diesel {dm[peak22]:.0f}; 2026 peak {peak26}: diesel {dm[peak26]:.0f}")
print(f"latest {last}: diesel {dm[last]:.0f}, gasoline {gm[last]:.0f}")

date = lambda m: m + "-15"
cfg = {
    "type": "line",
    "headline": "Diesel's margin over crude hit a record in 2026, pulling far ahead of gasoline's",
    "subhead": "Refining margin over Brent crude, US Gulf Coast spot prices, dollars per barrel, monthly",
    "note": ("Margin is the product's spot price per barrel minus the Brent spot price. "
             f"Diesel is ultra-low-sulfur No. 2; gasoline is conventional regular. "
             f"2010-19 averages: diesel ${sum(pre)/len(pre):.0f}, gasoline ${sum(gpre)/len(gpre):.0f}."),
    "source": "EIA, Spot Prices (Brent; US Gulf Coast ULSD and conventional gasoline)",
    "sourceUrl": "https://www.eia.gov/dnav/pet/pet_pri_spt_s1_m.htm",
    "handle": "@EconChrisClarke",
    "xType": "date",
    "format": {"prefix": "$", "decimals": 0},
    "rules": [{"axis": "y", "at": 0}],
    "series": [
        {"name": "Diesel", "color": "#C71E1D", "data": [[date(m), dm[m]] for m in months]},
        {"name": "Gasoline", "color": "#1B3A5C", "data": [[date(m), gm[m]] for m in months]},
    ],
    "annotations": [
        {"x": date(peak22), "y": dm[peak22], "text": "2022: Russia's war", "dx": -20, "dy": -6},
        {"x": date(peak26), "y": dm[peak26], "text": "2026: Iran war", "dx": -60, "dy": -10},
    ],
}
out = ROOT / "charts" / "diesel-gasoline-margins.json"
out.write_text(json.dumps(cfg, indent=2) + "\n")
print(f"wrote {out.relative_to(ROOT)}")
