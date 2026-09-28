#!/usr/bin/env python3
"""Gulf diesel before and after the Iran war (from 28 February 2026), using
only official reported data, no estimates:

  Exporters' own reports   JODI Oil World Database, gas/diesel oil exports
                           (Saudi Arabia, Kuwait and Bahrain are the only Gulf
                           states that report them)
  Europe's customs data    Eurostat Comext CN8, EU27 imports of gas oil
                           (27101943/44/46/47/48) from all eight Gulf states
                           (fetch_eu_diesel_imports.py)
  Australia's statistics   Australian Petroleum Statistics, diesel imports
                           by source country, from the Gulf states

Windows: "before" = September 2025 to February 2026 (six months); "after" =
April to June 2026, the latest three months every source has. March 2026 is
left out: the war began on 28 February and cargoes already at sea were still
arriving.

Outputs:
  data/trade/gulf_diesel_war_summary.csv
  charts/gulf-diesel-war.json
"""

import csv
import json
import subprocess
import urllib.request
from calendar import monthrange
from collections import defaultdict
from pathlib import Path

import openpyxl  # pip install openpyxl

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
UA = {"User-Agent": "Mozilla/5.0"}
BEFORE = ["2025-09", "2025-10", "2025-11", "2025-12", "2026-01", "2026-02"]
AFTER = ["2026-04", "2026-05", "2026-06"]
GULF_ISO2 = ["SA", "AE", "KW", "BH", "OM", "QA", "IQ", "IR"]
GULF_NAMES = ["Saudi Arabia", "United Arab Emirates", "Kuwait", "Bahrain", "Oman", "Qatar", "Iraq",
              "Iran, Islamic Republic of", "Iran"]
JODI = "https://www.jodidata.org/_resources/files/downloads/oil-data/annual-csv/secondary/{}.csv"
APS = ("https://data.gov.au/data/dataset/d889484e-fb65-4190-a2e3-1739517cbf9b/resource/"
       "a5825135-47fa-4c59-a4e8-94e19511cb95/download/"
       "australian_petroleum_statistics_-_data_extract_june_2026.xlsx")


def fetch(url, path):
    RAW.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_bytes(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=300).read())
    return path


def mean(d, months):
    missing = [m for m in months if m not in d]
    if missing:
        raise SystemExit(f"missing months {missing}")
    return sum(d[m] for m in months) / len(months)


# ---- JODI: exporters' own reports, kb/d ------------------------------------
jodi = defaultdict(dict)
for name in ("2025", "secondaryyear2026"):
    for r in csv.DictReader(fetch(JODI.format(name), RAW / f"jodi_secondary_{name}.csv").open()):
        if (r["ENERGY_PRODUCT"] == "GASDIES" and r["FLOW_BREAKDOWN"] == "TOTEXPSB"
                and r["UNIT_MEASURE"] == "KBD" and r["REF_AREA"] in ("SA", "KW", "BH")
                and r["OBS_VALUE"] not in ("", "-")):
            jodi[r["REF_AREA"]][r["TIME_PERIOD"]] = float(r["OBS_VALUE"]) * 1000

# ---- Eurostat: EU27 imports of gas oil from the Gulf, b/d ------------------
eu = defaultdict(float)
eu_by = defaultdict(lambda: defaultdict(float))
for r in csv.DictReader((ROOT / "data" / "trade" / "eu_gasoil_imports_by_partner_monthly.csv").open()):
    if r["partner"] in GULF_ISO2:
        eu[r["month"]] += float(r["barrels_per_day"])
        eu_by[r["partner"]][r["month"]] += float(r["barrels_per_day"])

# ---- Australia: diesel imports from the Gulf, b/d (ML -> barrels) -----------
wb = openpyxl.load_workbook(fetch(APS, RAW / "australian_petroleum_statistics_june_2026.xlsx"), read_only=True)
rows = list(wb["Imports volume by country"].iter_rows(values_only=True))
col = rows[0].index("Diesel oil (ML)")
aus = defaultdict(float)
for r in rows[1:]:
    if r[0] and r[1] in GULF_NAMES:
        m = r[0].strftime("%Y-%m")
        aus[m] += (r[col] or 0) * 6289.81 / monthrange(r[0].year, r[0].month)[1]   # ML -> bbl/day
for m in BEFORE + AFTER:                      # a month with no Gulf row is a measured zero
    aus.setdefault(m, 0.0)

series = [("Saudi Arabia", "Gulf exporters report", jodi["SA"]),
          ("Kuwait", "Gulf exporters report", jodi["KW"]),
          ("Bahrain", "Gulf exporters report", jodi["BH"]),
          ("EU27", "Importers report, from all Gulf states", eu),
          ("Australia", "Importers report, from all Gulf states", aus)]
summary = [(n, g, mean(d, BEFORE), mean(d, AFTER)) for n, g, d in series]

out = ROOT / "data" / "trade" / "gulf_diesel_war_summary.csv"
with out.open("w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["country", "measure", "before_sep2025_feb2026_bpd", "after_apr_jun2026_bpd", "change_pct"])
    for n, g, b, a in summary:
        w.writerow([n, g, round(b), round(a), round((a / b - 1) * 100) if b else ""])
print(f"wrote {out.relative_to(ROOT)}")
for n, g, b, a in summary:
    print(f"  {n:13s} {b/1000:7.1f} -> {a/1000:7.1f} k b/d  ({(a/b-1)*100 if b else 0:+.0f}%)")
print("  EU27 by Gulf supplier:", {p: (round(mean(d, BEFORE) / 1000, 1), round(mean(d, AFTER) / 1000, 1))
                                  for p, d in eu_by.items()})

# ---- chart config --------------------------------------------------------
names = [n for n, _, _, _ in summary]
icons = json.loads(subprocess.run(["node", str(ROOT / "chartkit" / "scripts" / "country_icons.js"), *names],
                                  capture_output=True, text=True, check=True).stdout)
cfg = {
    "type": "column",
    "headline": "Gulf diesel exports fell after the war began, and Europe and Australia received less",
    "subhead": "Diesel and gas oil, thousand barrels per day, average of Sep 2025–Feb 2026 vs Apr–Jun 2026",
    "note": ("Official reported data only. Saudi Arabia, Kuwait and Bahrain are the only Gulf states that report "
             "diesel exports. EU27 and Australia count imports from all eight Gulf states "
             "(incl. UAE, Qatar, Oman, Iraq and Iran). March 2026 is left out: the war began on 28 February."),
    "source": ("JODI Oil World Database (gas/diesel oil exports); Eurostat Comext, CN 27101943/44/46/47/48; "
               "Australian Petroleum Statistics (diesel imports by country)"),
    "sourceUrl": "https://www.jodidata.org/oil/database/data-downloads.aspx",
    "xType": "category",
    "categories": names,
    "format": {"decimals": 0},
    "series": [
        {"name": "Before the war (Sep 2025–Feb 2026)", "color": "#C4B5B8",
         "data": [round(b / 1000) for _, _, b, _ in summary]},
        {"name": "After (Apr–Jun 2026)", "color": "#C71E1D",
         "data": [round(a / 1000) for _, _, _, a in summary]},
    ],
    "categoryIcons": icons,
    "categoryGroups": [{"label": "Gulf exporters report", "from": 0, "to": 2},
                       {"label": "Importers report", "from": 3, "to": 4}],
    "changeLabels": True,
}
out = ROOT / "charts" / "gulf-diesel-war.json"
out.write_text(json.dumps(cfg, indent=2) + "\n")
print(f"wrote {out.relative_to(ROOT)}")
