#!/usr/bin/env python3
"""How full the main pipelines run, and the winter peak on the Gulf-to-East
Coast route.

1. Utilization, 2024-2025 average (charts/pipeline-utilization.json):
   barrels delivered out of each pipeline company's system (FERC Form No. 6,
   page 600, annual; via Catalyst Cooperative's PUDL build of the FERC XBRL
   filings) divided by the line's capacity from data/pipelines/pipeline_capacity.csv.
   Only companies whose FERC report is essentially one trunk line are used;
   for networks (Magellan, Buckeye, TEPPCO) system deliveries and line
   capacity are not comparable. Deliveries include barrels dropped off along
   the way and on laterals, so a line that runs full can report a little
   over 100%.

2. Monthly shipments (charts/pipeline-east-coast-monthly.json): EIA monthly
   movements by pipeline from the Gulf Coast (PADD 3) to the East Coast
   (PADD 1), by product. These count barrels crossing into the East Coast, so
   they are not a share of capacity (Colonial and Products SE also deliver in
   Mississippi, Alabama and Tennessee before the border).

Outputs:
  data/pipelines/pipeline_utilization_2024_2025.csv
  data/pipelines/gulf_to_east_coast_pipeline_monthly.csv
  charts/pipeline-utilization.json
  charts/pipeline-east-coast-monthly.json
"""

import calendar
import csv
import json
import sqlite3
import urllib.request
import zipfile
from pathlib import Path

import xlrd  # pip install xlrd

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
UA = {"User-Agent": "Mozilla/5.0"}
FERC6 = "https://s3.us-west-2.amazonaws.com/pudl.catalyst.coop/stable/ferc6_xbrl.sqlite.zip"
YEARS = ("2024", "2025")

# FERC respondent -> (label on the chart, row name in pipeline_capacity.csv, layer)
LINES = {
    "C000281": ("Colonial (Houston to Greensboro)", "Colonial Pipeline, Houston to Greensboro (Lines 1 and 2)", "Refined products"),
    "C001970": ("Explorer (Gulf to Midwest)", "Explorer Pipeline (Houston to Tulsa and Wood River)", "Refined products"),
    "C000630": ("Products SE (Gulf to Southeast)", "Products SE Pipeline (formerly Plantation)", "Refined products"),
    "C002778": ("UNEV (Salt Lake City to Las Vegas)", "UNEV Pipeline", "Refined products"),
    "C000774": ("Seaway (Cushing to Houston)", "Seaway Pipeline", "Crude oil"),
    "C000840": ("Express (Alberta to Wyoming)", "Express Pipeline", "Crude oil"),
    "C007618": ("Dakota Access (Bakken to Illinois)", "Dakota Access Pipeline", "Crude oil"),
}


def fetch(url, path):
    RAW.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_bytes(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=600).read())
    return path


# ---- 1. utilization from FERC Form 6 -----------------------------------------
db_path = RAW / "ferc6_xbrl.sqlite"
if not db_path.exists():
    with zipfile.ZipFile(fetch(FERC6, RAW / "ferc6_xbrl.sqlite.zip")) as z:
        z.extractall(RAW)
db = sqlite3.connect(db_path)
cap = {r["name"]: r for r in csv.DictReader((ROOT / "data" / "pipelines" / "pipeline_capacity.csv").open())}

latest = {}      # (entity, year) -> (publication time, barrels delivered): the latest filing wins
for e, s, en, pub, out in db.execute(
        "select entity_id, start_date, end_date, publication_time, number_of_barrels_delivered_out "
        "from statistics_of_operations_totals_600_duration where products_and_services_axis = 'total'"):
    if e in LINES and s[5:] == "01-01" and en[5:] == "12-31" and s[:4] in YEARS and out:
        if (e, s[:4]) not in latest or pub > latest[(e, s[:4])][0]:
            latest[(e, s[:4])] = (pub, out)

rows = []
for e, (label, capname, layer) in LINES.items():
    c = int(cap[capname]["capacity_bpd"])
    bpd = {y: latest[(e, y)][1] / (366 if calendar.isleap(int(y)) else 365) for y in YEARS}
    avg = sum(bpd.values()) / len(bpd)
    rows.append({"pipeline": label, "layer": layer, "capacity_bpd": c,
                 "delivered_2024_bpd": round(bpd["2024"]), "delivered_2025_bpd": round(bpd["2025"]),
                 "average_bpd": round(avg), "utilization_pct": round(avg / c * 100, 1)})
