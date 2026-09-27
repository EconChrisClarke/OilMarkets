#!/usr/bin/env python3
"""Turn the raw 2024 Census distillate import file into a by-state table and
the map config for the import arrow map.

Input  (from fetch_distillate_2024.py):
  data/census_trade/distillate_imports_district_country_2024.csv
Outputs:
  data/census_trade/distillate_imports_by_state_2024.csv
      state of entry x origin country, barrels per day (measured)
  maps/configs/diesel-imports-2024.json

"State" is the state of the customs district where the diesel cleared
customs, not where it was burned: Census publishes import quantities by
district, and its state-of-destination series is in dollars at HS6 only
(which lumps diesel with jet fuel and residual fuel oil).
"""

import csv
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
D = ROOT / "data" / "census_trade"
DAYS = 366  # 2024 is a leap year

# Customs district -> state of entry. District 01 (Portland, ME) also takes in
# New Hampshire's ports; 33 (Great Falls, MT) also takes in Idaho's crossings.
DISTRICT_STATE = {
    "01": "ME", "02": "VT", "04": "MA", "05": "RI", "07": "NY", "09": "NY",
    "10": "NY", "11": "PA", "16": "SC", "17": "GA", "18": "FL", "20": "LA",
    "23": "TX", "24": "TX", "27": "CA", "28": "CA", "29": "OR", "30": "WA", "31": "AK", "32": "HI",
    "33": "MT", "34": "ND", "36": "MN", "37": "WI", "38": "MI", "45": "MO",
    "49": "PR", "51": "VI", "52": "FL", "53": "TX", "54": "DC",
}
STATE_NAME = {
    "ME": "Maine", "VT": "Vermont", "MA": "Massachusetts", "RI": "Rhode Island",
    "NY": "New York", "PA": "Pennsylvania", "SC": "South Carolina", "GA": "Georgia",
    "FL": "Florida", "LA": "Louisiana", "TX": "Texas", "CA": "California",
    "OR": "Oregon", "WA": "Washington", "AK": "Alaska", "HI": "Hawaii",
    "MT": "Montana", "ND": "North Dakota", "MN": "Minnesota", "WI": "Wisconsin",
    "MI": "Michigan", "MO": "Missouri", "DC": "District of Columbia", "PR": "Puerto Rico", "VI": "US Virgin Islands",
}

rows = [r for r in csv.DictReader(open(D / "distillate_imports_district_country_2024.csv"))
        if r["SUMMARY_LVL"] == "DET" and r["DISTRICT"] != "-" and r["CTY_CODE"] != "-"]
by_sc = Counter()
for r in rows:
    st = DISTRICT_STATE.get(r["DISTRICT"])
    if st is None:
        raise SystemExit(f"district {r['DISTRICT']} {r['DIST_NAME']} has no state")
    by_sc[(st, r["CTY_NAME"].title())] += int(r["GEN_QY1_YR"]) / DAYS
by_sc = Counter({k: v for k, v in by_sc.items() if v >= 0.5})
total = sum(by_sc.values())

