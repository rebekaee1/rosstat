import { describe, it, expect } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import WeeklyPrices from './WeeklyPrices';
import { LocaleProvider } from '../../i18n';
import { kopText, pointOn, weeklyRows } from '../../lib/weeklyPrice';

// Санкт-Петербург, дизельное топливо: записи Росстата вокруг Нового года (ЕМИСС 37426, живой прогон 18.11.2026).
const SPB = [
  { date: '2025-12-15', value: 75.73 },
  { date: '2025-12-22', value: 75.83 },
  { date: '2026-01-12', value: 77.21 },
];
const RF = [
  { date: '2025-12-22', value: 75.83 },
  { date: '2026-01-12', value: 76.9 },
];

const wrap = (ui) => render(<LocaleProvider>{ui}</LocaleProvider>);

describe('weeklyPrice', () => {
  it('цена на день — последняя запись не позже него', () => {
    expect(pointOn(SPB, '2026-01-01')).toEqual(SPB[1]);
    expect(pointOn(SPB, '2026-01-12')).toEqual(SPB[2]);
    expect(pointOn(SPB, '2020-01-01')).toEqual(SPB[0]);
    expect(pointOn(SPB, '')).toEqual(SPB[2]);
    expect(pointOn([], '2026-01-01')).toBeNull();
  });

  it('копейки не теряются, строки таблицы — новые сверху с Россией', () => {
    expect(kopText(75.8, 'ru')).toMatch(/^75,80\s₽$/);
    expect(kopText(75.8, 'en')).toMatch(/^75\.80\s₽$/);
    const rows = weeklyRows(SPB, RF);
    expect(rows.map((r) => r.date)).toEqual(['2026-01-12', '2025-12-22', '2025-12-15']);
    expect(rows[2].russia).toBeNull();
  });
});

describe('WeeklyPrices', () => {
  it('без выбора — последняя запись; «на 01.01.2026» — запись 22 декабря и Россия в тот же день', () => {
    const { container } = wrap(
      <WeeklyPrices weekly={SPB} weeklyRussia={RF} regionName="г. Санкт-Петербург" subject="region:sankt-peterburg:ceni-dt" />,
    );
    expect(screen.getByRole('heading', { name: 'Цена на дату' })).toBeTruthy();
    expect(container.querySelector('.fw-answer__value').textContent).toMatch(/77,21/);
    expect(container.querySelector('.fw-answer__date').textContent).toBe('на 12 января 2026');

    fireEvent.change(container.querySelector('input[type="date"]'), { target: { value: '2026-01-01' } });
    expect(container.querySelector('.fw-answer__value').textContent).toMatch(/75,83/);
    expect(container.querySelector('.fw-answer__date').textContent).toBe('на 22 декабря 2025');
    expect(container.querySelector('.fw-answer__rf').textContent).toMatch(/75,83/);
    expect(container.querySelector('.fw-answer__note').textContent).toMatch(/1 января 2026/);
  });

  it('таблица раскрывается, выбранная запись подсвечена; у России нет колонки «Россия»', () => {
    const { container } = wrap(
      <WeeklyPrices weekly={SPB} weeklyRussia={[]} regionName="Российская Федерация" isRussia subject="region:russia:ceni-dt" />,
    );
    const toggle = screen.getByRole('button', { name: /Все недельные цены \(3\)/ });
    expect(toggle.getAttribute('aria-expanded')).toBe('false');
    fireEvent.click(toggle);
    const heads = [...container.querySelectorAll('th')].map((n) => n.textContent);
    expect(heads).toEqual(['Дата записи', 'Российская Федерация']);
    expect(container.querySelector('tr[aria-current="true"] td').textContent).toBe('12 января 2026');
    expect(container.querySelector('.fw-answer__rf')).toBeNull();
  });
});
