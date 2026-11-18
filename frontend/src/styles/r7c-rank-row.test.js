// 18.11.2026: строка рейтинга регионов нажимается целиком.
// Пульс за 17.11: клики в полосу, номер места и поля строки ничего не открывали, хотя строка подсвечивается
// под курсором. Область названия растянута на строку; число остаётся отдельной ссылкой поверх неё.
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';

const here = dirname(fileURLToPath(import.meta.url));
const css = readFileSync(join(here, 'r7c-regions.css'), 'utf8');
const jsx = readFileSync(join(here, '..', 'components', 'regions', 'RegionRanking.jsx'), 'utf8');

const rule = (selector) => {
  const at = css.indexOf(`${selector} {`);
  expect(at, `правило ${selector}`).toBeGreaterThan(-1);
  return css.slice(at, css.indexOf('}', at));
};

describe('строка рейтинга нажимается целиком', () => {
  it('область названия покрывает строку, строка — опора для неё', () => {
    expect(rule(':root:root .fe-rank__row')).toMatch(/position:\s*relative/);
    const after = rule(':root:root .fe-rank__row > .fe-rank__name.fe-rank__link::after');
    expect(after).toMatch(/position:\s*absolute/);
    expect(after).toMatch(/inset:\s*0/);
    // полоса значения сама позиционирована и стоит в разметке позже: без z-index она перекрыла бы область
    expect(after).toMatch(/z-index:\s*1/);
  });

  it('название не становится опорой само: без position и без сжатия при нажатии', () => {
    expect(rule(':root:root .fe-rank__row > .fe-rank__name.fe-rank__link')).toMatch(/position:\s*static/);
    expect(rule(':root:root .fe-rank__row > .fe-rank__name.fe-rank__link:active')).toMatch(/transform:\s*none/);
  });

  it('число — отдельная ссылка поверх области названия', () => {
    const value = rule(':root:root .fe-rank__row > .fe-rank__value.fe-rank__link');
    expect(value).toMatch(/position:\s*relative/);
    expect(value).toMatch(/z-index:\s*2/);
  });

  it('разметка: название и число — прямые потомки строки, каждое со своей ссылкой', () => {
    expect(jsx).toMatch(/<li key=\{row\.slug\} className=\{`fe-rank__row/);
    expect(jsx).toMatch(/<Link to=\{regionPath\(row\.slug\)\} className="fe-rank__name fe-rank__link fe-press">/);
    expect(jsx).toMatch(/className="fe-rank__value fe-rank__link fe-num fe-press"/);
  });
});
