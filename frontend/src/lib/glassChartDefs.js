// Общие градиенты «стеклянной ленты» для графиков других зон (класс .k4-glass в styles/k4-charts.css).
// Один скрытый SVG на страницу: правила CSS ссылаются на градиенты как stroke: url(#fe-glass-ribbon).
// Скрыт не через display:none (в нём градиенты не работают), а нулевым размером и позиционированием вне потока.
// Модуль безопасен без браузера (сборка, тесты без DOM): тогда ничего не делает. Значения те же, что в lib/chartTheme.js.
import {
  CHART_AREA, CHART_AREA_COLOR, RIBBON_STOPS, SAPPHIRE_STOPS,
} from './chartTheme';

export const GLASS_DEFS_ID = 'fe-glass-defs';

function stopsMarkup(stops) {
  return stops.map((stop) => `<stop offset="${stop.offset}" stop-color="${stop.color}"/>`).join('');
}

export function glassDefsMarkup() {
  return `<defs>
<linearGradient id="fe-glass-ribbon" x1="0" y1="0" x2="1" y2="0">${stopsMarkup(RIBBON_STOPS)}</linearGradient>
<linearGradient id="fe-glass-sapphire" x1="0" y1="0" x2="1" y2="0">${stopsMarkup(SAPPHIRE_STOPS)}</linearGradient>
<linearGradient id="fe-glass-area" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stop-color="${CHART_AREA_COLOR}" stop-opacity="${CHART_AREA.top}"/><stop offset="100%" stop-color="${CHART_AREA_COLOR}" stop-opacity="${CHART_AREA.bottom}"/></linearGradient>
</defs>`;
}

/** Создаёт скрытый SVG с градиентами, если его ещё нет. Возвращает true, если элемент есть после вызова. */
export function ensureGlassDefs(doc = typeof document !== 'undefined' ? document : null) {
  if (!doc || !doc.body) return false;
  if (doc.getElementById(GLASS_DEFS_ID)) return true;
  const svg = doc.createElementNS('http://www.w3.org/2000/svg', 'svg');
  svg.setAttribute('id', GLASS_DEFS_ID);
  svg.setAttribute('width', '0');
  svg.setAttribute('height', '0');
  svg.setAttribute('aria-hidden', 'true');
  svg.setAttribute('focusable', 'false');
  svg.style.position = 'absolute';
  svg.style.pointerEvents = 'none';
  svg.innerHTML = glassDefsMarkup();
  doc.body.appendChild(svg);
  return true;
}

ensureGlassDefs();
