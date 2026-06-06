import { describe, expect, it } from 'vitest';
import {
  getInternationalReservesChartTitle,
  getInternationalReservesViewModeContent,
  isInternationalReservesFamily,
} from './internationalReservesViewModeContent';

describe('internationalReservesViewModeContent', () => {
  it('isInternationalReservesFamily only for international-reserves', () => {
    expect(isInternationalReservesFamily('international-reserves')).toBe(true);
    expect(isInternationalReservesFamily('external-debt')).toBe(false);
  });

  it('chart titles mention reserves and billion USD', () => {
    expect(getInternationalReservesChartTitle('level')).toMatch(/резерв|млрд/i);
    expect(getInternationalReservesChartTitle('annual')).toMatch(/год/i);
  });

  it('content avoids implementation jargon', () => {
    const { description, methodology } = getInternationalReservesViewModeContent({
      chartMode: 'monthly',
    });
    expect(description + methodology).not.toMatch(/parser|bulk_upsert|ADR/i);
    expect(description).toMatch(/резерв|недел|месяц/i);
  });

  it('level content references Bank of Russia', () => {
    const { methodology } = getInternationalReservesViewModeContent({ chartMode: 'level' });
    expect(methodology).toMatch(/Банк России|Банка России/);
  });
});
