// Геометрия стран для карты мира и профиля страны.
//
// Обзорная карта стартует на грубом контуре из основного бандла (105 КБ),
// затем лениво подменяет его на 50m (~740 КБ / ~230 КБ по сети) — иначе
// Скандинавия и Британия выглядят угловато. Карточка страны дополнительно
// может дотянуть 10m для государств-крох.
//
// Уровней подгрузки два. 'detailed' (740 КБ) закрывает обзорную карту и
// почти все карточки. 'fine' (3,6 МБ) — только крохам (Мальта, Кипр, Люксембург).
import { geoArea } from 'd3-geo';
import { feature } from 'topojson-client';
import baseTopology from 'world-atlas/countries-110m.json';

export function numericId(raw) {
  return String(raw).padStart(3, '0');
}

function featuresOf(topology) {
  return feature(topology, topology.objects.countries).features;
}

function indexByNumericId(features) {
  const byId = new Map();
  for (const item of features) {
    const id = numericId(item.id);
    const previous = byId.get(id);
    // Natural Earth вешает один numeric id на страну и на её удалённое
    // владение (036 — и Австралия, и риф Ашмор); берём большую территорию.
    if (previous && geoArea(previous) >= geoArea(item)) continue;
    byId.set(id, item);
  }
  return byId;
}

export const WORLD_FEATURES = featuresOf(baseTopology);
export const WORLD_FEATURE_BY_ID = indexByNumericId(WORLD_FEATURES);

const ATLAS_IMPORT = {
  detailed: () => import('world-atlas/countries-50m.json'),
  fine: () => import('world-atlas/countries-10m.json'),
};

const requests = new Map();

/**
 * Контуры выбранного уровня: Map numericId → feature, либо null, если чанк не
 * догрузился (офлайн, обрыв). Вызывающий код в этом случае остаётся на том, что
 * уже есть — пустого места на карточке быть не должно.
 */
export function loadWorldFeatures(level) {
  if (!requests.has(level)) {
    requests.set(level, ATLAS_IMPORT[level]()
      .then((module) => indexByNumericId(featuresOf(module.default || module)))
      .catch(() => null));
  }
  return requests.get(level);
}
