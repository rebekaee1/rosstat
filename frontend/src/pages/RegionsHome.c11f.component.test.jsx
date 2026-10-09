// Круг 11, зона F: карта регионов России. Лучшие и последние десять рядом с картой, сравнение нескольких регионов, скачивание таблицы.
import { afterEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, screen, waitFor, within } from '@testing-library/react';
import RegionsHome from './RegionsHome';
import { mockApiGet, renderPage } from '../test/renderPage';
import * as gridDownload from '../lib/gridDownload';

vi.mock('../components/RegionsMap', () => ({
  default: ({
    pickedSlug, onPickedChange, compareSlugs, onCompareToggle, reserveCard,
  }) => (
    <div data-testid="regions-map" data-picked={pickedSlug || ''} data-reserve={reserveCard ? 'yes' : 'no'}>
      <button type="button" onClick={() => onPickedChange('r1')}>выбрать r1</button>
      {['r1', 'r2', 'r3'].map((slug) => (
        <button key={slug} type="button" onClick={() => onCompareToggle(slug)}>
          {`сравнить ${slug}${compareSlugs.includes(slug) ? ' (в наборе)' : ''}`}
        </button>
      ))}
    </div>
  ),
}));
vi.mock('../components/MapTimeline', () => ({ default: () => null }));
afterEach(() => vi.restoreAllMocks());

const REGIONS = Array.from({ length: 14 }, (_, i) => ({ slug: `r${i + 1}`, name: `Регион ${i + 1}` }));

function heat(code, { unit = '%', lowerBetter = false, base = 1 } = {}) {
  return {
    indicator: { code, name: `Показатель ${code}`, unit },
    year: 2024,
    polarity: lowerBetter ? 'lower_better' : 'neutral',
    default_sort: lowerBetter ? 'asc' : 'desc',
    rank_as_achievement: lowerBetter,
    values: REGIONS.map((r, i) => ({ slug: r.slug, name: r.name, value: base + i, raw: base + i })),
  };
}

