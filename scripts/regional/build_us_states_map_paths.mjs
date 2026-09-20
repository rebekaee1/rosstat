#!/usr/bin/env node
/**
 * SVG path map of U.S. states for the subnational choropleth (ADR-0014).
 *
 * Geometry: U.S. Census Bureau cartographic boundary files via the `us-atlas`
 * TopoJSON package (`states-10m.json`), public domain. The npm package is ISC.
 * Downloaded at build time from unpkg — not vendored as a runtime dependency.
 *
 * Projection: d3.geoAlbersUsa (Alaska and Hawaii as insets).
 * Output: frontend/src/lib/usStatesMap.json
 *   { viewBox, regions:[{slug,path}], markers:[{slug,cx,cy}] }
 * District of Columbia is a clickable marker (same pattern as Moscow).
 *
 * FIPS → slug mapping is read from backend/app/data/world_subnational/us.yaml.
 *
 * Run: node scripts/regional/build_us_states_map_paths.mjs
 */
import { writeFileSync, readFileSync, mkdirSync } from 'node:fs';
import { createRequire } from 'node:module';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '../..');
const require = createRequire(resolve(ROOT, 'frontend/package.json'));
const { geoAlbersUsa, geoPath } = require('d3-geo');
const { feature } = require('topojson-client');

const YAML_PATH = resolve(ROOT, 'backend/app/data/world_subnational/us.yaml');
const OUT_PATH = resolve(ROOT, 'frontend/src/lib/usStatesMap.json');
const ATLAS_URL = 'https://unpkg.com/us-atlas@3/states-10m.json';
const WIDTH = 960;
const HEIGHT = 600;
const DC_FIPS = '11';

function fipsToSlug(yamlText) {
  const map = new Map();
  const blocks = yamlText.split(/\n  - slug:/).slice(1);
  for (const block of blocks) {
    const slug = block.match(/^\s*([a-z0-9-]+)/)?.[1];
    const fips = block.match(/\bfips:\s*"?(\d+)"?/)?.[1];
    if (slug && fips) map.set(fips.padStart(2, '0'), slug);
  }
  return map;
}

function ringToPath(ring) {
  if (!ring?.length) return '';
  return ring
    .map(([x, y], i) => `${i === 0 ? 'M' : 'L'}${x.toFixed(1)} ${y.toFixed(1)}`)
    .join('') + 'Z';
}

function geomToPath(geom, project) {
  if (!geom) return '';
  if (geom.type === 'Polygon') {
    return geom.coordinates.map((ring) => ringToPath(ring.map(project).filter(Boolean))).join('');
  }
  if (geom.type === 'MultiPolygon') {
    return geom.coordinates
      .map((poly) => poly.map((ring) => ringToPath(ring.map(project).filter(Boolean))).join(''))
      .join('');
  }
  return '';
}

function centroid(geom, project) {
  const polys = geom.type === 'Polygon' ? [geom.coordinates] : geom.coordinates;
  let sx = 0;
  let sy = 0;
  let n = 0;
  for (const poly of polys) {
    for (const [lon, lat] of poly[0] || []) {
      const xy = project([lon, lat]);
      if (!xy) continue;
      sx += xy[0];
      sy += xy[1];
      n += 1;
    }
  }
  if (!n) return null;
  return [sx / n, sy / n];
}

async function main() {
  const yamlText = readFileSync(YAML_PATH, 'utf8');
  const fipsMap = fipsToSlug(yamlText);
  const res = await fetch(ATLAS_URL);
  if (!res.ok) throw new Error(`us-atlas download HTTP ${res.status}`);
  const topo = await res.json();
  const collection = feature(topo, topo.objects.states);
  const projection = geoAlbersUsa().fitSize([WIDTH, HEIGHT], collection);
  const project = (coords) => {
    const xy = projection(coords);
    return xy ? [xy[0], xy[1]] : null;
  };
  // geoPath is used only to validate the projection; paths are built from
  // projected rings so the JSON stays compact and matches regionsMap.json.
  geoPath(projection);

  const regions = [];
  const markers = [];
  for (const feat of collection.features) {
    const fips = String(feat.id).padStart(2, '0');
    const slug = fipsMap.get(fips);
    if (!slug) continue;
    const path = geomToPath(feat.geometry, project);
    if (path) regions.push({ slug, path });
    if (fips === DC_FIPS) {
      const c = centroid(feat.geometry, project);
      if (c) markers.push({ slug, cx: +c[0].toFixed(1), cy: +c[1].toFixed(1) });
    }
  }
  if (regions.length < 50) {
    throw new Error(`expected 50+ states, got ${regions.length}`);
  }
  const payload = {
    viewBox: `0 0 ${WIDTH} ${HEIGHT}`,
    regions,
    markers,
  };
  mkdirSync(dirname(OUT_PATH), { recursive: true });
  writeFileSync(OUT_PATH, JSON.stringify(payload));
  console.log(`wrote ${OUT_PATH} regions=${regions.length} markers=${markers.length}`);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
