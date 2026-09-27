# OilMarkets

Charts and data on global crude oil markets.

## Charts

**Live pages** (GitHub Pages, `https://econchrisclarke.github.io/OilMarkets/`):

| # | Chart | Live page |
|---|---|---|
| 1 | The US exports 1.2 million barrels of diesel a day, mostly from the Gulf | [diesel-exports-2024.html](https://econchrisclarke.github.io/OilMarkets/diesel-exports-2024.html) |
| 2 | Most US diesel imports are Canadian fuel landing in New England | [diesel-imports-2024.html](https://econchrisclarke.github.io/OilMarkets/diesel-imports-2024.html) |

### US diesel exports by port region and destination, 2024

The US exported 1.19 million barrels a day of distillate fuel oil (diesel and
heating oil) in 2024, mostly from Texas and Louisiana/Mississippi ports.
About half went to Latin America, a quarter to Europe and a fifth to Mexico.
Arrow width is barrels per day.

- **View the map:** [diesel-exports-2024.html](https://econchrisclarke.github.io/OilMarkets/diesel-exports-2024.html)
  (Substack, vertical and square frames; hover for flow details; PNG export button)
- **Data:** [`data/census_trade/distillate_exports_by_district_2024.csv`](data/census_trade/distillate_exports_by_district_2024.csv)
  (exports), [`data/census_trade/distillate_imports_by_district_2024.csv`](data/census_trade/distillate_imports_by_district_2024.csv) (imports)
- **Map config:** [`maps/configs/diesel-exports-2024.json`](maps/configs/diesel-exports-2024.json),
  built by [`scripts/process_distillate_2024.py`](scripts/process_distillate_2024.py) and
  [`maps/build_map.js`](maps/build_map.js) (see [`maps/README.md`](maps/README.md))

**Source:** US Census Bureau, International Trade API, exports by customs
district at the HS10 level (Schedule B 2710.19.1106/1109/1112 and 2710.20).

### US diesel imports by state of entry and origin, 2024

The US imported 168,000 barrels a day of distillate fuel oil in 2024, about a
seventh of what it exported. Canada supplied 88% of it, and 59% came in
through New England: Massachusetts (47k b/d), Maine (38k b/d), Rhode Island
and Vermont. Puerto Rico (20k b/d, mostly from Colombia) was the next largest.
"State" is where the diesel cleared customs (the customs district's state),
not where it was used. Arrow width is barrels per day.

- **View the map:** [diesel-imports-2024.html](https://econchrisclarke.github.io/OilMarkets/diesel-imports-2024.html)
- **Data:** [`data/census_trade/distillate_imports_by_state_2024.csv`](data/census_trade/distillate_imports_by_state_2024.csv)
- **Map config:** [`maps/configs/diesel-imports-2024.json`](maps/configs/diesel-imports-2024.json),
  built by [`scripts/process_distillate_imports_2024.py`](scripts/process_distillate_imports_2024.py)

**Source:** US Census Bureau, International Trade API, imports by customs
district at the HS10 level (the same distillate codes as the export map).

### Crude oil sulfur content vs. API gravity

The heavier a crude oil, the more sulfur it tends to carry. This chart plots
API gravity (a measure of density — higher is lighter) against sulfur
content for major crude oil benchmarks traded worldwide.

- **View the chart:** [Open interactive chart](https://htmlpreview.github.io/?https://raw.githubusercontent.com/EconChrisClarke/OilMarkets/main/charts/crude-oil-sulfur-api.html)
  (renders in-browser; includes a PNG export button)
- **Data:** [`data/crude_oil_sulfur_api.csv`](data/crude_oil_sulfur_api.csv)
- **Chart source config:** [`charts/crude-oil-sulfur-api.json`](charts/crude-oil-sulfur-api.json)
- **Static image:** [`images/crude-oil-sulfur-api.png`](images/crude-oil-sulfur-api.png)

![Crude oil sulfur content vs. API gravity](images/crude-oil-sulfur-api.png)

**Source:** Langer, Huppmann & Holz (2016), "Lifting the US crude oil export
ban," *Energy Policy*.
