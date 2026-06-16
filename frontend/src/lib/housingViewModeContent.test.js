import { describe, it, expect } from 'vitest';
import { getHousingViewModeContent } from './housingViewModeContent';

const MODES = ['yoy', 'annual', 'qoq', 'index'];
const CODES = ['housing-price-primary', 'housing-price-secondary'];

describe('getHousingViewModeContent', () => {
  it('восемь комбинаций дают непустые уникальные пары description+methodology', () => {
    const seen = new Set();
    for (const code of CODES) {
      for (const chartMode of MODES) {
        const { description, methodology } = getHousingViewModeContent({
          chartMode,
          indicator: { code },
        });
        expect(description.length).toBeGreaterThan(40);
        expect(methodology.length).toBeGreaterThan(80);
        const key = `${description}|||${methodology}`;
        expect(seen.has(key)).toBe(false);
        seen.add(key);
      }
    }
    expect(seen.size).toBe(8);
  });

  it('первичка и вторичка на г/г — разные тексты', () => {
    const primary = getHousingViewModeContent({
      chartMode: 'yoy',
      indicator: { code: 'housing-price-primary' },
    });
    const secondary = getHousingViewModeContent({
      chartMode: 'yoy',
      indicator: { code: 'housing-price-secondary' },
    });
    expect(primary.methodology).toMatch(/первичн/i);
    expect(secondary.methodology).toMatch(/вторичн/i);
    expect(primary.methodology).not.toBe(secondary.methodology);
  });

  it('без внутренностей кода и ИПЦ', () => {
    const { methodology } = getHousingViewModeContent({
      chartMode: 'qoq',
      indicator: { code: 'housing-price-primary' },
    });
    expect(methodology).not.toMatch(/housing-price/);
    expect(methodology).not.toMatch(/потребительск/i);
  });
});
