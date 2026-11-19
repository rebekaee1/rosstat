// 19.11.2026: строка рейтинга стран нажимается целиком.
// Пульс за 30 дней: 24 человека нажимали в число, место, полосу и поля строки таблицы рейтинга стран; ссылкой было
// только название. Область названия растянута на строку (как у рейтинга регионов 18.11, r7c-rank-row.test.js).
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';

const here = dirname(fileURLToPath(import.meta.url));
const css = readFileSync(join(here, 'z6-rating.css'), 'utf8');
const jsx = readFileSync(join(here, '..', 'pages', 'WorldRatingPage.jsx'), 'utf8');

const rule = (selector) => {
  const at = css.indexOf(`${selector} {`);
  expect(at, `правило ${selector}`).toBeGreaterThan(-1);
  return css.slice(at, css.indexOf('}', at));
};

describe('строка рейтинга стран нажимается целиком', () => {
  it('строка — опора для области ссылки: position и transform (Safari не берёт строку опорой по одному position)', () => {
    const row = rule('.z6-table-card tbody .z6-row');
    expect(row).toMatch(/position:\s*relative/);
    expect(row).toMatch(/transform:\s*translate\(0\)/);
    expect(row).toMatch(/cursor:\s*pointer/);
  });

  it('область названия покрывает строку поверх полосы значения', () => {
    const after = rule('.z6-row > td > .z6-row__link::after');
    expect(after).toMatch(/position:\s*absolute/);
    expect(after).toMatch(/inset:\s*0/);
    expect(after).toMatch(/z-index:\s*1/);
  });

  it('фокус с клавиатуры подсвечивает строку', () => {
    expect(rule('.z6-row:has(.z6-row__link:focus-visible) td')).toMatch(/background:/);
  });

  it('разметка: в строке одна ссылка — название страны', () => {
    const start = jsx.indexOf('className="z6-row"');
    const end = jsx.indexOf('</tr>', start);
    expect(start).toBeGreaterThan(-1);
    const row = jsx.slice(start, end);
    expect(row.match(/<Link\b/g)).toHaveLength(1);
    expect(row).toMatch(/<Link to=\{rowHref\(item, \{ conceptSlug: viewSlug, russiaIndicatorCode \}\)\} className="z6-row__link /);
    expect(row).not.toMatch(/<a\b|<button\b/);
  });
});
