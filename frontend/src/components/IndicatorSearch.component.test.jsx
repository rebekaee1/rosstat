// @vitest-environment jsdom
import { beforeEach, afterEach, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, cleanup } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import IndicatorSearch from './IndicatorSearch';
const localeState = vi.hoisted(() => ({ value: 'ru' }));
vi.mock('../lib/hooks', () => ({ useIndicators: () => ({ data: [] }) }));
vi.mock('../lib/worldApi', () => ({
  useWorldSearch: () => ({ data: null, isPending: false }),
  useWorldCompareCatalog: () => ({
    data: { items: [
      { country_slug: 'united-states', indicator_code: 'us-gdp', concept_name: 'GDP', concept_name_en: 'GDP', country_name_en: 'United States' },
      { country_slug: 'russia', indicator_code: 'gdp', concept_name: 'ВВП', concept_name_en: 'GDP', country_name_en: 'Russia' },
    ] },
    isPending: false,
  }),
  WORLD_GLOBAL_SEARCH_LIMIT: 50,
}));
vi.mock('../lib/track', () => ({ track: vi.fn(), events: {} }));
vi.mock('../i18n', () => ({ useT: () => key => key, useLocale: () => ({ locale: localeState.value }) }));
beforeEach(() => {
  localeState.value = 'ru';
  HTMLElement.prototype.scrollIntoView = vi.fn();
  // jsdom has no layout. Simulate actual browser rects, including hidden parents.
  vi.spyOn(HTMLElement.prototype, 'getClientRects').mockImplementation(function () {
    return this.closest('[data-hidden]') ? [] : [{ width: 100, height: 30 }];
  });
});
afterEach(() => { cleanup(); vi.restoreAllMocks(); });
function mount() {
  render(<MemoryRouter><div data-hidden><IndicatorSearch variant="icon" /></div><div data-testid="desktop"><IndicatorSearch variant="pill" /></div><div data-testid="inline"><IndicatorSearch variant="inline" /></div></MemoryRouter>);
}
for (const shortcut of [{ key: 'k', metaKey: true }, { key: 'k', ctrlKey: true }, { key: '/' }]) {
  it(`opens exactly one portal for ${JSON.stringify(shortcut)} with hidden-first and inline instances`, () => {
    mount();
    fireEvent.keyDown(document, shortcut);
    expect(screen.getAllByRole('dialog')).toHaveLength(1);
    // Inspect owner state through toggle: it must close, not open a second instance.
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(screen.queryAllByRole('dialog')).toHaveLength(0);
  });
}
it('click on inline works; shortcut closes that owner instead of opening Navbar dialog', () => {
  mount();
  fireEvent.click(screen.getByTestId('inline').querySelector('button'));
  expect(screen.getAllByRole('dialog')).toHaveLength(1);
  fireEvent.keyDown(document, { key: 'k', metaKey: true });
  expect(screen.queryAllByRole('dialog')).toHaveLength(0);
});
it('does not steal an already claimed shortcut', () => {
  const claim = event => event.preventDefault();
  document.addEventListener('keydown', claim);
  mount(); fireEvent.keyDown(document, { key: 'k', metaKey: true });
  expect(screen.queryAllByRole('dialog')).toHaveLength(0);
  document.removeEventListener('keydown', claim);
});
it('slash does not interrupt typing in an input', () => {
  mount();
  const input = document.createElement('input'); document.body.append(input); input.focus();
  fireEvent.keyDown(input, { key: '/' });
  expect(screen.queryAllByRole('dialog')).toHaveLength(0);
  input.remove();
});
it('a mounted hidden trigger cannot open a portal by keyboard', () => {
  render(<MemoryRouter><div data-hidden><IndicatorSearch /></div></MemoryRouter>);
  fireEvent.keyDown(document, { key: 'k', metaKey: true });
  fireEvent.keyDown(document, { key: '/' });
  expect(screen.queryAllByRole('dialog')).toHaveLength(0);
});
it('starts an empty English search with US indicators and no Russian default results', () => {
  localeState.value = 'en';
  render(<MemoryRouter><IndicatorSearch variant="inline" /></MemoryRouter>);
  fireEvent.click(screen.getByRole('button', { name: 'search.openAria' }));
  expect(screen.getAllByRole('option')).toHaveLength(1);
  expect(screen.getByRole('option').textContent).toContain('United States');
});
