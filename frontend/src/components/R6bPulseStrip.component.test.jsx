import { describe, expect, it } from 'vitest';
import { screen } from '@testing-library/react';
import { renderPage } from '../test/renderPage';
import { buildIndicatorSummary } from '../lib/indicatorSummary';
import R6bPulseStrip from './R6bPulseStrip';

// R6-B: на телефоне под названием стоит изменение к прошлому значению и быстрые переходы к связанным показателям.
function strip(points, related = []) {
  const summary = buildIndicatorSummary({ points, frequency: 'monthly', unit: '%', locale: 'ru' });
  return renderPage(
    <R6bPulseStrip summary={summary} dateFormat="monthly" related={related} code="key-rate" category="rates" />,
  );
}

describe('R6bPulseStrip', () => {
  it('показывает изменение и связанные показатели без текущего', () => {
    strip(
      [{ date: '2026-08-01', value: 8.1 }, { date: '2026-09-01', value: 7.6 }],
      [{ code: 'key-rate', name: 'Ключевая ставка' }, { code: 'ruonia', name: 'RUONIA' }],
    );
    expect(screen.getByTestId('r6b-delta')).toBeTruthy();
    expect(screen.getAllByRole('link')).toHaveLength(1);
  });

  it('при неизменном значении пишет «без изменений»', () => {
    strip([{ date: '2026-08-01', value: 8 }, { date: '2026-09-01', value: 8 }]);
    expect(screen.getByTestId('r6b-delta').textContent).toMatch(/без изменений/i);
  });
});
