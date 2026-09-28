#!/usr/bin/env python3
"""Imports of gasoil/diesel-type oils (HS 271019) from the Gulf, by importer,
monthly, January 2025 onwards: the "mirror" of Gulf exports, as reported by
the countries that receive them.

Why mirror data: most Gulf states do not report their own product exports
(JODI has only Saudi Arabia, Kuwait and Bahrain), but their customers do.

Sources:
  UN Comtrade public API (no key), monthly, HS6, for importers in Asia,
      Africa and Oceania that have filed 2026 months.
  Eurostat Comext DS-059341, monthly, HS6, EU27 as one reporter.

HS 271019 is "other medium and heavy oils": mostly diesel/gasoil, but it also
includes jet fuel and some fuel oils. Quantities are net weight; barrels use
7.46 bbl/tonne (diesel), so they are approximate for the jet and fuel-oil part.

CAUTION: for bunkering hubs and several Asian importers (Singapore, Hong Kong,
Mauritius, India) HS 271019 is dominated by heavy fuel oil, not diesel (unit
values ~$400-550/t against ~$600-1,100/t for diesel), and Egypt reports
estimated weights at a flat unit value. Use those rows for direction only.
The EU27 rows (Eurostat) are the most reliable here.

Output: data/trade/gulf_271019_imports_monthly.csv
  importer, partner, month, tonnes, barrels_per_day
"""

import csv
import json
import time
import urllib.request
from calendar import monthrange
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "trade" / "gulf_271019_imports_monthly.csv"
BBL_PER_T = 7.46
MONTHS = [f"{y}{m:02d}" for y in (2025, 2026) for m in range(1, 13) if f"{y}{m:02d}" <= "202607"]

# Gulf suppliers, Comtrade (M49) and Eurostat (ISO2) codes; 0 / "WORLD" = all
PARTNERS = {"Saudi Arabia": (682, "SA"), "UAE": (784, "AE"), "Kuwait": (414, "KW"),
            "Bahrain": (48, "BH"), "Oman": (512, "OM"), "Qatar": (634, "QA"),
            "Iraq": (368, "IQ"), "Iran": (364, "IR"), "World": (0, None)}
# Importers that had filed 2026 months with Comtrade at the time of writing
IMPORTERS = {"Australia": 36, "Japan": 392, "Malaysia": 458, "Philippines": 608,
             "Thailand": 764, "Indonesia": 360, "Hong Kong": 344, "India": 699,
             "Singapore": 702, "Pakistan": 586, "South Africa": 710, "Egypt": 818,
             "Angola": 24, "Cote d'Ivoire": 384, "Mauritius": 480, "Ghana": 288, "Togo": 768}
UA = {"User-Agent": "Mozilla/5.0"}


def get(url, tries=6):
    for i in range(tries):
        try:
            j = json.load(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120))
        except Exception as e:           # rate limit or timeout: back off
            time.sleep(10 * (i + 1)); continue
        if isinstance(j, dict) and "ASYNCH" in json.dumps(j.get("error", ""))[:200]:
            time.sleep(30); continue
        return j
    raise RuntimeError(f"gave up on {url}")


def bpd(tonnes, month):
    y, m = int(month[:4]), int(month[4:])
    return tonnes * BBL_PER_T / monthrange(y, m)[1]


rows = []
code2name = {v[0]: k for k, v in PARTNERS.items()}
name_of = {v: k for k, v in IMPORTERS.items()}
# The preview endpoint takes one month per call, but many importers at once
for per in MONTHS:
    url = ("https://comtradeapi.un.org/public/v1/preview/C/M/HS?reporterCode=%s&period=%s"
           "&partnerCode=%s&cmdCode=271019&flowCode=M&motCode=0&customsCode=C00&partner2Code=0"
           % (",".join(str(c) for c in IMPORTERS.values()), per,
              ",".join(str(v[0]) for v in PARTNERS.values())))
    n = 0
    for r in get(url).get("data", []) or []:
        kg = r.get("netWgt") or 0
        if not kg and r.get("qtyUnitCode") == 8:      # 8 = kg
            kg = r.get("qty") or 0
        p, imp = code2name.get(r["partnerCode"]), name_of.get(r["reporterCode"])
        if p and imp and kg:
            rows.append([imp, p, r["period"], round(kg / 1000), round(bpd(kg / 1000, r["period"]))]); n += 1
    print(f"{per}: {n} rows")
    time.sleep(3)

# EU27 from Eurostat (quantity in kg)
url = ("https://ec.europa.eu/eurostat/api/comext/dissemination/statistics/1.0/data/DS-059341?"
       "format=JSON&lang=en&freq=M&product=271019&flow=1&reporter=EU&indicators=QUANTITY_KG"
       "&sinceTimePeriod=2025-01" + "".join(f"&partner={v[1]}" for v in PARTNERS.values() if v[1])
       + "&partner=WORLD")
j = get(url)
dims, size = j["id"], j["size"]
rev = {d: {v: k for k, v in j["dimension"][d]["category"]["index"].items()} for d in dims}
iso2name = {v[1]: k for k, v in PARTNERS.items() if v[1]}
iso2name["WORLD"] = "World"
for flat, v in j["value"].items():
    f, pos = int(flat), {}
    for d, s in reversed(list(zip(dims, size))):
        pos[d] = f % s; f //= s
    per = rev["time"][pos["time"]].replace("-", "")
    p = iso2name.get(rev["partner"][pos["partner"]])
    if p and per <= MONTHS[-1] and v:
        rows.append(["EU27", p, per, round(v / 1000), round(bpd(v / 1000, per))])
print(f"EU27: {sum(1 for x in rows if x[0] == 'EU27')} rows")

OUT.parent.mkdir(parents=True, exist_ok=True)
with OUT.open("w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["importer", "partner", "month", "tonnes", "barrels_per_day"])
    w.writerows(sorted(rows, key=lambda r: (r[0], r[1], r[2])))
print(f"wrote {OUT.relative_to(ROOT)} ({len(rows)} rows)")
