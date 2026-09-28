#!/usr/bin/env python3
"""EU27 imports of gas oil (diesel) by supplier country, monthly, from
Eurostat Comext bulk files at CN8 detail.

The Comext API only serves CN8 detail through 2024, and its HS6 code 271019
mixes diesel with jet fuel and fuel oil. The monthly bulk files ("full_v2")
carry every CN8 line, so they are downloaded one month at a time, filtered to
the gas-oil codes, and deleted.

CN8 codes kept (flow 1 = imports into each EU member state; extra-EU partners):
  27101943  gas oils, sulfur <= 0.001% (road diesel, ULSD)
  27101946  gas oils, sulfur > 0.001% and <= 0.002%
  27101947  gas oils, sulfur > 0.002% and <= 0.1%
  27101948  gas oils, sulfur > 0.1%
Barrels use 7.46 bbl per tonne, the standard conversion for gas oil.

Output: data/trade/eu_gasoil_imports_by_partner_monthly.csv
  month, partner, cn8, tonnes, barrels_per_day
"""

import csv
import io
import sys
import urllib.request
from calendar import monthrange
from collections import defaultdict
from pathlib import Path

import py7zr  # pip install py7zr

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw" / "comext"          # git-ignored
OUT = ROOT / "data" / "trade" / "eu_gasoil_imports_by_partner_monthly.csv"
URL = ("https://ec.europa.eu/eurostat/api/dissemination/files/"
       "?file=comext%2FCOMEXT_DATA%2FPRODUCTS%2Ffull_v2_{}.7z")
CODES = {"27101943", "27101946", "27101947", "27101948"}
BBL_PER_T = 7.46
MONTHS = sys.argv[1:] or [f"{y}{m:02d}" for y, m in
                          [(2025, m) for m in range(1, 13)] + [(2026, m) for m in range(1, 8)]]

agg = defaultdict(float)                       # (month, partner, cn8) -> kg
RAW.mkdir(parents=True, exist_ok=True)
for mo in MONTHS:
    arc = RAW / f"full_v2_{mo}.7z"
    req = urllib.request.Request(URL.format(mo), headers={"User-Agent": "Mozilla/5.0"})
    arc.write_bytes(urllib.request.urlopen(req, timeout=600).read())
    with py7zr.SevenZipFile(arc) as z:
        z.extractall(RAW)
    arc.unlink()
    dat = RAW / f"full_{mo}.dat"
    n = 0
    with dat.open(newline="") as f:
        for r in csv.DictReader(f):
            if r["PRODUCT_NC"] in CODES and r["FLOW"] == "1" and r["QUANTITY_KG"]:
                agg[(mo, r["PARTNER"], r["PRODUCT_NC"])] += float(r["QUANTITY_KG"]); n += 1
    dat.unlink()
    print(f"{mo}: {n} gas-oil import lines", flush=True)

rows = []
for (mo, p, c), kg in agg.items():
    days = monthrange(int(mo[:4]), int(mo[4:]))[1]
    rows.append([f"{mo[:4]}-{mo[4:]}", p, c, round(kg / 1000), round(kg / 1000 * BBL_PER_T / days)])
OUT.parent.mkdir(parents=True, exist_ok=True)
old = []
if OUT.exists() and sys.argv[1:]:              # partial refresh: keep other months
    done = {f"{m[:4]}-{m[4:]}" for m in MONTHS}
    old = [r for r in csv.reader(OUT.open()) if r and r[0] != "month" and r[0] not in done]
with OUT.open("w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["month", "partner", "cn8", "tonnes", "barrels_per_day"])
    w.writerows(sorted(old + rows))
print(f"wrote {OUT.relative_to(ROOT)} ({len(old) + len(rows)} rows)")
