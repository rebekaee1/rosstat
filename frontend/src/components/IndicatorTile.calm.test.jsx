// @vitest-environment jsdom
// Лента раздела «Туризм» (z3): приращение с единицей, без «,00», без цвета и без кружка со стрелкой.
import { describe, expect, it } from 'vitest';
import IndicatorTile from './IndicatorTile';
import { renderPage } from '../test/renderPage';

const base = {
  code: 'tour-test', name: 'Тест', frequency: 'quarterly', category: 'Туризм', is_active: true,
  current_date: '2026-06-30',
};

function tile(over, calm = true) {
  return renderPage(<IndicatorTile indicator={{ ...base, ...over }} surface="category" calm={calm} />).container;
}

describe('IndicatorTile calm', () => {
  it('прирост в миллионах пишется с единицей числа', () => {
    const c = tile({ unit: 'тыс. поездок', current_value: 12140, change: 2140 });
    expect(c.querySelector('.fe-delta-badge').textContent).toMatch(/\+2,14\s*млн/);
  });

  it('у целых без «,00»; тысячи разделены пробелом', () => {
    const c = tile({ unit: 'ед.', current_value: 90, change: 1181 });
    const text = c.querySelector('.fe-delta-badge').textContent;
    expect(text).toMatch(/\+1\s181/);
    expect(text).not.toMatch(/,00/);
  });

  it('цвет смысла не ставится, кружка со стрелкой нет', () => {
    const c = tile({ unit: 'руб.', name: 'Безработица', current_value: 100, change: -5 });
    expect(c.querySelector('.fe-delta-badge').className).toContain('fe-tone--neutral');
    expect(c.querySelector('.fe-tile__go')).toBeNull();
    const other = tile({ unit: 'руб.', current_value: 100, change: -5 }, false);
    expect(other.querySelector('.fe-tile__go')).not.toBeNull();
  });
});
