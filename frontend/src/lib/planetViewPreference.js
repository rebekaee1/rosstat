// Что показывать в окне «планеты» по умолчанию: плоскую карту или объёмный шар.
// Модуль без импортов: его читает и каркас загрузки, и главная до того, как скачан код шара.
export const PLANET_VIEW_KEY = 'fe_planet_view';

/** 'map' по умолчанию; 'globe' только если человек сам выбрал шар (и хранилище работает). */
export function readPlanetViewPreference() {
  try { return window.localStorage.getItem(PLANET_VIEW_KEY) === 'globe' ? 'globe' : 'map'; } catch { return 'map'; }
}

export function writePlanetViewPreference(kind) {
  try { window.localStorage.setItem(PLANET_VIEW_KEY, kind === 'globe' ? 'globe' : 'map'); } catch { /* private mode: выбор живёт до закрытия страницы */ }
}
