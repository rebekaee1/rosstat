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
    const inflation = within(cardOf('Инфляция')).getAllByText(/\+0,34/)[0].closest('.fe-delta-badge');
    expect(inflation.className).toContain('fe-tone--bad');
    // Волна 6: «п. п.» заменено словами, слово «сегодня» ушло с карточек (дата стоит рядом с числом).
    expect(inflation.textContent.replace(/\u00a0/g, ' ')).toContain('процентного пункта');
    // Единица не рвётся на три строки: слова «процентного пункта» связаны неразрывным пробелом.
    expect(inflation.textContent).toContain('процентного\u00a0пункта');
    expect(inflation.textContent).not.toContain('п. п.');
    expect(cardOf('Инфляция').textContent).not.toMatch(/сегодня/);
    const dollar = within(cardOf('Курс доллара')).getByText(/\+0,28/).closest('.fe-delta-badge');
    expect(dollar.className).toContain('fe-tone--neutral');
    expect(within(cardOf('Курс евро')).getByText('Без изменений')).toBeTruthy();
    // Подпись «График →» на каждой карточке показывает, что она ведёт на график.
    expect(within(cardOf('Курс доллара')).getByText('График →')).toBeTruthy();
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
    // Дата склеена неразрывными пробелами: «2026» не остаётся одиноким на второй строке.
    expect(container.textContent).toContain('на\u00A04\u00A0октября\u00A02026');
  });

  it('изменение с единицей и периодом, цвет по смыслу', () => {
    const { container } = renderPage(
      <IndicatorTile indicator={{ ...base, code: 'unemployment', name: 'Безработица', unit: '%', frequency: 'monthly', change: 0.4, current_value: 2.9, current_date: '2026-08-01' }} />,
    );
    const badge = container.querySelector('.fe-delta-badge');
    expect(badge.textContent).toContain('+0,40');
    // R6-B: в плитке короткая единица «п. п.», без длинных слов.
    expect(badge.textContent.replace(/\u00a0/g, ' ')).toContain('п. п.');
    expect(badge.className).toContain('fe-tone--bad');
    expect(container.textContent).toContain('за месяц');
    expect(container.textContent).toContain('за\u00A0август\u00A02026');
  });
});

describe('CalendarEventCard', () => {
  // Дата в будущем: статус прошедшего события другой («Вышло», «Ждём данные», «Дата прошла»).
  const event = {
    id: 1, source: 'cbr', importance: 3, title: 'Заседание Совета директоров по ключевой ставке',
    scheduled_date: '2099-10-23', scheduled_time: '13:30', date_confidence: 'official_rule',
  };

  it('ежедневное правило источника — «По графику» с подсказкой и пометка важного события', () => {
    const { container } = renderPage(<CalendarEventCard event={event} />);
    expect(screen.getByText('По графику')).toBeTruthy();
    expect(screen.getByText('Важное событие')).toBeTruthy();
    expect(container.textContent).not.toMatch(/Ориентировочно/);
    expect(screen.getByText('По графику').closest('[title]').getAttribute('title')).toMatch(/каждый рабочий день/);
  });

  it('официальная дата — «Дата подтверждена»', () => {
    renderPage(<CalendarEventCard event={{ ...event, date_confidence: 'official', importance: 2 }} />);
    expect(screen.getByText('Дата подтверждена')).toBeTruthy();
    expect(screen.queryByText('Важное событие')).toBeNull();
  });

  it('прошедшее событие с цифрой — «Вышло», перенесённое — «Перенесено с …»', () => {
    renderPage(<CalendarEventCard event={{ ...event, scheduled_date: '2026-10-23', status: 'released', actual_value: '14' }} />);
    expect(screen.getByText('Вышло')).toBeTruthy();
    renderPage(<CalendarEventCard event={{ ...event, date_confidence: 'official_explicit', rescheduled_from: '2099-10-13' }} />);
    expect(screen.getByText(/Перенесено с 13 октября/)).toBeTruthy();
  });

  it('мировой выпуск ведёт на карточку ряда страны, прогноз подписан «Прогноз Forecast Economy»', () => {
    const { container } = renderPage(<CalendarEventCard event={{
      id: 9, source: 'bea', importance: 2, title: 'США: ВВП (вторая оценка)', scheduled_date: '2099-11-25',
      date_confidence: 'official_explicit', reference_period: 'Q3 2099', country: 'США',
      link_path: '/united-states/us-gdp-real-growth', previous_value: '2,1', forecast_value: '2,5',
    }} />);
    expect(container.querySelector('a[href="/united-states/us-gdp-real-growth"]')).toBeTruthy();
    expect(screen.getByText('Бюро экономического анализа США')).toBeTruthy();
    expect(screen.getByText('Прогноз Forecast Economy')).toBeTruthy();
  });
});