out = D / "distillate_imports_by_state_2024.csv"
with out.open("w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["state", "state_name", "origin_country", "barrels_per_day"])
    for (st, c), v in sorted(by_sc.items(), key=lambda x: -x[1]):
        w.writerow([st, STATE_NAME[st], c, round(v)])
print(f"wrote {out.relative_to(ROOT)} ({len(by_sc)} rows)")

# ---- map config -----------------------------------------------------------
# Dots sit at the main port of entry, nudged inland where two states' dots
# would otherwise touch at national scale.
STATE_NODE = {
    "MA": {"lonlat": [-71.2, 42.4], "sides": ["se", "below"]},
    "ME": {"lonlat": [-70.0, 44.0], "sides": ["right", "se", "ne"]},
    "NY": {"lonlat": [-75.6, 43.1], "sides": ["left", "sw", "below", "nw"]},
    "MT": {"lonlat": [-110.5, 47.6], "sides": ["below", "left", "right"]},
    "RI": {"lonlat": [-71.5, 41.7], "labelAt": [-70.5, 38.6], "sides": ["below", "right", "left"]},
    "VT": {"lonlat": [-72.8, 44.4], "sides": ["left", "sw", "below", "nw"]},
    "ND": {"lonlat": [-98.5, 47.9], "sides": ["below", "right", "left"]},
    "WA": {"lonlat": [-122.3, 47.6], "sides": ["below", "left", "right"]},
    "MI": {"lonlat": [-83.05, 42.33], "sides": ["below", "left", "sw", "right"]},
    "WI": {"lonlat": [-87.9, 43.04], "sides": ["below", "left", "sw"]},
    "FL": {"lonlat": [-81.6, 27.8], "sides": ["left", "below", "right"]},
    "PR": {"lonlat": [-66.3, 18.25], "sides": ["right", "below", "left", "above"]},
}
ORIGINS = {
    "canada": {"label": "Canada", "color": "#1B3A5C", "lonlat": [-95, 58], "labelAt": [-86, 51.5], "sides": ["left", "above", "below"]},
    "colombia": {"label": "Colombia", "color": "#2E8B7A", "lonlat": [-74, 5]},
}
COUNTRY_NODE = {"Canada": "canada", "Colombia": "colombia"}
# Arrows point back along the supply route. Canadian diesel into New England
# comes mostly by tanker from Saint John, New Brunswick, so those arrows come
# in off the Atlantic, fanned out so the three heads don't pile up. Along the
# land border it comes straight from the north.
TOWARD = {
    ("canada", "ME"): [-67, 49], ("canada", "MA"): [-60, 40.5],
    ("canada", "RI"): [-60, 37.5], ("canada", "PR"): [-61, 30],
}
MIN = 1000
flows = []
for (st, c), v in sorted(by_sc.items(), key=lambda x: -x[1]):
    if v < MIN or st not in STATE_NODE or c not in COUNTRY_NODE:
        continue
    o = COUNTRY_NODE[c]
    f = {"from": o, "to": st, "value": round(v, -2)}
    lon, lat = STATE_NODE[st]["lonlat"]
    f["toward"] = TOWARD.get((o, st), [lon, lat + 6] if o == "canada" else None)
    if f["toward"] is None:
        del f["toward"]
    flows.append(f)
shown = sum(f["value"] for f in flows)
by_state = Counter()
by_country = Counter()
for (st, c), v in by_sc.items():
    by_state[st] += v
    by_country[c] += v

cfg = {
    "headline": "Most US diesel imports are Canadian fuel landing in New England",
    "subhead": "Distillate fuel oil imports by state of entry and country of origin, 2024, barrels per day",
    "note": (f"Map covers {shown/total:.0%} of imports. Alaska ({by_state['AK']/1000:.0f}k b/d) "
             f"and Hawaii ({by_state['HI']/1000:.0f}k b/d) not shown. State is where the diesel "
             "cleared customs."),
    "source": "US Census Bureau, International Trade API (imports by customs district, HS10)",
    "sourceUrl": "https://api.census.gov/data/timeseries/intltrade/imports/hs",
    "units": "b/d",
    "draft": False,
    "style": "fan",
    "direction": "in",
    "arrowStyle": "swoosh",
    "arrowLength": 95,
    "maxArrowWidth": 26,
    "legendTitle": "Arrow width",
    "legend": [10000, 40000],
    "geoBBox": [-170, -25, -20, 75],
    "nodes": {**{k: {"label": STATE_NAME[k], "short": k if len(STATE_NAME[k]) > 9 else STATE_NAME[k],
                     **n} for k, n in STATE_NODE.items()}, **ORIGINS},
    "flows": flows,
    "frames": {
        "substack": {"bounds": [[-125, 16], [-62, 53]]},
        "vertical": {"bounds": [[-124, 16], [-63, 52]], "labelMin": 6000, "shortLabels": True},
        "square": {"bounds": [[-124, 16], [-61, 53]],
                   # the square frame is narrower: move RI's label out to sea and
                   # put Puerto Rico's on its west side, where there is room
                   "nodes": {"RI": {"labelAt": [-68.5, 39.6]},
                             "PR": {"sides": ["left", "nw", "above"]}}},
    },
}
out = ROOT / "maps" / "configs" / "diesel-imports-2024.json"
out.write_text(json.dumps(cfg, indent=2) + "\n")
print(f"wrote {out.relative_to(ROOT)} ({len(flows)} flows)")
print(f"imports {total:,.0f} b/d, arrows cover {shown/total:.1%}")
print("by country:", {k: round(v) for k, v in by_country.most_common(6)})
print("by state:", {k: round(v) for k, v in by_state.most_common()})
for f in flows:
    print(f"  {f['from']:9s} -> {f['to']} {f['value']:8,.0f}")
