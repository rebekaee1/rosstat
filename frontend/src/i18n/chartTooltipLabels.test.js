import { describe, expect, it } from 'vitest';
import { translate } from './messages';
import { forecastTooltipLabel, levelTooltipLabel } from './chartTooltipLabels';

const tEn = (key, vars) => translate(key, vars, 'en');
const tRu = (key, vars) => translate(key, vars, 'ru');

describe('chart tooltip labels', () => {
  it('monthly unemployment forecast is EN twin of Прогноз (мес.)', () => {
    const ctx = { chartMode: 'cpi', indicator: { frequency: 'monthly' } };
    expect(forecastTooltipLabel(tRu, ctx)).toBe('Прогноз (мес.)');
    expect(forecastTooltipLabel(tEn, ctx)).toBe('Forecast (mo)');
    expect(forecastTooltipLabel(tEn, ctx)).not.toMatch(/[А-Яа-яЁё]/);
  });

  it('monthly actual series uses Факт / Actual with freq', () => {
    const ctx = { chartMode: 'cpi', indicator: { frequency: 'monthly' } };
    expect(levelTooltipLabel(tRu, ctx)).toBe('Факт (мес.)');
    expect(levelTooltipLabel(tEn, ctx)).toBe('Actual (mo)');
  });
});
