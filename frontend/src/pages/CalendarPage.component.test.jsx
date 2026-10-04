import { describe, it, expect, afterEach, vi } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import CalendarPage from './CalendarPage';
import { renderPage, mockApiGet } from '../test/renderPage';
import api from '../lib/api';

afterEach(() => vi.restoreAllMocks());

function render(locale, route = '/calendar/2031/05') {
  return renderPage(<CalendarPage fixedYear={2031} fixedMonth={4} seoPath="/calendar/2031/05" />, {
    path: '/calendar/:year/:month',
    route,
    locale,
  });
}

describe('CalendarPage: видимые состояния', () => {
  it('пустой месяц: заголовок и подсказка, не пустой экран (ru)', async () => {
    mockApiGet([
      [/^\/calendar\?/, { events: [], total: 0 }],
      [/^\/calendar\/upcoming/, { events: [] }],
    ]);
    render('ru');
    expect(await screen.findByText('Нет событий в этом месяце')).toBeTruthy();
    expect(screen.getByText('Попробуйте другой месяц или сбросьте фильтр источника')).toBeTruthy();
    expect(screen.getByTestId('calendar-empty').getAttribute('role')).toBe('status');
  });

  it('пустой месяц на английском', async () => {
    mockApiGet([
      [/^\/calendar\?/, { events: [], total: 0 }],
      [/^\/calendar\/upcoming/, { events: [] }],
    ]);
    render('en');
    expect(await screen.findByText('No events this month')).toBeTruthy();
  });

  it('ошибка загрузки: баннер с повтором, без ложного «нет событий» (ru и en)', async () => {
    for (const [locale, title] of [['ru', 'Календарь временно недоступен.'], ['en', 'The calendar is temporarily unavailable.']]) {
      vi.restoreAllMocks();
      vi.spyOn(api, 'get').mockImplementation((url) => {
        const err = new Error(`fail ${url}`);
        err.response = { status: 500 };
        return Promise.reject(err);
      });
      const { unmount } = render(locale);
      await waitFor(() => expect(screen.getByRole('alert').textContent).toContain(title));
      expect(screen.queryByTestId('calendar-empty')).toBeNull();
      unmount();
    }
  });
});
