// @vitest-environment jsdom
import { beforeEach, afterEach, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, cleanup, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import IndicatorSearch from './IndicatorSearch';
const localeState = vi.hoisted(() => ({ value: 'ru' }));
const searchState = vi.hoisted(() => ({ data: { results: [], version: 'v2' }, isPending: false, isDebouncing: false, isError: false }));
vi.mock('../lib/useGlobalSearch', () => ({ default: vi.fn(() => searchState) }));
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
  Object.assign(searchState, { data: { results: [], version: 'v2' }, isPending: false, isDebouncing: false, isError: false });
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
it.each([['ru', 'Инфляция в США'], ['en', 'Inflation in the US']])('starts with a titled group of plain-language examples instead of a raw catalogue (%s)', (locale, first) => {
  localeState.value = locale;
  render(<MemoryRouter><IndicatorSearch variant="inline" /></MemoryRouter>);
  fireEvent.click(screen.getByRole('button', { name: 'search.openAria' }));
  expect(screen.getByText('shell.search.popular')).toBeTruthy();
  const options = screen.getAllByRole('option');
  expect(options).toHaveLength(6);
  expect(options[0].textContent).toBe(`shell.search.example.1`);
  expect(first).toBeTruthy();
  // Ни кодов рядов, ни категорий базы: только понятные фразы.
  expect(options.map((row) => row.textContent).join(' ')).not.toMatch(/[a-z]+-[a-z]+_|\//);
});

it('a popular example fills the field and keeps the dialog open instead of navigating away', () => {
  render(<MemoryRouter><IndicatorSearch variant="inline" /></MemoryRouter>);
  fireEvent.click(screen.getByRole('button', { name: 'search.openAria' }));
  fireEvent.click(screen.getAllByRole('option')[2]);
  expect(screen.getByRole('combobox').value).toBe('shell.search.example.3');
  expect(screen.getByRole('dialog')).toBeTruthy();
});

it('keyboard hints are hidden on touch screens and the result rows are large targets', () => {
  render(<MemoryRouter><IndicatorSearch variant="inline" /></MemoryRouter>);
  fireEvent.click(screen.getByRole('button', { name: 'search.openAria' }));
  expect(document.querySelector('.fe-search-kbd').className).toContain('[@media(pointer:coarse)]:hidden');
  expect(screen.getAllByRole('option')[0].className).toContain('min-h-14');
});

it('result rows show place, frequency and unit without internal codes and collapse duplicates', () => {
  searchState.data = {
    version: 'v2',
    results: [
      { key: 'a', kind: 'world', code: 'de-prc_hicp_minr-total-i15', name: 'Гармонизированный индекс потребительских цен', country_name: 'Германия', frequency: 'monthly', unit: 'индекс (2015 = 100)', path: '/germany/indicator/a' },
      { key: 'b', kind: 'world', code: 'de-prc_hicp_midx-cp00-i15', name: 'Гармонизированный индекс потребительских цен', country_name: 'Германия', frequency: 'monthly', unit: 'индекс (2015 = 100)', path: '/germany/indicator/b' },
      { key: 'c', kind: 'world', code: 'de-unemp', name: 'Безработица', country_name: 'Германия', frequency: 'annual', unit: '%', path: '/germany/indicator/c' },
      { key: 'd', kind: 'country', code: 'DE', name: 'Германия', path: '/germany' },
    ],
  };
  render(<MemoryRouter><IndicatorSearch variant="inline" /></MemoryRouter>);
  fireEvent.click(screen.getByRole('button', { name: 'search.openAria' }));
  fireEvent.change(screen.getByRole('combobox'), { target: { value: 'инфляция Германии' } });
  const rows = screen.getAllByRole('option');
  expect(rows).toHaveLength(3);
  const text = rows.map((row) => row.textContent).join('|');
  expect(text).toContain('Германия — shell.freq.monthly, индекс (2015 = 100)');
  expect(text).toContain('Германия — shell.freq.annual, %');
  expect(text).not.toMatch(/prc_hicp|de-unemp|\//);
});

it('nothing found: friendly empty state with tips and examples that refill the field', () => {
  render(<MemoryRouter><IndicatorSearch variant="inline" /></MemoryRouter>);
  fireEvent.click(screen.getByRole('button', { name: 'search.openAria' }));
  fireEvent.change(screen.getByRole('combobox'), { target: { value: 'абвгд' } });
  const empty = screen.getByTestId('search-nothing');
  expect(empty.textContent).toContain('search.nothingFound');
  expect(empty.textContent).toContain('shell.search.tip.spelling');
  fireEvent.click(within(empty).getByRole('button', { name: 'shell.search.example.2' }));
  expect(screen.getByRole('combobox').value).toBe('shell.search.example.2');
});

it('the inline field offers example chips that open the dialog with the query already typed', () => {
  render(<MemoryRouter><IndicatorSearch variant="inline" examples={['Инфляция в США', 'ВВП Китая']} /></MemoryRouter>);
  const chips = screen.getByRole('list', { name: 'shell.search.examplesAria' });
  expect(within(chips).getAllByRole('button')).toHaveLength(2);
  fireEvent.click(within(chips).getByRole('button', { name: 'ВВП Китая' }));
  expect(screen.getByRole('dialog')).toBeTruthy();
  expect(screen.getByRole('combobox').value).toBe('ВВП Китая');
});

it('passes the complete country query to the shared server search and renders its geography', async () => {
  const { default: useGlobalSearch } = await import('../lib/useGlobalSearch');
  searchState.data.results = [{ key: 'de:cpi', kind: 'world', code: 'de-cpi', name: 'Инфляция', country_name: 'Германия', path: '/germany/indicator/de-cpi' }];
  render(<MemoryRouter><IndicatorSearch variant="inline" /></MemoryRouter>);
  fireEvent.click(screen.getByRole('button', { name: 'search.openAria' }));
  fireEvent.change(screen.getByRole('combobox'), { target: { value: 'инфляция Германии' } });
  expect(useGlobalSearch).toHaveBeenLastCalledWith('инфляция Германии', expect.objectContaining({ enabled: true }));
  expect(screen.getByRole('option').textContent).toContain('Германия');
  expect(screen.getByRole('combobox').getAttribute('aria-activedescendant')).toBe(screen.getByRole('option').id);
});

it.each(['isPending', 'isDebouncing'])('does not expose stale clickable results or a zero-result message while %s', (flag) => {
  searchState[flag] = true;
  searchState.data.results = [{ key: 'old', name: 'Old result', path: '/russia' }];
  render(<MemoryRouter><IndicatorSearch variant="inline" /></MemoryRouter>);
  fireEvent.click(screen.getByRole('button', { name: 'search.openAria' }));
  fireEvent.change(screen.getByRole('combobox'), { target: { value: 'новый запрос' } });
  expect(screen.queryByRole('option')).toBeNull();
  expect(screen.getByText('search.loading')).toBeTruthy();
  expect(screen.queryByText('search.nothingFound')).toBeNull();
});

it.each(['isPending', 'isDebouncing'])('shows spinner, progress bar and skeleton rows while %s, and removes them afterwards', (flag) => {
  searchState[flag] = true;
  const { rerender } = render(<MemoryRouter><IndicatorSearch variant="inline" /></MemoryRouter>);
  fireEvent.click(screen.getByRole('button', { name: 'search.openAria' }));
  fireEvent.change(screen.getByRole('combobox'), { target: { value: 'ввп' } });
  expect(screen.getByTestId('search-spinner')).toBeTruthy();
  expect(screen.getByTestId('search-skeleton')).toBeTruthy();
  expect(document.querySelector('.fe-search-progress').getAttribute('data-active')).toBe('true');
  searchState[flag] = false;
  rerender(<MemoryRouter><IndicatorSearch variant="inline" /></MemoryRouter>);
  expect(screen.queryByTestId('search-spinner')).toBeNull();
  expect(screen.queryByTestId('search-skeleton')).toBeNull();
  expect(document.querySelector('.fe-search-progress').getAttribute('data-active')).toBe('false');
});

it('says the connection is slow only after a long wait', async () => {
  searchState.isPending = true;
  render(<MemoryRouter><IndicatorSearch variant="inline" /></MemoryRouter>);
  fireEvent.click(screen.getByRole('button', { name: 'search.openAria' }));
  fireEvent.change(screen.getByRole('combobox'), { target: { value: 'медленно' } });
  expect(screen.queryByTestId('search-slow')).toBeNull();
  expect(await screen.findByTestId('search-slow', {}, { timeout: 4000 })).toBeTruthy();
}, 8000);

it('distinguishes request failure from an empty catalogue match', () => {
  searchState.isError = true;
  searchState.refetch = vi.fn();
  render(<MemoryRouter><IndicatorSearch variant="inline" /></MemoryRouter>);
  fireEvent.click(screen.getByRole('button', { name: 'search.openAria' }));
  fireEvent.change(screen.getByRole('combobox'), { target: { value: 'ВВП' } });
  expect(screen.getByText('search.error')).toBeTruthy();
  fireEvent.click(screen.getByRole('button', { name: 'common.retry' }));
  expect(searchState.refetch).toHaveBeenCalledOnce();
});

it('restores focus to the trigger and wraps keyboard focus within the dialog', () => {
  render(<MemoryRouter><IndicatorSearch variant="inline" /></MemoryRouter>);
  const trigger = screen.getByRole('button', { name: 'search.openAria' });
  trigger.focus();
  fireEvent.click(trigger);
  const input = screen.getByRole('combobox');
  input.focus();
  fireEvent.keyDown(input, { key: 'Tab', shiftKey: true });
  expect(document.activeElement).toBe(screen.getAllByRole('button', { name: 'common.close' })[1]);
  fireEvent.keyDown(document.activeElement, { key: 'Tab' });
  expect(document.activeElement).toBe(input);
  fireEvent.keyDown(document, { key: 'Escape' });
  expect(document.activeElement).toBe(trigger);
});

it('review: composition confirms text without selecting or closing', async () => {
  const { track } = await import('../lib/track'); track.mockClear();
  searchState.data = { results: [{key:'de:cpi',name:'Inflation',path:'/germany/indicator/de-cpi'}], version:'v2' };
  render(<MemoryRouter><IndicatorSearch variant="inline" /></MemoryRouter>);
  fireEvent.click(screen.getByRole('button',{name:'search.openAria'}));
  const input=screen.getByRole('combobox');
  fireEvent.change(input,{target:{value:'inflation'}});
  fireEvent.keyDown(input,{key:'Enter',isComposing:true,keyCode:229});
  expect(screen.getByRole('dialog')).toBeTruthy();
  expect(track).not.toHaveBeenCalled();
  fireEvent.keyDown(document,{key:'Escape',isComposing:true,keyCode:229});
  expect(screen.getByRole('dialog')).toBeTruthy();
  fireEvent.keyDown(input,{key:'Enter'});
  expect(screen.queryByRole('dialog')).toBeNull();
});

it('suspends requests, selectable results and demand telemetry through the complete IME composition', async () => {
  const { default: useGlobalSearch } = await import('../lib/useGlobalSearch');
  const { track } = await import('../lib/track'); track.mockClear();
  searchState.data = { results: [{ key: 'old', name: 'Old result', path: '/russia' }], version: 'federated-v2' };
  render(<MemoryRouter><IndicatorSearch variant="inline" /></MemoryRouter>);
  fireEvent.click(screen.getByRole('button', { name: 'search.openAria' }));
  const input = screen.getByRole('combobox');
  fireEvent.compositionStart(input);
  fireEvent.change(input, { target: { value: 'инфляция Германии' } });
  expect(useGlobalSearch).toHaveBeenLastCalledWith('инфляция Германии', { enabled: false });
  expect(screen.queryByRole('option')).toBeNull();
  fireEvent.keyDown(input, { key: 'Enter' });
  fireEvent.keyDown(document, { key: 'Escape' });
  expect(screen.getByRole('dialog')).toBeTruthy();
  await new Promise(resolve => setTimeout(resolve, 950));
  expect(track).not.toHaveBeenCalled();
  fireEvent.compositionEnd(input, { data: 'Германии' });
  expect(useGlobalSearch).toHaveBeenLastCalledWith('инфляция Германии', { enabled: true });
  expect(input.value).toBe('инфляция Германии');
});

it('explains an unsupported query and associates natural-query help with the input', () => {
  searchState.data = { results: [], reason: 'unsupported_query', version: 'federated-v2' };
  render(<MemoryRouter><IndicatorSearch variant="inline" /></MemoryRouter>);
  fireEvent.click(screen.getByRole('button', { name: 'search.openAria' }));
  const input = screen.getByRole('combobox');
  fireEvent.change(input, { target: { value: '100%' } });
  expect(document.getElementById(input.getAttribute('aria-describedby')).textContent).toBe('search.help');
  expect(screen.getByText('search.unsupportedQuery').closest('[role="status"]').getAttribute('aria-live')).toBe('polite');
  expect(screen.queryByText('search.nothingFound')).toBeNull();
});

it('review: same-query replacement clamps highlight for aria and Enter', () => {
  searchState.data = {results:[0,1,2].map(i=>({key:'r'+i,name:'Result '+i,path:'/russia/indicator/result-'+i})),version:'v2'};
  const view=render(<MemoryRouter><IndicatorSearch variant="inline" /></MemoryRouter>);
  fireEvent.click(screen.getByRole('button',{name:'search.openAria'}));
  const input=screen.getByRole('combobox');
  fireEvent.change(input,{target:{value:'result'}});
  fireEvent.keyDown(input,{key:'ArrowDown'});
  fireEvent.keyDown(input,{key:'ArrowDown'});
  expect(input.getAttribute('aria-activedescendant')).toBe(screen.getAllByRole('option')[2].id);
  searchState.data={results:[{key:'remaining',name:'Remaining',path:'/russia/indicator/remaining'}],version:'v2'};
  view.rerender(<MemoryRouter><IndicatorSearch variant="inline" /></MemoryRouter>);
  expect(screen.getByRole('combobox').getAttribute('aria-activedescendant')).toBe(screen.getByRole('option').id);
  fireEvent.keyDown(screen.getByRole('combobox'),{key:'Enter'});
  expect(screen.queryByRole('dialog')).toBeNull();
});

it('review: query telemetry retains all 100 candidate keys', async () => {
  const { track }=await import('../lib/track'); track.mockClear();
  const results=Array.from({length:100},(_,i)=>({key:'result-'+i,name:'Result '+i,path:'/russia/indicator/result-'+i}));
  searchState.data={results,version:'v2',has_more:true};
  render(<MemoryRouter><IndicatorSearch variant="inline" /></MemoryRouter>);
  fireEvent.click(screen.getByRole('button',{name:'search.openAria'}));
  fireEvent.change(screen.getByRole('combobox'),{target:{value:'result'}});
  await waitFor(()=>expect(track).toHaveBeenCalledWith(undefined,expect.objectContaining({keys:results.map(x=>x.key),returned_count:100,has_more:true})),{timeout:2000});
});
