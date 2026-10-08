/** @vitest-environment jsdom */
// Круг 8, C1/C2: у ряда один цвет во всех местах страницы, а цвета двух первых рядов заметно разные.
import { describe, it, expect, afterEach, vi } from 'vitest';
import { screen } from '@testing-library/react';
import ComparePage from './ComparePage';
import { renderPage, mockApiGet } from '../test/renderPage';
import { COMPARE_COLORS, mixWithWhite, ribbonStopsFor } from '../lib/chartTheme';

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
    expect(legend).toEqual([toRgb(COMPARE_COLORS[0]), toRgb(COMPARE_COLORS[1])]);
    expect(beads.map((b) => b.toLowerCase())).toEqual([COMPARE_COLORS[0].toLowerCase(), COMPARE_COLORS[1].toLowerCase()]);
  });
});

describe('палитра сравнения', () => {
  it('два первых цвета различимы по тону и светлоте, золота нет', () => {
    const [a, b] = COMPARE_COLORS;
    expect(Math.abs(lightness(a) - lightness(b))).toBeGreaterThan(40);
    expect(COMPARE_COLORS.slice(0, 2).every((c) => !/^#(E|D|C|B|A)/i.test(c))).toBe(true);
  });

  it('лента строится из цвета ряда и у правого конца равна ему', () => {
    COMPARE_COLORS.slice(0, 2).forEach((color) => {
      const stops = ribbonStopsFor(color);
      expect(stops[stops.length - 1].color).toBe(color);
      expect(stops[0].color).toBe(mixWithWhite(color, 0.42));
    });
  });
});
