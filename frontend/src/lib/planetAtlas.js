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
