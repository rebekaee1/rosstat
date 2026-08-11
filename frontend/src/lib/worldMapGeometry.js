import { geoArea } from 'd3-geo';

export function displayWorldGeometry(geometry, code) {
  if (code !== 'FR' || geometry.geometry?.type !== 'MultiPolygon') return geometry;
  const mainland = geometry.geometry.coordinates
    .map((coordinates) => ({
      coordinates,
      area: geoArea({ type: 'Polygon', coordinates }),
    }))
    .sort((a, b) => b.area - a.area)[0];
  if (!mainland) return geometry;
  return {
    ...geometry,
    geometry: { type: 'Polygon', coordinates: mainland.coordinates },
  };
}
