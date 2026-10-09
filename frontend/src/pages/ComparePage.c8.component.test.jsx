/** @vitest-environment jsdom */
// Круг 8, C1/C2: у ряда один цвет во всех местах страницы, а цвета двух первых рядов заметно разные.
import { describe, it, expect, afterEach, vi } from 'vitest';
import { screen } from '@testing-library/react';
import ComparePage from './ComparePage';
import { renderPage, mockApiGet } from '../test/renderPage';
import { COMPARE_COLORS, COMPARE_SERIES_COLORS, ribbonStopsFor } from '../lib/chartTheme';

vi.mock('../lib/track', async (importOriginal) => {
  const actual = await importOriginal();
  return { ...actual, track: vi.fn() };
});

afterEach(() => vi.restoreAllMocks());

const GDP = 'Валовой внутренний продукт в текущих ценах';
function item(slug, country) {
  return {
    code: `w:${slug}:gdp-usd`, country_slug: slug, country_name: country, concept_slug: 'gdp-usd', concept_name: GDP, frequency: 'annual', unit: 'млрд $',
  };
}
const CATALOG = { items: [item('united-states', 'США'), item('china', 'Китай')], total: 2 };

function seriesFor(url) {
  const slug = url.split('/')[4];
  const found = CATALOG.items.find((it) => it.country_slug === slug);
  const base = slug === 'china' ? 18000 : 29000;
  return {
    meta: { code: found.code, country_slug: slug, country_name: found.country_name, concept_slug: 'gdp-usd', concept_name: GDP, unit: 'млрд $', frequency: 'annual' },
    data: [{ date: '2022-01-01', value: base }, { date: '2023-01-01', value: base * 1.02 }, { date: '2024-01-01', value: base * 1.05 }],
  };
}

function lightness(hex) {
  const n = parseInt(hex.slice(1), 16);
  return 0.2126 * ((n >> 16) & 255) + 0.7152 * ((n >> 8) & 255) + 0.0722 * (n & 255);
}

describe('ComparePage: цвета рядов (круг 8)', () => {
  it('легенда, бусины бейджа и точки итогов берут один и тот же цвет ряда', async () => {
    mockApiGet([
      ['/auth/me', { user: null }],
      [/^\/indicators/, []],
      ['/regions/catalog', { sections: [] }],
      [/^\/regions/, { districts: [], sections: [] }],
      ['/world/compare/catalog', CATALOG],
      [/^\/world\/compare\/series\//, seriesFor],
      [/^\/world\/[^/]+\/regions$/, { regions: [], indicators: [], sections: [] }],
    ]);
    const { container } = renderPage(<ComparePage />, { path: '/compare', route: '/compare' });
    await screen.findByTestId('compare-gap');
    const legend = [...container.querySelectorAll('.fe-compare-legend > span > span:first-child')]
      .map((el) => el.style.backgroundColor);
    const beads = [...container.querySelectorAll('.fe-compare-gap__beads i')].map((el) => el.style.getPropertyValue('--bead'));
    const toRgb = (hex) => {
      const n = parseInt(hex.slice(1), 16);
      return `rgb(${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255})`;
    };
    expect(legend).toEqual([toRgb(COMPARE_SERIES_COLORS[0]), toRgb(COMPARE_SERIES_COLORS[1])]);
    expect(beads.map((b) => b.toLowerCase())).toEqual([COMPARE_SERIES_COLORS[0].toLowerCase(), COMPARE_SERIES_COLORS[1].toLowerCase()]);
  });
});

describe('палитра сравнения', () => {
  it('два первых цвета различимы по тону и светлоте, золота нет', () => {
    const [a, b] = COMPARE_COLORS;
    expect(Math.abs(lightness(a) - lightness(b))).toBeGreaterThan(40);
    expect(COMPARE_COLORS.slice(0, 2).every((c) => !/^#(E|D|C|B|A)/i.test(c))).toBe(true);
  });

  it('круг 11: первые пять цветов рядов различимы по тону (Китай и Россия не одного бирюзового оттенка)', () => {
    const hue = (hex) => {
      const n = parseInt(hex.slice(1), 16);
      const [r, g, b] = [(n >> 16) & 255, (n >> 8) & 255, n & 255].map((v) => v / 255);
      const max = Math.max(r, g, b);
      const min = Math.min(r, g, b);
      if (max === min) return 0;
      const d = max - min;
      let h;
      if (max === r) h = ((g - b) / d) % 6;
      else if (max === g) h = (b - r) / d + 2;
      else h = (r - g) / d + 4;
      return ((h * 60) + 360) % 360;
    };
    const first = COMPARE_SERIES_COLORS.slice(0, 4);
    expect(new Set(first).size).toBe(4);
    for (let i = 0; i < first.length; i += 1) {
      for (let j = i + 1; j < first.length; j += 1) {
        const diff = Math.abs(hue(first[i]) - hue(first[j]));
        expect(Math.min(diff, 360 - diff)).toBeGreaterThan(25);
      }
    }
    expect(COMPARE_SERIES_COLORS.some((c) => /^#(?:F|E|D)[0-9A-F]{5}$/i.test(c) && hue(c) > 35 && hue(c) < 65)).toBe(false);
  });

  it('лента строится из цвета ряда и одного цвета по всей длине (круг 10, Г1: без «двойной линии»)', () => {
    COMPARE_COLORS.slice(0, 2).forEach((color) => {
      const stops = ribbonStopsFor(color);
      expect(stops[stops.length - 1].color).toBe(color);
      expect(stops[0].color).toBe(color);
    });
  });
});