rows.sort(key=lambda r: -r["utilization_pct"])
out = ROOT / "data" / "pipelines" / "pipeline_utilization_2024_2025.csv"
with out.open("w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0]))
    w.writeheader()
    w.writerows(rows)
print(f"wrote {out.relative_to(ROOT)}")
for r in rows:
    print(f"  {r['pipeline']:38s} {r['average_bpd']/1000:6.0f}k of {r['capacity_bpd']/1000:5.0f}k  {r['utilization_pct']:5.1f}%")

RED, NAVY = "#C71E1D", "#1B3A5C"
util = {
    "type": "bar",
    "headline": "Colonial, the main fuel line from the Gulf to the East Coast, runs full",
    "subhead": "Barrels delivered as a share of capacity, 2024-2025 average, %",
    "note": ("Deliveries are each pipeline company's reported barrels delivered, all products; they include barrels "
             "dropped off along the way and on branch lines, so a line that runs full can show slightly over 100%. "
             "Capacity: company filings and EIA. Pipelines whose report covers a whole network (e.g. Magellan, "
             "Buckeye) are left out."),
    "source": "FERC Form No. 6, annual reports of oil pipeline companies (via Catalyst Cooperative PUDL); capacity: EIA, company 10-K filings",
    "sourceUrl": "https://data.catalyst.coop",
    "xType": "category",
    "categories": [r["pipeline"] for r in rows],
    "format": {"suffix": "%", "decimals": 0},
    "yZero": True,
    "valueLabels": True,
    "rules": [{"axis": "y", "at": 100, "label": "Capacity"}],
    "series": [{"name": "Share of capacity used", "color": RED,
                "data": [r["utilization_pct"] for r in rows]}],
    "highlight": rows[0]["pipeline"],
    "categoryShort": {r["pipeline"]: r["pipeline"].split(" (")[0] for r in rows},   # names only where routes do not fit
}
(ROOT / "charts" / "pipeline-utilization.json").write_text(json.dumps(util, indent=2) + "\n")

# ---- 2. monthly Gulf -> East Coast shipments (EIA) -----------------------------
PRODUCTS = {  # EIA series, PADD 1 receipts by pipeline from PADD 3 (thousand barrels a month)
    "Diesel and other distillate": ["MD0MP", "MD1MP"],
    "Gasoline and blendstocks": ["MG4MP", "MO1MP", "MO5MP"],
    "Propane and other gas liquids": ["MNGMP"],
}
URL = "https://www.eia.gov/dnav/pet/hist_xls/{}_R10-R30_1m.xls"
monthly = {}
for name, codes in PRODUCTS.items():
    for code in codes:
        sh = xlrd.open_workbook(file_contents=urllib.request.urlopen(
            urllib.request.Request(URL.format(code), headers=UA), timeout=120).read()).sheet_by_name("Data 1")
        for r in range(3, sh.nrows):
            d, v = sh.cell_value(r, 0), sh.cell_value(r, 1)
            if v == "":
                continue
            y, m, *_ = xlrd.xldate_as_tuple(d, 0)
            if y >= 2024:
                k = f"{y}-{m:02d}"
                monthly.setdefault(k, {p: 0.0 for p in PRODUCTS})
                monthly[k][name] += v * 1000 / calendar.monthrange(y, m)[1]
months = sorted(monthly)
out = ROOT / "data" / "pipelines" / "gulf_to_east_coast_pipeline_monthly.csv"
with out.open("w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["month"] + [f"{p} (b/d)" for p in PRODUCTS] + ["total (b/d)"])
    for k in months:
        w.writerow([k] + [round(monthly[k][p]) for p in PRODUCTS] + [round(sum(monthly[k].values()))])
print(f"wrote {out.relative_to(ROOT)} ({months[0]} to {months[-1]})")

tot = {k: sum(monthly[k].values()) / 1000 for k in months}
dsl = {k: monthly[k]["Diesel and other distillate"] / 1000 for k in months}
winters = [{"x0": f"{y}-12-01", "x1": f"{y + 1}-03-01"} for y in (2023, 2024, 2025) if f"{y + 1}-01" in monthly]
peak = max(months, key=lambda k: tot[k])
mon = {
    "type": "line",
    "headline": "Pipeline shipments from the Gulf to the East Coast peak every winter",
    "subhead": "Gulf Coast to East Coast pipeline shipments, thousand barrels per day, monthly",
    "note": ("Shaded: December to February. Counts barrels crossing into the East Coast region (PADD 1); Colonial and "
             "Products SE also deliver in Mississippi, Alabama and Tennessee on the way, so this is not a share of "
             f"capacity. Latest month: {calendar.month_name[int(months[-1][5:])]} {months[-1][:4]}."),
    "source": "EIA, Movements by Pipeline between PAD Districts, East Coast receipts from the Gulf Coast (monthly)",
    "sourceUrl": "https://www.eia.gov/dnav/pet/pet_move_pipe_dc_R10-R30_mbbl_m.htm",
    "xType": "date",
    "format": {"decimals": 0},
    "yZero": True,
    "bands": winters,
    "series": [
        {"name": "All products", "color": NAVY, "data": [[k + "-15", round(tot[k])] for k in months]},
        {"name": "Diesel", "color": RED, "data": [[k + "-15", round(dsl[k])] for k in months]},
    ],
    "annotations": [{"x": peak + "-15", "y": round(tot[peak]), "series": "All products",
                     "text": f"{calendar.month_name[int(peak[5:])]} {peak[:4]}: {tot[peak]/1000:.2f}M b/d", "dx": -60, "dy": -24}],
}
(ROOT / "charts" / "pipeline-east-coast-monthly.json").write_text(json.dumps(mon, indent=2) + "\n")
print("wrote charts/pipeline-utilization.json, charts/pipeline-east-coast-monthly.json")
