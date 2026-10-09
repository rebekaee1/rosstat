// Круг 11, зона C: «Отменить последнее», «Поделиться ссылкой», выгрузка CSV/Excel, место для кнопки кабинета,
// отметки событий, подсказка графика в режиме «рост от старта».
import { describe, it, expect, afterEach, vi } from 'vitest';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import ComparePage, { CompareTooltip } from './ComparePage';
import { LocaleProvider } from '../i18n';
import api from '../lib/api';
import { renderPage, mockApiGet } from '../test/renderPage';

vi.mock('../lib/track', async (importOriginal) => {
  const actual = await importOriginal();
  return { ...actual, track: vi.fn(), trackFile: vi.fn() };
});

afterEach(() => vi.restoreAllMocks());

const GDP_NAME = 'Валовой внутренний продукт в текущих ценах';
const CATALOG = {
  items: ['united-states', 'china'].map((slug) => ({
    code: `w:${slug}:gdp-usd`,
    country_slug: slug,
    country_name: slug === 'china' ? 'Китай' : 'США',
    country_name_en: slug === 'china' ? 'China' : 'United States',
    concept_slug: 'gdp-usd',
    concept_name: GDP_NAME,
    frequency: 'annual',
    unit: 'млрд $',
  })),
  total: 2,
};

function seriesFor(url) {
  const [, , , , slug, concept] = url.split('/');
  const found = CATALOG.items.find((it) => it.country_slug === slug && it.concept_slug === concept);
  const base = slug === 'united-states' ? 6000 : 5000;
  return {
    meta: {
      code: found.code, country_slug: slug, country_name: found.country_name, concept_slug: concept, concept_name: found.concept_name, unit: found.unit, frequency: found.frequency,
    },
    data: Array.from({ length: 30 }, (_, i) => ({ date: `${1996 + i}-01-01`, value: base + i * base * 0.05 + ((i * 7) % 5) * 40 })),
  };
}

