# Maps

House-style (econ-chart-style) maps built here instead of in Datawrapper.
One self-contained HTML file per map: three frames (Substack 1456, Vertical 9:16,
Square 1:1), hover tooltips, and a Download PNG button, like the chart template.

```bash
cd maps && npm install          # geometry + d3-geo, from the npm registry
node build_map.js --config configs/diesel-exports-2024.json --out ../diesel-exports-2024.html
```

Published maps are written to the repo root, where GitHub Pages serves them at
`https://econchrisclarke.github.io/OilMarkets/<name>.html`. Drafts and variants
stay in `charts/`.

## Config

- `nodes`: `{id: {label, lonlat:[lon,lat], sides?, heading?, length?, arrowLabel?}}`.
  Destinations can sit off the map; they are pulled to the map edge.
- `flows`: `[{from, to, value, bend?}]`, with values in `units` (e.g. `b/d`).
- `style`:
  - `flows`: curved arrows from each origin to each destination.
  - `departure`: one arrow per origin, pointing toward its value-weighted destination.
  - `fan`: one short straight arrow per origin–destination pair.
- `frames.{substack,vertical,square}.bounds`: `[[west,south],[east,north]]`,
  fitted with a conformal conic projection.
- `direction: "in"` (with `style: "fan"`): an import map. The dot is the
  destination (e.g. a state) and the arrows arrive at it from the direction of
  their origin, coloured by the origin node's `color`; origin labels read
  "From X" at the arrow tails. `toward` is then the point the arrow comes from.
- `labelAt` on a dot's node (fan and departure styles) moves its label to that
  `[lon, lat]`, joined to the dot by a hairline leader. Use it when a cluster
  of dots (New England) leaves no room next to the dot.
- `widthMaxValue`: the value drawn at `maxArrowWidth`. Without it the map's
  largest flow gets the full width; set it (with the same `maxArrowWidth` and
  `legend`) on maps meant to be compared, so equal widths mean equal flows.
- `length` on a flow overrides its fan arrow's length (a node's `length` sets
  all of that origin's arrows). A very wide arrow needs a longer one to read
  as an arrow rather than a wedge.
- Node label options: `sub` replaces the second label line (default: the
  node's flow total); `textColor` colours the name; `dot: false` leaves the
  dot out (an "Imports" point that is a direction, not a place); `labelAt` now
  works in every style; and the side `"near"` centres the label on its point,
  or on the nearest free spot around it.
- `regions`: `{id: {color, states: [state names]}}` fills groups of US states
  as one pale area each (merged by the builder, outlined in white), e.g. PADDs.
- `bars`: `{max, height, width, values, legend, legendLabel}` with `bar`,
  `barAt` and `barColor` on nodes draws a vertical bar per node on one scale,
  with its value on top and a sample in the key.
- `labelBars`: `{max, height, width, legend, legendLabel, keys}` with
  `labelBars: [{value, color, textColor}]` on nodes draws skinny bars beside the
  node's name, values on top, placed with the label as one block.
- `nearMax` (design units, default 90) lets `"near"` labels search further for
  a free spot; `frames.X.labelBarsHeight` sets label-bar height per frame. A
  leader is drawn only when a label sits away from its dot.
- `color` on a flow overrides the destination colour (imports, exports and
  domestic flows in different colours).
- `legend`: reference values drawn as sample arrows. `draft: true` stamps a
  PLACEHOLDER watermark on the map.

## Lessons for the skill (maps-datawrapper.md is out of date)

- **The chart skill's reasons for handing maps to Datawrapper no longer hold here.**
  The npm registry is reachable, so `world-atlas`/`us-atlas` (Natural Earth
  TopoJSON) and `d3-geo` can be installed and inlined. That gives accurate
  geography in the house style, with no CDN at runtime.
- **Filter and round the geometry.** Keep only countries inside a bounding box
  and round coordinates to 0.01°. 50m countries plus 10m state lines then come
  to about 720 KB of HTML.
- **Screenshots can be checked in the sandbox.** Headless Chromium (Playwright)
  can render every frame via the same `draw()` the Download button uses. Google
  Fonts are blocked there, so screenshots show fallback faces.
- **Arrow width is linear in value**, unlike a circle's area. Readers compare
  widths, and a width is one-dimensional.
- **Port-to-destination curves tangle** once origins sit within about 100 miles
  of each other (Gulf Coast refineries). Group ports into regions for the
  national view, and show individual ports in a zoomed panel.
- **Straight arrows to far destinations cross land** (Gulf to Europe cuts
  across Georgia). Place destination anchors where the sea route goes, and
  label the arrowhead ("To Europe").
- **Labels are placed greedily and dropped rather than shrunk.** Dropped names
  are logged as `LABELS_DROPPED` in the console. Straight arrows reserve their
  footprint so labels avoid them.

### Arrow styles and labels (second round)

- `arrowStyle`: `flat`, `gradient`, `swoosh` (the one chosen) or `split`.
  - Swoosh tapers from a point to full width with a slight curve. Arrows
    leaving one origin are thin where they overlap, which is why it reads best.
  - Split (Sankey-style trunks) curls badly when one origin ships in
    opposite directions.
- **Destination colours:** set `color` (and `textColor` when the colour is too
  light for text) on destination nodes. Use three warm hues separated by
  lightness (red, amber, maroon) so they survive colour blindness. The
  destination labels printed in those colours are the key, so the swatch key
  (`colorKey`) is off by default.
- **Label placement:**
  - Labels are placed in descending order of volume, so the smallest flow is
    the one that loses its label.
  - Dots, arrow bodies and the key are all off limits to labels.
  - A label pushed off its dot gets a hairline leader.
  - Sides include diagonals (`ne`, `nw`, `se`, `sw`).
- **Per-frame settings:**
  - `labelMin` skips small origins on the phone frame, like the chart
    template's `pl:false`.
  - `shortLabels` uses each node's `short` name.
  - `keyPos: "tr"` moves the key to the top right.
- **Debugging:** set `window.MAP_DEBUG = 1` before load. Each dropped label
  then logs every spot it tried and what blocked it (edge, a named arrow, a
  label, a dot or the key). Fixing labels without this is guesswork.
