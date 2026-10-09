/** @vitest-environment jsdom */
// Сравнение стран на мировой карточке показателя: в режиме «Значения» рисуются ВСЕ выбранные страны
// (раньше линия была только у первой), а при очень разных размерах страница сама показывает проценты.
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, screen, waitFor, within } from '@testing-library/react';
import WorldChartSection from './WorldChartSection';
import { renderPage, mockApiGet } from '../test/renderPage';

vi.mock('../lib/track', async (importOriginal) => {
  const actual = await importOriginal();
  return { ...actual, track: vi.fn() };
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

function series(base, step) {
  return Array.from({ length: 20 }, (_, i) => ({ date: `${2006 + i}-01-01`, value: base + i * step }));
}

const PEERS = [
  { code: 'peer:japan:pop', country_slug: 'japan', country_name: 'Япония', country_code: 'JP', indicator_code: 'jp-pop' },
  { code: 'peer:france:pop', country_slug: 'france', country_name: 'Франция', country_code: 'FR', indicator_code: 'fr-pop' },
  { code: 'peer:china:pop', country_slug: 'china', country_name: 'Китай', country_code: 'CN', indicator_code: 'cn-pop' },
];

const PROPS = {
  code: 'de-pop',
  indicator: { name: 'Население', unit: 'человек', frequency: 'annual', category: 'Демография' },
  modeMeta: { id: 'level-annual', type: 'level', freq: 'annual', unit: 'человек' },
  dataPoints: series(80_000_000, 100_000),
  forecastEnabled: false,
  showForecast: true,
  onToggleForecast: vi.fn(),
  frequency: 'annual',
  unit: 'человек',
  country: { slug: 'germany', name: 'Германия', code: 'DE' },
  conceptSlug: 'population',
  comparisonPeers: PEERS,
  onFullData: vi.fn(),
  onDownloadCsv: vi.fn(),
  onDownloadExcel: vi.fn(),
};

function renderSection() {
  mockApiGet([
    ['/auth/me', { user: null }],
    [/\/world\/indicators\/japan\//, { points: series(125_000_000, -150_000) }],
    [/\/world\/indicators\/france\//, { points: series(62_000_000, 250_000) }],
    [/\/world\/indicators\/china\//, { points: series(1_300_000_000, 5_000_000) }],
  ]);
  return renderPage(<WorldChartSection {...PROPS} />, { path: '/', route: '/' });
}

/** Подписи линий под графиком: у каждой выбранной страны своя строка легенды. */
function legendLabels(container) {
  return [...container.querySelectorAll('span.max-w-\\[14rem\\]')].map((node) => node.textContent);
}

describe('сравнение стран на мировой карточке', () => {
  it('режим «Значения»: на графике все выбранные страны, а не только первая', async () => {
    const { container } = renderSection();
    const compare = container.querySelector('#compare');
    fireEvent.click(within(compare).getByRole('button', { name: 'Япония' }));
    await waitFor(() => expect(legendLabels(container)).toEqual(['Япония']));
    fireEvent.click(within(compare).getByRole('button', { name: 'Франция' }));
    await waitFor(() => expect(legendLabels(container)).toEqual(['Япония', 'Франция']));
    expect(screen.queryByTestId('compare-scale-auto')).toBeNull();
  });

  it('страны разного размера: проценты сами не включаются, есть предложение с объяснением', async () => {
    const { container } = renderSection();
    const compare = container.querySelector('#compare');
    fireEvent.click(within(compare).getByRole('button', { name: 'Китай' }));
    const nudge = await screen.findByTestId('compare-scale-nudge');
    expect(nudge.textContent).toMatch(/в процентах/);
    expect(screen.queryByTestId('compare-scale-auto')).toBeNull();
    // Значения остаются на экране, пока человек не нажал кнопку.
    expect(legendLabels(container)).toEqual(['Китай']);
    fireEvent.click(within(nudge).getByRole('button', { name: 'Показать в процентах' }));
    await waitFor(() => expect(screen.queryByTestId('compare-scale-nudge')).toBeNull());
  });
});
