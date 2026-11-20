/** @vitest-environment jsdom */
import { describe, expect, it, vi } from 'vitest';
import { render } from '@testing-library/react';
import { LocaleProvider } from '../i18n';

const seen = [];
vi.mock('./TelemetryCard', () => ({ default: (props) => { seen.push(props); return null; } }));

const { default: IndicatorTelemetryGrid } = await import('./IndicatorTelemetryGrid');

const pts = [{ date: '2026-01-01', value: 812.4 }, { date: '2026-04-01', value: 847.69 }];
const digitsFor = (unit) => {
  seen.length = 0;
  render(
    <LocaleProvider locale="ru">
      <IndicatorTelemetryGrid indicator={{ frequency: 'quarterly', unit }} adj={(x) => x} safeViewMode="level" chartMode="level"
        points={pts} viewStats={{ currentValue: 847.69, previousValue: 812.4, currentDate: '2026-04-01', previousDate: '2026-01-01' }} />
    </LocaleProvider>,
  );
  return seen.find((card) => card.delay === 1).valueDigits;
};

describe('плитки: одна точность числа с таблицей и графиком (правки 20 и 38)', () => {
  it('«тыс. поездок» без дроби, как в таблице', () => {
    expect(digitsFor('тыс. поездок')).toBe(0);
  });

  it('рубли и проценты остаются с прежней точностью', () => {
    expect(digitsFor('руб.')).toBe(2);
    expect(digitsFor('%')).toBe(2);
  });
});
