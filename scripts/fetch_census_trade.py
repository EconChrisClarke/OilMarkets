#!/usr/bin/env python3
"""Download US petroleum-product trade by state and by port from the Census
International Trade API (https://api.census.gov/data/timeseries/intltrade).

Pulls monthly values for HS 2709 (crude), 2710 (refined products), 2711
(petroleum gases / LPG) and 2713 (petcoke, bitumen) at the HS6 level, for:

  exports/statehs  - exports by state of origin of movement x destination country
  exports/porths   - exports by port of lading x destination country
  imports/statehs  - imports by state of destination x origin country
  imports/porths   - imports by port of unlading x origin country
  exports/hs, imports/hs - national HS10 detail with quantities (barrels), used
                     to split HS 271019 into diesel / jet / resid / other and
                     to convert dollars to barrels.

State and port data are published in dollars only, at HS6 at most, so barrels
and the diesel share must be estimated from the national HS10 detail.

Standard library only. Set CENSUS_API_KEY for higher rate limits (optional).

Usage:
  python3 scripts/fetch_census_trade.py --start 2019-01 --end 2025-12
"""

import argparse
import csv
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

BASE = "https://api.census.gov/data/timeseries/intltrade"
ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw" / "census_trade"
OUT = ROOT / "data" / "census_trade"

HS6 = [
    "270900",  # crude petroleum
    "271012", "271019", "271020", "271091", "271099",  # refined products
    "271111", "271112", "271113", "271114", "271119", "271121", "271129",  # gases
    "271311", "271312", "271320", "271390",  # petcoke, bitumen, residues
]

# Variables we would like; each request uses whichever of these the endpoint offers.
WANT = {
    "exports/statehs": ["STATE", "E_COMMODITY", "E_COMMODITY_SDESC", "CTY_CODE",
                        "CTY_NAME", "ALL_VAL_MO"],
    "exports/porths": ["PORT", "PORT_NAME", "E_COMMODITY", "E_COMMODITY_SDESC",
                       "CTY_CODE", "CTY_NAME", "ALL_VAL_MO", "VES_VAL_MO",
                       "VES_WGT_MO", "CNT_VAL_MO", "AIR_VAL_MO"],
    "imports/statehs": ["STATE", "I_COMMODITY", "I_COMMODITY_SDESC", "CTY_CODE",
                        "CTY_NAME", "GEN_VAL_MO", "CON_VAL_MO"],
    "imports/porths": ["PORT", "PORT_NAME", "I_COMMODITY", "I_COMMODITY_SDESC",
                       "CTY_CODE", "CTY_NAME", "GEN_VAL_MO", "CON_VAL_MO",
                       "VES_VAL_MO", "VES_WGT_MO", "CNT_VAL_MO"],
    "exports/hs": ["E_COMMODITY", "E_COMMODITY_LDESC", "CTY_CODE", "CTY_NAME",
                   "ALL_VAL_MO", "QTY_1_MO", "UNIT_QY1", "VES_WGT_MO"],
    "imports/hs": ["I_COMMODITY", "I_COMMODITY_LDESC", "CTY_CODE", "CTY_NAME",
                   "GEN_VAL_MO", "CON_VAL_MO", "GEN_QY1_MO", "CON_QY1_MO",
                   "UNIT_QY1", "VES_WGT_MO"],
}


def get(url, retries=4):
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(url, timeout=120) as r:
                if r.status == 204:
                    return None
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code in (204, 404):
                return None
            body = e.read().decode("utf-8", "replace")[:300]
            if e.code == 400:
                raise RuntimeError(f"400 for {url}: {body}")
            err = f"HTTP {e.code}: {body}"
        except (urllib.error.URLError, TimeoutError) as e:
            err = str(e)
        wait = 2 ** (attempt + 1)
        print(f"  retry in {wait}s ({err})", file=sys.stderr)
        time.sleep(wait)
    raise RuntimeError(f"failed after {retries} tries: {url}")


def available_vars(endpoint):
    data = get(f"{BASE}/{endpoint}/variables.json")
    return set(data["variables"]) if data else set()


def query(endpoint, fields, params):
    q = {"get": ",".join(fields), **params}
    key = os.environ.get("CENSUS_API_KEY")
    if key:
        q["key"] = key
    url = f"{BASE}/{endpoint}?{urllib.parse.urlencode(q, safe=',*+:')}"
    return get(url)


def year_ranges(start, end):
    y0, y1 = int(start[:4]), int(end[:4])
    for y in range(y0, y1 + 1):
        a = start if y == y0 else f"{y}-01"
        b = end if y == y1 else f"{y}-12"
        yield y, a, b


def fetch(endpoint, commodities, level, start, end):
    have = available_vars(endpoint)
    fields = [v for v in WANT[endpoint] if v in have]
    missing = [v for v in WANT[endpoint] if v not in have]
    if missing:
        print(f"{endpoint}: not offered, skipping {missing}")
    comm_var = "E_COMMODITY" if endpoint.startswith("exports") else "I_COMMODITY"
    tag = endpoint.replace("/", "_")
    rows, header = [], None
    for code in commodities:
        for year, a, b in year_ranges(start, end):
            cache = RAW / f"{tag}_{code.strip('*')}_{year}.json"
            if cache.exists():
                data = json.loads(cache.read_text())
            else:
                print(f"{endpoint} {code} {year}")
                data = query(endpoint, fields, {
                    "time": f"from {a} to {b}",
                    "COMM_LVL": level,
                    comm_var: code,
                })
                cache.write_text(json.dumps(data))
                time.sleep(0.5)
            if not data:
                continue
            header = header or data[0]
            rows.extend(data[1:])
    if header:
        OUT.mkdir(parents=True, exist_ok=True)
        path = OUT / f"{tag}.csv"
        with path.open("w", newline="") as f:
            w = csv.writer(f)
            w.writerow(header)
            w.writerows(rows)
        print(f"wrote {path.relative_to(ROOT)} ({len(rows):,} rows)")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--start", default="2019-01")
    ap.add_argument("--end", default="2025-12")
    ap.add_argument("--only", nargs="*", help="subset of endpoints to fetch")
    args = ap.parse_args()
    RAW.mkdir(parents=True, exist_ok=True)

    jobs = [
        ("exports/statehs", HS6, "HS6"),
        ("exports/porths", HS6, "HS6"),
        ("imports/statehs", HS6, "HS6"),
        ("imports/porths", HS6, "HS6"),
        # National HS10 detail for the 2710/2711 chapters (wildcard match).
        ("exports/hs", ["2710*", "2711*"], "HS10"),
        ("imports/hs", ["2710*", "2711*"], "HS10"),
    ]
    for endpoint, codes, level in jobs:
        if args.only and endpoint not in args.only:
            continue
        fetch(endpoint, codes, level, args.start, args.end)


if __name__ == "__main__":
    main()
