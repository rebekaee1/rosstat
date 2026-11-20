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
    // Чипов соседних рядов и липкой плашки с числом больше нет.
    expect(screen.queryAllByRole('link')).toHaveLength(0);
    expect(screen.queryByTestId('r6b-sticky')).toBeNull();
  });

  it('сезонный ряд: одно сравнение, с тем же периодом прошлого года, а не с прошлым кварталом', () => {
    const points = [
      { date: '2025-04-01', value: 100 }, { date: '2025-07-01', value: 150 },
      { date: '2026-01-01', value: 60 }, { date: '2026-04-01', value: 104 },
    ];
    const summary = buildIndicatorSummary({ points, frequency: 'quarterly', unit: 'тыс. поездок', locale: 'ru' });
    renderPage(<R6bPulseStrip summary={summary} dateFormat="quarterly" />);
    const text = screen.getByTestId('r6b-delta').textContent;
    expect(text).toMatch(/\+4,0/);
    expect(text).not.toMatch(/73/);
    expect(text).toMatch(/прошлого года/);
  });

  it('при неизменном значении пишет «без изменений»', () => {
    strip([{ date: '2026-08-01', value: 8 }, { date: '2026-09-01', value: 8 }]);
    expect(screen.getByTestId('r6b-delta').textContent).toMatch(/без изменений/i);
  });
});
