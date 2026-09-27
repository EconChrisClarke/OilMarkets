#!/usr/bin/env python3
"""Collect 2024 US distillate fuel oil trade from the Census International
Trade API, for the diesel-export-ban maps.

Distillate = the "light fuel oil" lines of HS 2710.19 (25 deg API or more),
by sulfur grade, plus diesel blends containing biodiesel (2710.20):

  2710191106  <=15 ppm sulfur (ultra-low-sulfur diesel)
  2710191109  15-500 ppm
  2710191112  >500 ppm (Saybolt viscosity <45 s)
  2710200000  containing biodiesel

Jet fuel (2710191600), residual/heavy fuel oils and lubricants are excluded.

Outputs, all calendar-2024 annual totals, in data/census_trade/:

  distillate_exports_district_country_2024.csv  measured barrels (QTY_1)
  distillate_imports_district_country_2024.csv  measured barrels (GEN_QY1)
  hs271019_exports_port_2024.csv                 port x country, dollars and
      vessel shipping weight only -- the API has no HS10 or barrels by port,
      so ports are used only to apportion district barrels
  hs271019_exports_state_2024.csv                state of origin x country, dollars

Reads CENSUS_API_KEY from the environment or from ./.env.
"""

import csv
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "census_trade"
BASE = "https://api.census.gov/data/timeseries/intltrade"
TIME = "2024-12"          # *_YR variables in December = calendar-year total

EXPORT_CODES = ["2710191106", "2710191109", "2710191112", "2710200000"]

# Import (HTS) lines are finer than export (Schedule B) lines. Same definition:
# No. 2 and 3 fuel oils and light fuel oils at 25 deg API or more, every sulfur
# grade, diesel or not, plus diesel blended with biodiesel. No. 4 fuel oils,
# heavy fuel oils, kerosene and lubricants are left out, as on the export side.
IMPORT_CODES = ["2710191102", "2710191103", "2710191104", "2710191105", "2710191107",
                "2710191108", "2710191111", "2710191113", "2710191114",
                "2710201002", "2710201003", "2710201004", "2710201005", "2710201006",
                "2710201007", "2710201008"]


def api_key():
    if os.environ.get("CENSUS_API_KEY"):
        return os.environ["CENSUS_API_KEY"]
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            if line.startswith("CENSUS_API_KEY="):
                return line.split("=", 1)[1].strip()
    sys.exit("CENSUS_API_KEY not set (environment or .env)")


class NoRedirect(urllib.request.HTTPRedirectHandler):
    # A missing or inactive key redirects to an HTML page; fail loudly instead.
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise RuntimeError(f"Census API redirected to {newurl} (check CENSUS_API_KEY)")


OPENER = urllib.request.build_opener(NoRedirect)


def query(endpoint, fields, **params):
    q = {"get": ",".join(fields), "time": TIME, "key": api_key(), **params}
    url = f"{BASE}/{endpoint}?{urllib.parse.urlencode(q, safe=',*')}"
    for attempt in range(4):
        try:
            with OPENER.open(url, timeout=180) as r:
                body = r.read().decode("utf-8")
                return json.loads(body) if body.strip() else []
        except urllib.error.HTTPError as e:
            if e.code == 204:
                return []
            if e.code == 400:
                raise RuntimeError(f"400: {e.read().decode()[:300]}")
            err = f"HTTP {e.code}"
        except (urllib.error.URLError, TimeoutError) as e:
            err = str(e)
        time.sleep(2 ** (attempt + 1))
        print(f"  retry ({err})", file=sys.stderr)
    raise RuntimeError(f"failed: {endpoint} {params}")


def write(name, rows):
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / name
    with path.open("w", newline="") as f:
        csv.writer(f).writerows(rows)
    print(f"wrote {path.relative_to(ROOT)} ({len(rows) - 1:,} rows)")


def dedupe_cols(data):
    """The API echoes predicate columns (time, COMM_LVL, commodity) at the end,
    sometimes twice. Keep the first occurrence of each column name."""
    head = data[0]
    keep = [i for i, h in enumerate(head) if h not in head[:i]]
    return [[r[i] for i in keep] for r in data]


def main():
    # 1. Exports: district x country x HS10, measured barrels.
    rows = None
    for code in EXPORT_CODES:
        d = query("exports/hs", ["DISTRICT", "DIST_NAME", "CTY_CODE", "CTY_NAME",
                                 "SUMMARY_LVL", "E_COMMODITY_SDESC", "QTY_1_YR",
                                 "UNIT_QY1", "ALL_VAL_YR", "VES_VAL_YR", "VES_WGT_YR"],
                  COMM_LVL="HS10", E_COMMODITY=code)
        d = dedupe_cols(d)
        rows = rows or [d[0]]
        rows += d[1:]
    write("distillate_exports_district_country_2024.csv", rows)

    # 2. Imports: list the HTS10 lines under 2710 for the record, then pull
    #    the distillate ones.
    d = dedupe_cols(query("imports/hs", ["I_COMMODITY", "I_COMMODITY_LDESC", "GEN_QY1_YR", "UNIT_QY1"],
                          COMM_LVL="HS10", I_COMMODITY="2710*"))
    codes = [c for c in IMPORT_CODES if any(r[0] == c for r in d[1:])]
    write("distillate_import_codes_2024.csv",
          [["I_COMMODITY", "I_COMMODITY_LDESC", "GEN_QY1_YR", "UNIT_QY1", "included"]] +
          [r[:4] + [r[0] in codes] for r in d[1:] if r[0].startswith(("271019", "271020"))])
    rows = None
    for code in codes:
        d = dedupe_cols(query("imports/hs", ["DISTRICT", "DIST_NAME", "CTY_CODE", "CTY_NAME",
                                            "SUMMARY_LVL", "I_COMMODITY_SDESC", "GEN_QY1_YR",
                                            "UNIT_QY1", "GEN_VAL_YR"],
                              COMM_LVL="HS10", I_COMMODITY=code))
        if not d:
            continue
        rows = rows or [d[0]]
        rows += d[1:]
    write("distillate_imports_district_country_2024.csv", rows)

    # 3. Ports: HS6 271019, dollars and vessel weight only.
    d = dedupe_cols(query("exports/porths", ["PORT", "PORT_NAME", "CTY_CODE", "CTY_NAME",
                                             "SUMMARY_LVL", "ALL_VAL_YR", "VES_VAL_YR", "VES_WGT_YR"],
                          COMM_LVL="HS6", E_COMMODITY="271019"))
    write("hs271019_exports_port_2024.csv", d)

    # 4. State of origin: HS6 271019, dollars.
    d = dedupe_cols(query("exports/statehs", ["STATE", "CTY_CODE", "CTY_NAME", "SUMMARY_LVL",
                                              "ALL_VAL_YR", "VES_VAL_YR"],
                          COMM_LVL="HS6", E_COMMODITY="271019"))
    write("hs271019_exports_state_2024.csv", d)


if __name__ == "__main__":
    main()
