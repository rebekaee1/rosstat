import { describe, it, expect } from 'vitest';
import {
  getKeyRateViewModeContent,
  getKeyRateChartTitle,
  getKeyRateTableTitle,
  isKeyRateFamily,
} from './keyRateViewModeContent';
import { getViewModeContent } from './cpiViewModeContent';

describe('keyRateViewModeContent', () => {
  it('isKeyRateFamily only for key-rate', () => {
    expect(isKeyRateFamily('key-rate')).toBe(true);
    expect(isKeyRateFamily('ruonia')).toBe(false);
  });

  it('level mode describes step chart', () => {
    const { description, methodology } = getKeyRateViewModeContent({ chartMode: 'level' });
    expect(description).toMatch(/ступенчат|уровень|ключев/i);
    expect(methodology).toMatch(/уровень ставки|рефинансирован/i);
    expect(methodology).not.toMatch(/ИПЦ|потребительск/i);
  });

  it('monthly agg mode describes averaging', () => {
    const { description, methodology } = getKeyRateViewModeContent({ chartMode: 'monthly' });
    expect(description).toMatch(/средн/i);
    expect(methodology).toMatch(/месяц/i);
  });

  it('chart and table titles follow mode', () => {
    expect(getKeyRateChartTitle('level')).toMatch(/Ключевая ставка ЦБ/);
    expect(getKeyRateChartTitle('monthly')).toMatch(/среднее по месяцам/i);
    expect(getKeyRateTableTitle('quarterly')).toMatch(/кварталам/i);
  });

  it('getViewModeContent routes key-rate away from CPI', () => {
    const content = getViewModeContent({
      chartMode: 'level',
      safeViewMode: 'level',
      isPriceCategory: false,
      isHousingFamily: false,
      isPpiFamily: false,
      isAutoLoanFamily: false,
      isCbrTermSliceFamily: false,
      isKeyRateFamily: true,
      indicator: { code: 'key-rate', description: 'fallback' },
    });
    expect(content.methodology).toMatch(/уровень ставки/i);
    expect(content.description).not.toBe('fallback');
  });
});
