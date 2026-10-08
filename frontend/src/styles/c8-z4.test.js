// Круг 8, зона Z4 (Россия, регионы, календарь, страны): стражи раскладки и цвета.
import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';

const read = (name) => readFileSync(new URL(`./${name}`, import.meta.url), 'utf8');
const z5 = read('z5-country.css');
const russia = read('indicator-russia.css');
const regions = read('regions-w4.css');

describe('круг 8 Z4: «Главное» России', () => {
  it('подложки под плитками нет: ни фона, ни тени, ни отступа', () => {
    expect(z5).toMatch(/\.z5-key-grid, \.z5-ru-main \{[^}]*padding: 0;[^}]*background: none;[^}]*box-shadow: none/);
  });

  it('пять в ряд от 1100 px, на планшете 3 + 2 с растяжкой нижних двух, на телефоне одна колонка', () => {
    expect(z5).toMatch(/min-width: 1100px\)\s*\{\s*\.z5-ru-main \{ grid-template-columns: repeat\(5, minmax\(0, 1fr\)\)/);
    expect(z5).toMatch(/\.z5-ru-main \{ grid-template-columns: repeat\(6, minmax\(0, 1fr\)\)/);
    expect(z5).toMatch(/\.z5-ru-main > \.z5-key:nth-child\(5\):last-child \{ grid-column: span 3; \}/);
  });

  it('единица остаётся рядом с числом, график прижат к низу, пустого слота «год назад» нет', () => {
    expect(z5).toMatch(/\.z5-ru-key \.z5-key__value \{ flex-wrap: nowrap; white-space: nowrap; \}/);
    expect(z5).toMatch(/\.z5-ru-key \.z5-key__spark \{[^}]*margin-top: auto/);
    expect(z5).toMatch(/\.z5-ru-key \.z5-key__ago--empty \{ display: none; \}/);
  });
});

describe('круг 8 Z4: календарь и карта регионов', () => {
  it('день календаря: названия только в широкой клетке (container query), плотность дня холодная', () => {
    expect(russia).toMatch(/\.fe-cal-day \{ container-type: inline-size;/);
    expect(russia).toMatch(/@container calday \(min-width: 150px\)/);
    const heat = russia.match(/\.fe-cal-day\[data-heat='[123]'\][^\n]*/g) || [];
    expect(heat).toHaveLength(3);
    for (const line of heat) expect(line).not.toContain('173, 138, 72');
  });

  it('переключатель «Контуры / Пузыри»: активный сегмент графитовый, не золотой', () => {
    expect(regions).toMatch(/\.fe-map-shape button\[aria-pressed='true'\] \{\s*background: var\(--fe-glass-active/);
  });
});
