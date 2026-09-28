#!/usr/bin/env node
/* Country silhouettes as SVG path strings, for the chart template's
   `categoryIcons`. Each shape is fitted into a 100 x 100 box (so icons are
   not to scale with each other) from Natural Earth 1:50m outlines.

     node chartkit/scripts/country_icons.js "Saudi Arabia" Kuwait EU27 ...
       -> JSON {name: "M..Z"} on stdout

   "EU27" merges the member states into one outline, clipped to Europe so
   overseas territories (French Guiana, Reunion, ...) drop out.
   Uses the geometry and d3-geo installed for the map builder (maps/). */

const path = require('path');
const mod = p => require(path.join(__dirname, '..', '..', 'maps', 'node_modules', p));
const topojson = mod('topojson-client');
const d3 = Object.assign({}, mod('d3-geo'));
const world = mod('world-atlas/countries-50m.json');

const EU27 = ['Austria', 'Belgium', 'Bulgaria', 'Croatia', 'Cyprus', 'Czechia', 'Denmark', 'Estonia',
  'Finland', 'France', 'Germany', 'Greece', 'Hungary', 'Ireland', 'Italy', 'Latvia', 'Lithuania',
  'Luxembourg', 'Malta', 'Netherlands', 'Poland', 'Portugal', 'Romania', 'Slovakia', 'Slovenia',
  'Spain', 'Sweden'];
const ALIASES = { 'UAE': 'United Arab Emirates', 'US': 'United States of America' };

const geoms = world.objects.countries.geometries;
const byName = n => geoms.filter(g => g.properties.name === (ALIASES[n] || n));

/* Keep only rings big enough to see at icon size: tiny islands turn into
   specks that read as noise. */
function prune(feature, keep) {
  const g = feature.geometry;
  const polys = g.type === 'Polygon' ? [g.coordinates] : g.coordinates;
  const area = p => Math.abs(d3.geoArea({ type: 'Polygon', coordinates: p }));
  const big = Math.max(...polys.map(area));
  return { type: 'Feature', geometry: { type: 'MultiPolygon',
    coordinates: polys.filter(p => area(p) >= big * keep) } };
}

function icon(name) {
  let f, extent = null;
  if (name === 'EU27') {
    const members = EU27.flatMap(byName);
    if (members.length !== EU27.length) throw new Error('EU27: missing members in the geometry');
    f = { type: 'Feature', geometry: topojson.merge(world, members) };
    extent = [[-11, 34.5], [34, 70.5]];        // mainland Europe and the Mediterranean islands
    const clip = d3.geoClipRectangle(extent[0][0], extent[0][1], extent[1][0], extent[1][1]);
    f = { type: 'Feature', geometry: {
      type: 'MultiPolygon',
      coordinates: f.geometry.coordinates.filter(p => p[0].every(([x, y]) =>
        x >= extent[0][0] && x <= extent[1][0] && y >= extent[0][1] && y <= extent[1][1])) } };
    f = prune(f, 0.0005);
  } else {
    const g = byName(name);
    if (!g.length) throw new Error(`no country named "${name}" in the geometry`);
    f = prune(topojson.feature(world, g[0]), 0.002);
  }
  const c = d3.geoCentroid(f);
  const proj = d3.geoAzimuthalEqualArea().rotate([-c[0], -c[1]]).fitExtent([[2, 2], [98, 98]], f);
  const p = d3.geoPath(proj).digits(1)(f);
  return p;
}

const out = {};
for (const n of process.argv.slice(2)) out[n] = icon(n);
process.stdout.write(JSON.stringify(out));
