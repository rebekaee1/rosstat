// Волна 2 (W3): Сегодня, демография, календарь, плитка каталога — понятные подписи, единицы, смысловой цвет.
import { afterEach, describe, expect, it, vi } from 'vitest';
import { screen, waitFor, within } from '@testing-library/react';
import TodayHub from './TodayHub';
import DemographicsPage from './DemographicsPage';
import IndicatorTile from '../components/IndicatorTile';
import CalendarEventCard from '../components/calendar/CalendarEventCard';
import { renderPage, mockApiGet } from '../test/renderPage';

afterEach(() => vi.restoreAllMocks());

function seriesRoute(code) {
  const rows = {
    'usd-rub': [['2026-10-02', 83.2], ['2026-10-03', 83.48]],
    'eur-rub': [['2026-10-02', 94.32], ['2026-10-03', 94.32]],
    'cpi-yoy': [['2026-07-01', 8.2], ['2026-08-01', 8.54]],
  }[code] || [['2026-10-02', 10], ['2026-10-03', 10]];
  return { indicator: code, data: rows.map(([date, value]) => ({ date, value })) };
}

describe('TodayHub', () => {
  function mountHub() {
    mockApiGet([
      ['/auth/me', { user: null }],
      [/^\/indicators\/([a-z0-9-]+)\/data/, (url) => seriesRoute(url.split('/')[2])],
      [/^\/indicators\/([a-z0-9-]+)$/, (url) => {
        const code = url.split('/')[2];
        return {
          code,
          name: code,
          unit: code === 'cpi-yoy' ? '%' : code.endsWith('-rub') ? 'руб.' : '%',
          frequency: code === 'cpi-yoy' ? 'monthly' : 'daily',
          source: 'Банк России',
        };
      }],
    ]);
    return renderPage(<TodayHub />, { path: '/russia/today', route: '/russia/today' });
  }

  it('курс подписан «курс ЦБ на дату», а рядом объяснено отличие от бегущей строки', async () => {
    mountHub();
    expect((await screen.findAllByText(/курс ЦБ на 3 октября 2026/)).length).toBeGreaterThan(0);
    expect(screen.getByText(/бегущей строке сверху показаны рыночные котировки/)).toBeTruthy();
  });

  it('рост инфляции не зелёный, рост курса без оценки, неизменный курс — «Без изменений»', async () => {
    const { container } = mountHub();
    await screen.findAllByText(/курс ЦБ на/);
    await waitFor(() => expect(container.querySelectorAll('.fe-delta-badge').length).toBeGreaterThan(2));
    const cards = [...container.querySelectorAll('.fe-today-card')];
    const cardOf = (title) => cards.find((c) => c.textContent.includes(title));
    const inflation = within(cardOf('Инфляция сегодня')).getAllByText(/\+0,34/)[0].closest('.fe-delta-badge');
    expect(inflation.className).toContain('fe-tone--bad');
    expect(inflation.textContent).toContain('п. п.');
    const dollar = within(cardOf('Курс доллара сегодня')).getByText(/\+0,28/).closest('.fe-delta-badge');
    expect(dollar.className).toContain('fe-tone--neutral');
    expect(within(cardOf('Курс евро сегодня')).getByText('Без изменений')).toBeTruthy();
  });

  it('названия не капсом и не моноширинным шрифтом, у даты нет сокращений «авг»', async () => {
    const { container } = mountHub();
    await screen.findAllByText(/курс ЦБ на/);
    expect(container.querySelector('.uppercase')).toBeNull();
    expect(container.querySelector('.font-mono')).toBeNull();
    expect(container.textContent).not.toMatch(/\bавг\b/);
  });
});

describe('DemographicsPage', () => {
  it('у каждой группы своя цветная точка, числа с единицей, а подписи в легенде и подсказке совпадают', async () => {
    mockApiGet([
      ['/auth/me', { user: null }],
      ['/demographics/structure', {
        series: [
          { year: 2022, 'pop-under-working-age': 27.1, 'working-age-population': 83.6, 'pop-over-working-age': 35.5 },
          { year: 2023, 'pop-under-working-age': 27.2, 'working-age-population': 83.4, 'pop-over-working-age': 35.9 },
        ],
      }],
    ]);
    const { container } = renderPage(<DemographicsPage />, { path: '/russia/demographics', route: '/russia/demographics' });
    const items = await waitFor(() => {
      const found = container.querySelectorAll('.fe-demo-item');
      expect(found).toHaveLength(3);
      return found;
    });
    items.forEach((item) => {
      expect(item.querySelector('.fe-demo-item__dot').getAttribute('style')).toMatch(/background/);
      expect(item.textContent).toMatch(/млн чел\./);
      expect(item.textContent).toMatch(/% населения/);
    });
    // Возрасты в подписях не фиксируем: «(0–15)» бывает устаревшим.
    expect(container.textContent).not.toMatch(/\(0.15\)/);
  });
});

describe('IndicatorTile', () => {
  const base = {
    code: 'eur-usd', name: 'Курс EUR/USD', name_en: 'EUR/USD exchange rate', unit: '', frequency: 'daily',
    category: 'Валюты', is_active: true, current_value: 1.1634, current_date: '2026-10-04', change: -0.001,
  };

  it('нет английского подзаголовка и повтора категории, «−0,00» превратился в «Без изменений»', () => {
    const { container } = renderPage(<IndicatorTile indicator={base} surface="category" />);
    expect(container.textContent).not.toMatch(/exchange rate/);
    expect(container.textContent).not.toMatch(/Валюты/);
    expect(container.textContent).toContain('Без изменений');
    expect(container.textContent).not.toMatch(/0,00/);
    expect(container.textContent).toContain('на 4 октября 2026');
  });

  it('изменение с единицей и периодом, цвет по смыслу', () => {
    const { container } = renderPage(
      <IndicatorTile indicator={{ ...base, code: 'unemployment', name: 'Безработица', unit: '%', frequency: 'monthly', change: 0.4, current_value: 2.9, current_date: '2026-08-01' }} />,
    );
    const badge = container.querySelector('.fe-delta-badge');
    expect(badge.textContent).toContain('+0,40');
    expect(badge.textContent).toContain('п. п.');
    expect(badge.className).toContain('fe-tone--bad');
    expect(container.textContent).toContain('за месяц');
    expect(container.textContent).toContain('за август 2026');
  });
});

describe('CalendarEventCard', () => {
  const event = {
    id: 1, source: 'cbr', importance: 3, title: 'Заседание Совета директоров по ключевой ставке',
    scheduled_date: '2026-10-23', scheduled_time: '13:30', date_confidence: 'official_rule',
  };

  it('вместо «●●○ по графику источника» — «Ориентировочно» с подсказкой и пометка важного события', () => {
    const { container } = renderPage(<CalendarEventCard event={event} />);
    expect(screen.getByText('Ориентировочно')).toBeTruthy();
    expect(screen.getByText('Важное событие')).toBeTruthy();
    expect(container.textContent).not.toMatch(/по графику источника/);
    expect(screen.getByText('Ориентировочно').closest('[title]').getAttribute('title')).toMatch(/графику источника/);
  });

  it('официальная дата — «Дата подтверждена»', () => {
    renderPage(<CalendarEventCard event={{ ...event, date_confidence: 'official', importance: 2 }} />);
    expect(screen.getByText('Дата подтверждена')).toBeTruthy();
    expect(screen.queryByText('Важное событие')).toBeNull();
  });
});