function mockApis() {
  return mockApiGet([
    ['/auth/me', { user: null }],
    [/^\/indicators/, []],
    ['/regions/catalog', { sections: [] }],
    [/^\/regions/, { districts: [], sections: [] }],
    ['/world/compare/catalog', CATALOG],
    [/^\/world\/compare\/series\//, seriesFor],
    [/^\/world\/[^/]+\/regions$/, { regions: [], indicators: [], sections: [] }],
  ]);
}

const ROUTE = '/compare?codes=w:united-states:gdp-usd,w:china:gdp-usd';
const cards = (container) => container.querySelectorAll('.fe-compare-picked__card');

describe('сравнение: «Отменить последнее» (круг 11)', () => {
  it('убранный ряд возвращается кнопкой «Отменить последнее», об убранном сказано словами', async () => {
    mockApis();
    const { container } = renderPage(<ComparePage />, { path: '/compare', route: ROUTE });
    await waitFor(() => expect(cards(container)).toHaveLength(2));
    expect(screen.queryByTestId('compare-undo')).toBeNull();
    fireEvent.click(within(cards(container)[0]).getByRole('button', { name: 'Убрать' }));
    await waitFor(() => expect(cards(container)).toHaveLength(1));
    expect(screen.getByTestId('compare-status').textContent).toMatch(/Убрали/);
    fireEvent.click(screen.getByTestId('compare-undo'));
    await waitFor(() => expect(cards(container)).toHaveLength(2));
    expect(screen.getByTestId('compare-status').textContent).toMatch(/Вернули прежнее/);
    expect(screen.queryByTestId('compare-undo')).toBeNull();
  });
});

describe('сравнение: ссылка, выгрузка, кнопка кабинета (круг 11)', () => {
  it('«Поделиться ссылкой» копирует обычный адрес с кодами рядов', async () => {
    mockApis();
    const writeText = vi.fn().mockResolvedValue();
    Object.defineProperty(navigator, 'clipboard', { value: { writeText }, configurable: true });
    renderPage(<ComparePage />, { path: '/compare', route: ROUTE });
    fireEvent.click(await screen.findByTestId('compare-share'));
    await waitFor(() => expect(writeText).toHaveBeenCalledTimes(1));
    const url = writeText.mock.calls[0][0];
    expect(url).toMatch(/\?codes=/);
    expect(decodeURIComponent(url)).toContain('w:united-states:gdp-usd,w:china:gdp-usd');
    expect((await screen.findByTestId('compare-action-note')).textContent).toBe('Ссылка скопирована.');
  });

  it('«Скачать данные»: CSV уходит на /export/grid одной таблицей, без lower и upper', async () => {
    mockApis();
    const post = vi.spyOn(api, 'post').mockResolvedValue({ data: new Blob(['x']), headers: {} });
    URL.createObjectURL = vi.fn(() => 'blob:x');
    URL.revokeObjectURL = vi.fn();
    renderPage(<ComparePage />, { path: '/compare', route: ROUTE });
    fireEvent.click(await screen.findByRole('button', { name: /Скачать данные/ }));
    fireEvent.click(await screen.findByRole('menuitem', { name: /Таблица CSV/ }));
    await waitFor(() => expect(post).toHaveBeenCalledTimes(1));
    const [url, body] = post.mock.calls[0];
    expect(url).toBe('/export/grid');
    expect(body.format).toBe('csv');
    expect(body.columns.map((c) => c.key)).toEqual(['date', 'v0', 'v1']);
    expect(body.rows.length).toBeGreaterThan(10);
    expect(body.history.source).toBe('compare');
    expect(JSON.stringify(body)).not.toMatch(/lower|upper/);
  });

  it('место для кнопки кабинета: функция renderSave получает описание сравнения (коды как в адресе)', async () => {
    mockApis();
    const renderSave = vi.fn((spec) => <button type="button" data-testid="fake-save">{spec.kind}</button>);
    renderPage(<ComparePage renderSave={renderSave} />, { path: '/compare', route: ROUTE });
    const button = await screen.findByTestId('fake-save');
    expect(button.textContent).toBe('comparison');
    const spec = renderSave.mock.calls.at(-1)[0];
    expect(spec.itemKey).toBe('w:united-states:gdp-usd,w:china:gdp-usd');
    expect(spec.payload).toEqual({ codes: 'w:united-states:gdp-usd,w:china:gdp-usd' });
    expect(spec.title.length).toBeGreaterThan(0);
  });

  it('без renderSave и на готовом примере кнопки сохранения нет', async () => {
    mockApis();
    renderPage(<ComparePage />, { path: '/compare', route: ROUTE });
    await screen.findByTestId('compare-share');
    expect(screen.queryByTestId('fake-save')).toBeNull();
  });
});

describe('сравнение: отметки событий (круг 11)', () => {
  it('по умолчанию отметок нет; кнопка «События» показывает список событий окна графика', async () => {
    mockApis();
    renderPage(<ComparePage />, { path: '/compare', route: `${ROUTE}` });
    const chip = await screen.findByTestId('chart-events-toggle');
    expect(screen.queryByTestId('chart-events-list')).toBeNull();
    fireEvent.click(chip);
    const list = await screen.findByTestId('chart-events-list');
    expect(list.textContent).toMatch(/Мировой финансовый кризис/);
    expect(list.textContent).not.toMatch(/Распад СССР/);
  });
});

describe('подсказка графика', () => {
  const payload = [
    {
      dataKey: 'v0', name: 'США', value: 877, color: '#2C4A8A', payload: { v0_raw: 30767, v0_rawUnit: 'млрд $', v0_unit: '% от старта' },
    },
    {
      dataKey: 'v1', name: 'Китай', value: 119, color: '#B5675B', payload: { v1_raw: 100, v1_rawUnit: 'млрд $', v1_unit: '% от старта' },
    },
  ];
  const colors = { v0: '#2C4A8A', v1: '#B5675B' };

  it('рост от старта: единица названа один раз в шапке, в строках число и «в 8,8 раза», рядом настоящее значение', () => {
    const { container } = render(
      <LocaleProvider>
        <CompareTooltip active payload={payload} label="2025-01-01" colors={colors} indexed locale="ru" />
      </LocaleProvider>,
    );
    const text = container.textContent;
    expect(text.match(/Рост от старта/g)).toHaveLength(1);
    expect(text).toContain('877');
    expect(text).toContain('в 8,8 раза больше старта');
    expect(text).toMatch(/30\s767/);
    expect(text).toContain('+19');
    expect(text).not.toMatch(/пункт|index points/);
  });

  it('обычный режим: значение с короткой единицей, ширина ограничена', () => {
    const plain = [{ dataKey: 'v0', name: 'США', value: 30767, color: '#2C4A8A', payload: { v0_unit: 'млрд $' } }];
    const { container } = render(
      <LocaleProvider>
        <CompareTooltip active payload={plain} label="2025-01-01" colors={{ v0: '#2C4A8A' }} maxWidth={210} />
      </LocaleProvider>,
    );
    expect(container.textContent).toMatch(/30\s767/);
    expect(container.firstChild.style.maxWidth).toBe('210px');
  });
});
