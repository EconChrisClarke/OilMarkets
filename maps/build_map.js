#!/usr/bin/env node
/* Build a self-contained house-style flow-arrow map.

     node maps/build_map.js --config maps/configs/<name>.json --out charts/<name>.html

   Geometry (Natural Earth via world-atlas, US states via us-atlas) and the
   projection code (d3-geo) are inlined into the HTML, so the file has no
   runtime dependency except Google Fonts, which degrade to system faces. */

const fs = require('fs');
const path = require('path');
const topojson = require('topojson-client');

const args = Object.fromEntries(process.argv.slice(2).reduce((a, v, i, arr) =>
  v.startsWith('--') ? a.concat([[v.slice(2), arr[i + 1]]]) : a, []));
if (!args.config || !args.out) {
  console.error('usage: node build_map.js --config <config.json> --out <file.html>');
  process.exit(1);
}

const cfg = JSON.parse(fs.readFileSync(args.config, 'utf8'));
const mod = p => path.join(__dirname, 'node_modules', p);

/* ---- validate --------------------------------------------------------- */
const errs = [];
for (const k of ['headline', 'subhead', 'source', 'units', 'nodes', 'flows', 'frames'])
  if (!cfg[k]) errs.push(`missing "${k}"`);
if (cfg.headline && cfg.headline.length > 110) errs.push('headline over 110 characters');
const ids = new Set(Object.keys(cfg.nodes || {}));
(cfg.flows || []).forEach((f, i) => {
  if (!ids.has(f.from)) errs.push(`flow ${i}: unknown node "${f.from}"`);
  if (!ids.has(f.to)) errs.push(`flow ${i}: unknown node "${f.to}"`);
  if (!(f.value > 0)) errs.push(`flow ${i}: value must be positive`);
});
for (const [k, n] of Object.entries(cfg.nodes || {}))
  if (!Array.isArray(n.lonlat) || n.lonlat.length !== 2) errs.push(`node ${k}: lonlat must be [lon, lat]`);
if (errs.length) { console.error('config errors:\n  ' + errs.join('\n  ')); process.exit(1); }

/* ---- geometry --------------------------------------------------------- */
/* Keep only countries that touch the widest frame's bounding box, and round
   coordinates to 0.01 degrees (about 1km) — invisible at these scales and it
   cuts the file size several-fold. */
const bbox = cfg.geoBBox || [-170, -60, 10, 80];    // [w, s, e, n]
const round = c => typeof c[0] === 'number'
  ? [Math.round(c[0] * 100) / 100, Math.round(c[1] * 100) / 100]
  : c.map(round);
function inBox(geom) {
  let hit = false;
  const walk = c => {
    if (hit) return;
    if (typeof c[0] === 'number') {
      if (c[0] >= bbox[0] && c[0] <= bbox[2] && c[1] >= bbox[1] && c[1] <= bbox[3]) hit = true;
    } else c.forEach(walk);
  };
  walk(geom.coordinates);
  return hit;
}
const world = JSON.parse(fs.readFileSync(mod('world-atlas/countries-50m.json')));
const countries = topojson.feature(world, world.objects.countries).features
  .filter(f => f.geometry && inBox(f.geometry))
  .map(f => ({ type: 'Feature', id: f.id, properties: { name: f.properties.name },
               geometry: { type: f.geometry.type, coordinates: round(f.geometry.coordinates) } }));
const us = JSON.parse(fs.readFileSync(mod('us-atlas/states-10m.json')));
const stateLines = topojson.mesh(us, us.objects.states, (a, b) => a !== b);
stateLines.coordinates = round(stateLines.coordinates);
const GEO = { countries, stateLines, home: cfg.homeCountry || 'United States of America' };

/* ---- stamp ------------------------------------------------------------ */
const lib = fs.readFileSync(mod('d3-array/dist/d3-array.min.js'), 'utf8') + '\n' +
            fs.readFileSync(mod('d3-geo/dist/d3-geo.min.js'), 'utf8');
let html = fs.readFileSync(path.join(__dirname, 'map-template.html'), 'utf8');
const put = (tag, s) => { html = html.split(tag).join(s); };
put('/*LIBS*/', lib);
put('/*GEO*/', JSON.stringify(GEO));
put('/*CONFIG*/', JSON.stringify(cfg, null, 1));
put('MAP_TITLE', cfg.title || cfg.headline.replace(/</g, '&lt;'));
fs.mkdirSync(path.dirname(args.out), { recursive: true });
fs.writeFileSync(args.out, html);
console.log(`wrote ${args.out} (${(html.length / 1024).toFixed(0)} KB, ${countries.length} countries)`);