function mount({ user = null, route = '/russia/region/map/uroven-bezrabotitsy' } = {}) {
  mockApiGet([
    ['/auth/me', { user }],
    ['/regions', { totals: {}, districts: [{ slug: 'cfo', name: 'ЦФО', regions: REGIONS.map((r) => ({ ...r, stats: {} })) }] }],
    ['/regions/catalog', { sections: [] }],
    [/^\/regions\/heatmap-series\//, () => { throw Object.assign(new Error('no series'), { response: { status: 404 } }); }],
    [/^\/regions\/heatmap\/uroven-bezrabotitsy/, heat('uroven-bezrabotitsy', { lowerBetter: true })],
    [/^\/regions\/heatmap\/chislennost-naseleniya$/, heat('chislennost-naseleniya', { unit: 'чел.', base: 1000 })],
    [/^\/regions\/heatmap\/(.+)/, (url) => heat(url.split('/').pop(), { unit: '₽', base: 50000 })],
  ]);
  renderPage(<RegionsHome />, { path: '*', route });
}

describe('Регионы: лучшие и последние десять рядом с картой', () => {
  it('«меньше — лучше»: лучшие с наименьшим значением, места настоящие, строка выбирает регион на карте', async () => {
    mount();
    const leaders = await screen.findByTestId('region-leaders');
    const best = leaders.querySelector('[data-tone="top"]');
    const worst = leaders.querySelector('[data-tone="bottom"]');
    expect(best.querySelector('.fe-lead__head').textContent).toBe('Лучшие десять');
    expect(worst.querySelector('.fe-lead__head').textContent).toBe('Последние десять');
    // 14 регионов: по семь в каждом списке; самый низкий уровень безработицы (Регион 1) на первом месте.
    expect(best.querySelectorAll('li')).toHaveLength(7);
    const first = best.querySelector('li');
    expect(first.querySelector('.fe-lead__place').textContent).toBe('1');
    expect(first.querySelector('.fe-lead__name').textContent).toBe('Регион 1');
    expect(worst.querySelector('li .fe-lead__name').textContent).toBe('Регион 14');
    expect(worst.querySelector('li .fe-lead__place').textContent).toBe('14');
    fireEvent.click(within(first).getByRole('button'));
    expect(screen.getByTestId('regions-map').getAttribute('data-picked')).toBe('r1');
  });

  it('у величин без оценки (население) первыми стоят наибольшие значения и слова нейтральные', async () => {
    mount({ route: '/russia/region/map/chislennost-naseleniya' });
    const leaders = await screen.findByTestId('region-leaders');
    expect(leaders.querySelector('[data-tone="top"] .fe-lead__head').textContent).toBe('Больше всего');
    expect(leaders.querySelector('[data-tone="top"] .fe-lead__name').textContent).toBe('Регион 14');
    expect(leaders.querySelector('[data-tone="bottom"] .fe-lead__head').textContent).toBe('Меньше всего');
  });

  it('место под карточку выбранного региона занято сразу (страница не прыгает), список лежит в одной сетке с картой', async () => {
    mount();
    await screen.findByTestId('region-leaders');
    expect(screen.getByTestId('regions-map').getAttribute('data-reserve')).toBe('yes');
    const layout = document.querySelector('.fe-map-layout');
    expect(layout.querySelector('#chart')).toBeTruthy();
    expect(layout.querySelector('[data-testid="region-leaders"]')).toBeTruthy();
  });

  it('гость при скачивании таблицы получает окно регистрации, вошедший — файл со всеми регионами', async () => {
    const spy = vi.spyOn(gridDownload, 'downloadGrid').mockResolvedValue({ remaining: null });
    const limit = vi.fn();
    window.addEventListener('fe:download-limit', limit);
    mount();
    const leaders = await screen.findByTestId('region-leaders');
    fireEvent.click(within(leaders).getByRole('button', { name: /Скачать/ }));
    fireEvent.click(within(leaders).getByRole('menuitem', { name: /CSV/ }));
    expect(limit).toHaveBeenCalled();
    expect(spy).not.toHaveBeenCalled();
    window.removeEventListener('fe:download-limit', limit);
  });

  it('вошедшему уходят все 14 регионов по порядку мест, без диапазонов', async () => {
    const spy = vi.spyOn(gridDownload, 'downloadGrid').mockResolvedValue({ remaining: null });
    mount({ user: { id: 1, email: 'u@x.ru', is_admin: false } });
    const leaders = await screen.findByTestId('region-leaders');
    await waitFor(() => expect(within(leaders).getByRole('button', { name: /Скачать/ })).toBeTruthy());
    fireEvent.click(within(leaders).getByRole('button', { name: /Скачать/ }));
    fireEvent.click(within(leaders).getByRole('menuitem', { name: /Excel/ }));
    await waitFor(() => expect(spy).toHaveBeenCalledTimes(1));
    const payload = spy.mock.calls[0][0];
    expect(payload.rows).toHaveLength(14);
    expect(payload.rows[0]).toMatchObject({ rank: 1, region: 'Регион 1' });
    expect(payload.columns.map((c) => c.key)).toEqual(['rank', 'region', 'value']);
    expect(JSON.stringify(payload)).not.toMatch(/lower|upper/i);
  });
});

describe('Регионы: сравнение нескольких регионов', () => {
  it('набор растёт и убывает; с одним регионом таблицы нет, со вторым появляется таблица главных показателей с лучшим в строке', async () => {
    mount();
    await screen.findByTestId('regions-map');
    expect(screen.queryByTestId('region-compare-tray')).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: 'сравнить r1' }));
    const tray = await screen.findByTestId('region-compare-tray');
    expect(tray.textContent).toContain('Регион 1');
    expect(tray.querySelector('table')).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: 'сравнить r3' }));
    await waitFor(() => expect(tray.querySelector('table')).toBeTruthy());
    expect(tray.querySelectorAll('tbody tr')).toHaveLength(6);
    // Зарплата (больше — лучше): лучший Регион 3; безработица (меньше — лучше): лучший Регион 1.
    const rows = [...tray.querySelectorAll('tbody tr')];
    const wageRow = rows.find((tr) => tr.querySelector('th').textContent.includes('Зарплата'));
    await waitFor(() => expect(wageRow.querySelector('td[data-leader="true"]')).toBeTruthy());
    const headers = [...tray.querySelectorAll('thead th')].map((th) => th.textContent);
    expect(headers.slice(1)).toEqual(['Регион 1', 'Регион 3']);
    const winners = rows.map((tr) => [...tr.querySelectorAll('td')].findIndex((td) => td.getAttribute('data-leader') === 'true'));
    expect(winners.filter((index) => index >= 0).length).toBeGreaterThanOrEqual(4);
    // Для двух регионов есть ссылка на подробное сравнение.
    expect(within(tray).getByRole('link', { name: /подробное сравнение/ }).getAttribute('href')).toBe('/russia/region-vs/r1-vs-r3');
    // Убрать из набора крестиком.
    fireEvent.click(within(tray).getByRole('button', { name: /Убрать из сравнения: Регион 3/ }));
    await waitFor(() => expect(tray.querySelector('table')).toBeNull());
    fireEvent.click(within(tray).getByRole('button', { name: 'Очистить' }));
    expect(screen.queryByTestId('region-compare-tray')).toBeNull();
  });

  it('несколько регионов подряд попадают в набор в порядке выбора (предел в пять проверяет lib/regionCompareTable)', async () => {
    mount();
    await screen.findByTestId('regions-map');
    for (const slug of ['r1', 'r2', 'r3']) fireEvent.click(screen.getByRole('button', { name: `сравнить ${slug}` }));
    const tray = await screen.findByTestId('region-compare-tray');
    expect(tray.querySelectorAll('.fe-tray__chip')).toHaveLength(3);
  });
});
