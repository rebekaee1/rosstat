import { geoArea } from 'd3-geo';

const KM_PER_DEGREE = 111.32;

/**
 * Пороги отбора «основной территории» страны. Подобраны по фактической
 * геометрии Natural Earth (проверено на 68 странах карты в обоих разрешениях):
 * NEAR_KM держит прижатые к материку острова (Корсика, Готланд, Борнхольм,
 * Аландские о-ва), FAR_KM с MAJOR_AREA_RATIO — крупные удалённые части
 * (Аляска, Папуа, Хоккайдо), но уже не Гвиану и не Гавайи. SPECK_* отсекает
 * одиночные скалы, которые растягивают кадр вдвое (о. Медвежий и Ян-Майен
 * у Норвегии).
 */
const NEAR_KM = 400;
const NEAR_SPAN_FACTOR = 0.25;
const FAR_KM = 2500;
const MAJOR_AREA_RATIO = 0.05;
const SPECK_AREA_RATIO = 0.002;
const SPECK_NEAR_KM = 150;

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

/** Число вершин контура — мера того, насколько он угловат в кадре карточки. */
export function outlinePointCount(geometry) {
  let count = 0;
  const walk = (node) => {
    if (typeof node[0] === 'number') {
      count += 1;
      return;
    }
    node.forEach(walk);
  };
  const coordinates = geometry?.geometry?.coordinates;
  if (!coordinates) return 0;
  walk(coordinates);
  return count;
}

function boundingBox(coordinates) {
  let west = Infinity;
  let south = Infinity;
  let east = -Infinity;
  let north = -Infinity;
  const walk = (node) => {
    if (typeof node[0] === 'number') {
      if (node[0] < west) west = node[0];
      if (node[0] > east) east = node[0];
      if (node[1] < south) south = node[1];
      if (node[1] > north) north = node[1];
      return;
    }
    node.forEach(walk);
  };
  walk(coordinates);
  return [west, south, east, north];
}

/** Разрыв по долготе с учётом перехода через 180-й меридиан (Россия, США, Новая Зеландия). */
function longitudeGapDegrees(a, b) {
  if (a[2] >= b[0] && b[2] >= a[0]) return 0;
  const wrap = (value) => ((((value + 180) % 360) + 360) % 360) - 180;
  return Math.min(Math.abs(wrap(b[0] - a[2])), Math.abs(wrap(a[0] - b[2])));
}

function gapKm(a, b) {
  let latitudeGap = 0;
  if (a[3] < b[1]) latitudeGap = b[1] - a[3];
  else if (b[3] < a[1]) latitudeGap = a[1] - b[3];
  const meanLatitude = (Math.max(a[1], b[1]) + Math.min(a[3], b[3])) / 2;
  const longitudeGap = longitudeGapDegrees(a, b) * Math.cos((meanLatitude * Math.PI) / 180);
  return Math.hypot(latitudeGap, longitudeGap) * KM_PER_DEGREE;
}

function spanKm(box) {
  const meanLatitude = (box[1] + box[3]) / 2;
  const width = (box[2] - box[0]) * Math.cos((meanLatitude * Math.PI) / 180);
  return Math.hypot(box[3] - box[1], width) * KM_PER_DEGREE;
}

/**
 * Основная территория страны: главный массив суши плюс всё, что образует с ним
 * единый узнаваемый контур. Заморские владения и одиночные скалы отбрасываются —
 * иначе кадр растягивается на полглобуса и сама страна превращается в точку
 * (Франция с Гвианой, Нидерланды с Карибами, Португалия с Азорами, Испания с
 * Канарами, Норвегия со Шпицбергеном, Новая Зеландия с Кермадеком).
 */
export function mainlandWorldGeometry(geometry) {
  const shape = geometry?.geometry;
  if (shape?.type !== 'MultiPolygon' || shape.coordinates.length < 2) return geometry;
  const parts = shape.coordinates
    .map((coordinates) => ({
      coordinates,
      area: geoArea({ type: 'Polygon', coordinates }),
      box: boundingBox(coordinates),
    }))
    .sort((a, b) => b.area - a.area);
  const main = parts[0];
  const nearLimit = Math.max(NEAR_KM, NEAR_SPAN_FACTOR * spanKm(main.box));
  const kept = parts.filter((part, index) => {
    if (index === 0) return true;
    const ratio = main.area > 0 ? part.area / main.area : 1;
    const gap = gapKm(part.box, main.box);
    if (gap <= (ratio < SPECK_AREA_RATIO ? SPECK_NEAR_KM : nearLimit)) return true;
    return ratio >= MAJOR_AREA_RATIO && gap <= FAR_KM;
  });
  if (kept.length === parts.length) return geometry;
  return {
    ...geometry,
    geometry: { type: 'MultiPolygon', coordinates: kept.map((part) => part.coordinates) },
  };
}
