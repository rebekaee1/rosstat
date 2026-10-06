/** Largest side of a ring's bounding box, in degrees; a ring crossing the antimeridian is certainly large. */
export function ringSpanDegrees(ring) {
  let west = Infinity; let east = -Infinity; let south = Infinity; let north = -Infinity;
  for (const point of ring) {
    if (point[0] < west) west = point[0];
    if (point[0] > east) east = point[0];
    if (point[1] < south) south = point[1];
    if (point[1] > north) north = point[1];
  }
  return east - west > 180 ? Infinity : Math.max(east - west, north - south);
}

/**
 * Rings worth an outline. A ring smaller than `minSpanDegrees` is only filled: at that size a graphite
 * line is a black speck (Caribbean islets, lakes, atolls), not a border.
 */
export function outlineRings(geometry, minSpanDegrees = 0) {
  const polygons = geometry?.type === 'Polygon' ? [geometry.coordinates]
    : geometry?.type === 'MultiPolygon' ? geometry.coordinates : [];
  const rings = [];
  for (const polygon of polygons) {
    for (const ring of polygon) {
      if (Array.isArray(ring) && ring.length >= 4 && ringSpanDegrees(ring) >= minSpanDegrees) rings.push(ring);
    }
  }
  return rings;
}

/**
 * Geometry without dust. Fill and stroke of a ring only a pixel or two wide read as a black or dark-gold speck
 * (Greek and Croatian islets, Chesapeake bays, Azov and Caspian rocks, Caribbean cays), and they come in swarms in the 50m atlas.
 * Keeps polygons whose outer ring spans at least `minSpanDegrees`, always keeps the largest one (so Malta, Singapore
 * or Luxembourg stay painted) and drops small holes. Returns a geometry of the same kind, or the input if it has no polygons.
 */
export function substantialPolygons(geometry, minSpanDegrees = 0) {
  const polygons = geometry?.type === 'Polygon' ? [geometry.coordinates]
    : geometry?.type === 'MultiPolygon' ? geometry.coordinates : null;
  if (!polygons || !polygons.length) return geometry;
  const sized = polygons.map((rings) => ({ rings, span: ringSpanDegrees(rings[0] || []) }));
  let largest = sized[0];
  for (const item of sized) if (item.span > largest.span) largest = item;
  const kept = sized
    .filter((item) => item === largest || item.span >= minSpanDegrees)
    .map((item) => item.rings.filter((ring, index) => index === 0 || ringSpanDegrees(ring) >= minSpanDegrees));
  return kept.length === 1 ? { type: 'Polygon', coordinates: kept[0] } : { type: 'MultiPolygon', coordinates: kept };
}
