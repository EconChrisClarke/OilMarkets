#!/usr/bin/env python3
"""US petroleum-product and crude-oil trunk pipeline routes, from the EIA
layers republished on the federal HIFLD open-data service (ArcGIS Online,
"Federal_User_Community"). Each feature has the operator and pipeline name;
the layers carry no capacity or volume.

Outputs:
  data/geo/pipelines_products.geojson
  data/geo/pipelines_crude.geojson
"""

import json
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASE = "https://services2.arcgis.com/FiaPA4ga0iQKduv3/arcgis/rest/services/{}/FeatureServer/0/query"
LAYERS = {"products": "Petroleum_Products_Pipelines_1", "crude": "Crude_Oil_Trunk_Pipelines_1"}

out_dir = ROOT / "data" / "geo"
out_dir.mkdir(parents=True, exist_ok=True)
for key, layer in LAYERS.items():
    feats, off = [], 0
    while True:                                   # the service pages at 1,000 features
        q = f"?where=1%3D1&outFields=*&outSR=4326&f=geojson&resultOffset={off}&resultRecordCount=1000"
        d = json.load(urllib.request.urlopen(BASE.format(layer) + q, timeout=120))
        feats += d["features"]
        if len(d["features"]) < 1000:
            break
        off += 1000
    out = out_dir / f"pipelines_{key}.geojson"
    out.write_text(json.dumps({"type": "FeatureCollection", "features": feats}))
    print(f"wrote {out.relative_to(ROOT)} ({len(feats)} segments)")
