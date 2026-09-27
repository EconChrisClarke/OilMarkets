# Maps

House-style (econ-chart-style) maps built here instead of in Datawrapper.
One self-contained HTML file per map: three frames (Substack 1456, Vertical 9:16,
Square 1:1), hover tooltips, and a Download PNG button, like the chart template.

```bash
cd maps && npm install          # geometry + d3-geo, from the npm registry
node build_map.js --config configs/diesel-exports-fan.json --out ../charts/diesel-exports-fan.html
```

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
