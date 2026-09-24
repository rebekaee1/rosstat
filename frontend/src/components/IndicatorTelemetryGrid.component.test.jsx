import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { LocaleProvider } from '../i18n';
import IndicatorTelemetryGrid from './IndicatorTelemetryGrid';
vi.mock('./TelemetryCard', () => ({ default: ({ label, value }) => <div>{label}: {value}</div> }));
describe('indicator summary names the displayed transformation', () => {
  it.each(['inflation', 'inflation-quarter', 'inflation-year'])('labels %s as a year-on-year change, not a generic current value', (mode) => {
    render(<LocaleProvider locale="ru"><IndicatorTelemetryGrid indicator={{ frequency: 'monthly', unit: '%' }}
      isPriceCategory chartMode="inflation" safeViewMode={mode}
      viewStats={{ currentValue: 6.34, previousValue: 6, currentDate: '2026-08-01' }} adj={x => x} />
    </LocaleProvider>);
    expect(screen.getByText(/Год к году.*6.34/)).toBeTruthy();
    expect(screen.queryByText(/Текущее значение/)).toBeNull();
  });
});
