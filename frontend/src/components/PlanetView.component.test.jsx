import { useEffect } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter, useLocation } from 'react-router-dom';
import PlanetView from './PlanetView';

const scene = vi.hoisted(() => ({ fail: false, props: null, locale: 'ru' }));

vi.mock('../i18n', () => ({
  useT: () => (key, vars) => (vars?.count == null ? key : `${key}: ${vars.count}`),
  useLocale: () => ({ locale: scene.locale }),
}));
vi.mock('./PlanetScene', () => ({
  default: function MockPlanetScene(props) {
    scene.props = props;
    const { onReady, onError } = props;
    useEffect(() => {
      if (scene.fail) onError(new Error('No WebGL'));
      else onReady();
    }, [onError, onReady]);
    return <div data-testid="planet-scene"><button type="button" onClick={() => props.onSelect('DE')}>Pick Germany</button><button type="button" onClick={() => props.onSelect('ZZ')}>Pick unavailable country</button></div>;
  },
}));
vi.mock('./WorldMap', () => ({
  default: (props) => <div data-testid="fallback-map"><button type="button" onClick={() => props.onSelect(props.countries[0], props.detailsByCode?.get(props.countries[0]?.code))}>Select on map</button></div>,
}));

const countries = [
  { code: 'DE', slug: 'germany', name: 'Германия', name_en: 'Germany' },
  { code: 'MT', slug: 'malta', name: 'Мальта', name_en: 'Malta' },
];
const germanyDetail = { country_code: 'DE', country_slug: 'germany', date: '2026-06-01', value: 3.2, indicator_code: 'de-labour-survey-rate' };
const maltaDetail = { country_code: 'MT', country_slug: 'malta', date: '2026-06-01', value: 1.7, indicator_code: 'mt-national-jobless-rate' };

function countryList() {
  return within(screen.getByRole('group', { name: 'planet.countries' }));
}

function selectListCountry(name) {
  fireEvent.click(countryList().getByRole('button', { name: new RegExp(name) }));
}

beforeEach(() => {
  scene.fail = false;
  scene.props = null;
  scene.locale = 'ru';
});
afterEach(() => vi.restoreAllMocks());

describe('PlanetView interaction contract', () => {
  it('starts in Earth and selects a country before opening its actual row', async () => {
    const onSelect = vi.fn();
    const { container } = render(<PlanetView countries={countries} detailsByCode={new Map([['DE', germanyDetail]])} valuesByCode={new Map([['DE', 3.2]])} metricName="Безработица" unit="%" onSelect={onSelect} />);
    fireEvent.click(await screen.findByRole('button', { name: 'Pick Germany' }));
    expect(scene.props.mode).toBe('earth');
    expect(container.querySelector('[data-scene-ready="true"]')).toBeTruthy();
    expect(container.querySelector('[data-selected-country="DE"]')).toBeTruthy();
    expect(screen.getByText('июнь 2026')).toBeTruthy();
    expect(onSelect).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: 'planet.openIndicator' }));
    expect(onSelect).toHaveBeenCalledWith(countries[0], germanyDetail);
  });

  it('selects from the ranking without navigation, preserves selection on overview and clears it explicitly', async () => {
    const onSelect = vi.fn();
    const { container } = render(<PlanetView countries={countries} valuesByCode={{ DE: 3.2, MT: 1.7 }} detailsByCode={{ DE: germanyDetail }} onSelect={onSelect} />);
    await screen.findByTestId('planet-scene');
    selectListCountry('Германия');
    expect(scene.props.selectedCode).toBe('DE');
    expect(countryList().getByRole('button', { name: /Германия/ }).getAttribute('aria-pressed')).toBe('true');
    expect(onSelect).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole('button', { name: 'planet.reset' }));
    expect(scene.props.cameraCommand.type).toBe('reset');
    expect(scene.props.selectedCode).toBe('DE');
    expect(container.querySelector('[data-selected-country="DE"]')).toBeTruthy();

    const clear = screen.getByRole('button', { name: 'planet.clearSelection' });
    act(() => clear.focus());
    fireEvent.click(clear);
    expect(scene.props.selectedCode).toBeNull();
    expect(countryList().getByRole('button', { name: /Германия/ }).getAttribute('aria-pressed')).toBe('false');
    expect(screen.queryByRole('button', { name: 'planet.openIndicator' })).toBeNull();
    expect(document.activeElement).toBe(screen.getByRole('group', { name: 'planet.countries' }));
    expect(screen.getByRole('combobox').getAttribute('aria-expanded')).toBe('false');
    expect(onSelect).not.toHaveBeenCalled();
  });

  it('finds a microstate with an instant keyboard focus command and closes search on repeated selection', async () => {
    const onSelect = vi.fn();
    const { container } = render(<PlanetView countries={countries} onSelect={onSelect} />);
    const input = screen.getByRole('combobox');
    act(() => input.focus());
    fireEvent.change(input, { target: { value: 'mt' } });
    expect(screen.getAllByRole('option')).toHaveLength(1);
    fireEvent.keyDown(input, { key: 'Enter' });
    await waitFor(() => expect(scene.props.selectedCode).toBe('MT'));
    expect(scene.props.cameraCommand).toMatchObject({ type: 'focus', countryCode: 'MT', instant: true });
    expect(screen.queryByRole('listbox')).toBeNull();
    const card = container.querySelector('[data-selected-country="MT"]');
    expect(document.activeElement).toBe(card);
    expect(input.getAttribute('aria-expanded')).toBe('false');
    expect(onSelect).not.toHaveBeenCalled();

    act(() => input.focus());
    fireEvent.change(input, { target: { value: 'mt' } });
    fireEvent.keyDown(input, { key: 'Enter' });
    expect(screen.queryByRole('listbox')).toBeNull();
    expect(document.activeElement).toBe(card);
    fireEvent.click(screen.getByRole('button', { name: 'planet.openCountry' }));
    expect(onSelect).toHaveBeenCalledWith(countries[1], null);
  });

  it('prioritizes the UK code over Ukraine and resolves the GB alias in English search', async () => {
    scene.locale = 'en';
    const englishCountries = [
      { code: 'UA', slug: 'ukraine', name: 'Украина', name_en: 'Ukraine' },
      { code: 'UK', slug: 'united-kingdom', name: 'Великобритания', name_en: 'United Kingdom' },
    ];
    const onSelect = vi.fn();
    render(<PlanetView countries={englishCountries} onSelect={onSelect} />);
    const input = screen.getByRole('combobox');
    act(() => input.focus());
    fireEvent.change(input, { target: { value: 'UK' } });
    fireEvent.keyDown(input, { key: 'Enter' });
    await waitFor(() => expect(scene.props.selectedCode).toBe('UK'));
    expect(screen.getByRole('heading', { name: 'United Kingdom' })).toBeTruthy();
    const firstCommandId = scene.props.cameraCommand.id;
    act(() => input.focus());
    fireEvent.change(input, { target: { value: 'GB' } });
    expect(screen.getAllByRole('option')).toHaveLength(1);
    expect(screen.getByRole('option', { name: /United Kingdom/ })).toBeTruthy();
    fireEvent.keyDown(input, { key: 'Enter' });
    expect(scene.props.cameraCommand).toMatchObject({ type: 'focus', countryCode: 'UK', instant: true });
    expect(scene.props.cameraCommand.id).toBeGreaterThan(firstCommandId);
    expect(screen.queryByRole('listbox')).toBeNull();
    expect(onSelect).not.toHaveBeenCalled();
  });

  it('preserves map-series countries absent from the catalogue and real zero values', async () => {
    const detail = { country_code: 'US', country_slug: 'united-states', country_name: 'США', indicator_code: 'us-budget', value: 0 };
    const onSelect = vi.fn();
    const { container } = render(<PlanetView countries={countries} detailsByCode={{ US: detail }} valuesByCode={{ US: 0 }} metricName="Сальдо" initialMode="data" onSelect={onSelect} />);
    const input = screen.getByRole('combobox');
    fireEvent.change(input, { target: { value: 'us' } });
    fireEvent.keyDown(input, { key: 'Enter' });
    await waitFor(() => expect(scene.props.mode).toBe('data'));
    expect(container.querySelector('[data-selected-country="US"]')).toBeTruthy();
    expect(screen.queryByText('planet.noData')).toBeNull();
    expect(screen.getByLabelText('planet.value').textContent).toBe('0,00');
    fireEvent.click(screen.getByRole('button', { name: 'planet.openIndicator' }));
    expect(onSelect.mock.calls[0][0]).toMatchObject({ code: 'US', slug: 'united-states' });
    expect(onSelect.mock.calls[0][1]).toBe(detail);
  });

  it('ignores unavailable scene countries and never manufactures a selection', async () => {
    const onSelect = vi.fn();
    const { container } = render(<PlanetView countries={countries} onSelect={onSelect} />);
    fireEvent.click(await screen.findByRole('button', { name: 'Pick unavailable country' }));
    expect(container.querySelector('[data-selected-country=""]')).toBeTruthy();
    expect(screen.queryByRole('button', { name: 'planet.openCountry' })).toBeNull();
    expect(onSelect).not.toHaveBeenCalled();
  });

  it('offers Earth and Data while numeric colour intervals remain available through a disclosure', async () => {
    const { container } = render(<PlanetView countries={countries} valuesByCode={{ DE: -5, MT: 10 }} unit="%" metricName="Сальдо" colorMode="diverging" initialMode="data" />);
    await screen.findByTestId('planet-scene');
    const layers = within(screen.getByRole('group', { name: 'planet.layerLabel' }));
    expect(layers.getAllByRole('button').map((button) => button.textContent)).toEqual(['planet.earth', 'planet.data']);
    expect(screen.queryByRole('button', { name: 'planet.map' })).toBeNull();

    const summary = container.querySelector('details summary');
    expect(summary.textContent).toContain('-5,00–10,00 %');
    fireEvent.click(summary);
    expect(summary.parentElement.open).toBe(true);
    const legend = within(screen.getByLabelText('planet.legend'));
    expect(legend.getByText('world.map.scaleZero')).toBeTruthy();
    expect(legend.getByText('≤ -6,67 %')).toBeTruthy();
    expect(legend.getByText('0,00 %')).toBeTruthy();
    expect(legend.getByText('≥ 6,67 %')).toBeTruthy();
  });

  it('keeps the country selected across layers and opens the current observation after the period changes', async () => {
    const onSelect = vi.fn();
    const initialProps = {
      countries,
      detailsByCode: new Map([['DE', germanyDetail]]),
      valuesByCode: new Map([['DE', 3.2]]),
      metricName: 'Безработица',
      initialMode: 'data',
      onSelect,
    };
    const { container, rerender } = render(<PlanetView {...initialProps} />);
    fireEvent.click(await screen.findByRole('button', { name: 'Pick Germany' }));
    fireEvent.click(screen.getByRole('button', { name: 'planet.earth' }));
    expect(scene.props.mode).toBe('earth');

    const currentDetail = { ...germanyDetail, date: '2026-07-01', value: 5.1 };
    rerender(<PlanetView {...initialProps} detailsByCode={{ DE: currentDetail }} valuesByCode={{ DE: 5.1 }} />);
    expect(container.querySelector('[data-selected-country="DE"]')).toBeTruthy();
    expect(screen.getByText('июль 2026')).toBeTruthy();
    expect(screen.queryByText('июнь 2026')).toBeNull();
    expect(screen.getByLabelText('planet.value').textContent).toBe('5,10');

    fireEvent.click(screen.getByRole('button', { name: 'planet.data' }));
    expect(scene.props.selectedCode).toBe('DE');
    expect(scene.props.mode).toBe('data');
    expect(onSelect).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: 'planet.openIndicator' }));
    expect(onSelect).toHaveBeenCalledWith(countries[0], currentDetail);
  });

  it('passes the chosen year as a number without opening a country', () => {
    const onYearChange = vi.fn();
    const onSelect = vi.fn();
    render(<PlanetView countries={countries} years={[2024, 2025, 2026]} year={2026} onYearChange={onYearChange} onSelect={onSelect} />);
    fireEvent.change(screen.getByRole('combobox', { name: 'map.timeline.yearOnMap' }), { target: { value: '2025' } });
    expect(onYearChange).toHaveBeenCalledWith(2025);
    expect(onSelect).not.toHaveBeenCalled();
  });

  it('preserves the server benchmark label when the value is a mean rather than a median', () => {
    render(<PlanetView countries={countries} valuesByCode={{ DE: 3.2, MT: 1.7 }} unit="%" benchmark={{ value: 3, label: 'Среднее стран мира' }} />);
    expect(screen.getByText(/Среднее стран мира:/).textContent).toContain('3,00 %');
    expect(screen.queryByText(/planet.median/)).toBeNull();
  });

  it('compares two countries by the common concept rather than their different national indicator codes', () => {
    render(<PlanetView countries={countries} valuesByCode={{ DE: 3.2, MT: 1.7 }} detailsByCode={{ DE: germanyDetail, MT: maltaDetail }} conceptSlug="unemployment-rate" />);
    selectListCountry('Германия');
    fireEvent.click(screen.getByRole('button', { name: 'planet.addComparison' }));
    expect(screen.queryByRole('link', { name: 'planet.showComparison' })).toBeNull();
    selectListCountry('Мальта');
    fireEvent.click(screen.getByRole('button', { name: 'planet.addComparison' }));
    const link = screen.getByRole('link', { name: 'planet.showComparison' });
    const codes = new URL(link.getAttribute('href'), window.location.href).searchParams.get('codes');
    expect(codes).toBe('w:germany:unemployment-rate,w:malta:unemployment-rate');
    expect(codes).not.toContain(germanyDetail.indicator_code);
    expect(codes).not.toContain(maltaDetail.indicator_code);
  });

  it('opens country search from the empty comparison slot and allows real zero observations', async () => {
    render(<PlanetView countries={countries} valuesByCode={{ DE: 3.2, MT: 0 }} conceptSlug="budget-balance" />);
    selectListCountry('Германия');
    fireEvent.click(screen.getByRole('button', { name: 'planet.addComparison' }));
    fireEvent.click(screen.getByRole('button', { name: 'planet.chooseSecond' }));
    const input = screen.getByRole('combobox');
    expect(document.activeElement).toBe(input);
    expect(input.getAttribute('aria-expanded')).toBe('true');
    fireEvent.change(input, { target: { value: 'MT' } });
    fireEvent.keyDown(input, { key: 'Enter' });
    await waitFor(() => expect(scene.props.selectedCode).toBe('MT'));
    fireEvent.click(screen.getByRole('button', { name: 'planet.addComparison' }));
    expect(new URL(screen.getByRole('link', { name: 'planet.showComparison' }).href).searchParams.get('codes')).toBe('w:germany:budget-balance,w:malta:budget-balance');
    expect(screen.queryByRole('button', { name: 'planet.chooseSecond' })).toBeNull();
  });

  it('explains the two-country limit and makes room for a replacement when a chip is removed', () => {
    const france = { code: 'FR', slug: 'france', name: 'Франция' };
    const { container } = render(<PlanetView countries={[...countries, france]} valuesByCode={{ DE: 3.2, MT: 1.7, FR: 5 }} conceptSlug="unemployment-rate" />);
    for (const name of ['Германия', 'Мальта']) {
      selectListCountry(name);
      fireEvent.click(screen.getByRole('button', { name: 'planet.addComparison' }));
    }
    selectListCountry('Франция');
    const pin = screen.getByRole('button', { name: 'planet.addComparison' });
    expect(pin.disabled).toBe(true);
    expect(document.getElementById(pin.getAttribute('aria-describedby')).textContent).toBe('planet.comparisonFull');
    const pair = within(container.querySelector('.planet-comparison-pair'));
    fireEvent.click(pair.getAllByRole('button', { name: 'planet.removeComparison' })[0]);
    expect(pin.disabled).toBe(false);
    expect(screen.queryByText('planet.comparisonFull')).toBeNull();
    fireEvent.click(pin);
    expect(new URL(screen.getByRole('link', { name: 'planet.showComparison' }).href).searchParams.get('codes')).toBe('w:malta:unemployment-rate,w:france:unemployment-rate');
  });

  it('keeps removal available when a pinned country has no observation in the new year', () => {
    const props = { countries, valuesByCode: { DE: 3.2, MT: 1.7 }, conceptSlug: 'unemployment-rate' };
    const { rerender } = render(<PlanetView {...props} />);
    selectListCountry('Германия');
    fireEvent.click(screen.getByRole('button', { name: 'planet.addComparison' }));
    rerender(<PlanetView {...props} valuesByCode={{ DE: null, MT: 1.7 }} />);
    const pin = screen.getByRole('button', { name: 'planet.inComparison' });
    expect(pin.disabled).toBe(false);
    fireEvent.click(pin);
    expect(screen.queryByLabelText('planet.comparison')).toBeNull();
    expect(screen.getByRole('button', { name: 'planet.addComparison' }).disabled).toBe(true);
  });

  it('clears an unsuccessful search and returns focus to the complete country pool', () => {
    render(<PlanetView countries={countries} />);
    const input = screen.getByRole('combobox');
    fireEvent.change(input, { target: { value: 'nonexistent' } });
    expect(screen.getByText('planet.noMatches').getAttribute('role')).toBe('status');
    fireEvent.click(screen.getByRole('button', { name: 'planet.clearSearch' }));
    expect(input.value).toBe('');
    expect(document.activeElement).toBe(input);
    expect(screen.getAllByRole('option')).toHaveLength(2);
  });

  it('uses client-side routes for country, comparison and the chosen rating year', () => {
    function LocationProbe() {
      const location = useLocation();
      return <output data-testid="location">{location.pathname + location.search}</output>;
    }
    render(<MemoryRouter><PlanetView countries={countries} valuesByCode={{ DE: 3.2, MT: 1.7 }} conceptSlug="unemployment-rate" ratingHref="/world/rating/unemployment-rate?year=2024" /><LocationProbe /></MemoryRouter>);
    selectListCountry('Германия');
    fireEvent.click(screen.getByRole('link', { name: 'planet.allIndicators' }));
    expect(screen.getByTestId('location').textContent).toBe('/germany');
    fireEvent.click(screen.getByRole('link', { name: 'planet.fullRating' }));
    expect(screen.getByTestId('location').textContent).toBe('/world/rating/unemployment-rate?year=2024');
    fireEvent.click(screen.getByRole('button', { name: 'planet.addComparison' }));
    selectListCountry('Мальта');
    fireEvent.click(screen.getByRole('button', { name: 'planet.addComparison' }));
    fireEvent.click(screen.getByRole('link', { name: 'planet.showComparison' }));
    expect(screen.getByTestId('location').textContent).toContain('/compare?codes=');
    expect(new URL(screen.getByTestId('location').textContent, window.location.href).searchParams.get('codes')).toBe('w:germany:unemployment-rate,w:malta:unemployment-rate');
  });

  it('keeps Russia browsable without a value but cannot pin a missing observation for comparison', () => {
    const russia = { code: 'RU', slug: 'russia', name: 'Россия' };
    render(<PlanetView countries={[...countries, russia]} valuesByCode={{ DE: 3.2, MT: 1.7, RU: null }} detailsByCode={{ RU: { indicator_code: 'unemployment', value: null } }} conceptSlug="unemployment-rate" />);
    selectListCountry('Россия');
    expect(screen.getByText('planet.noData')).toBeTruthy();
    const pin = screen.getByRole('button', { name: 'planet.addComparison' });
    expect(pin.disabled).toBe(true);
    fireEvent.click(pin);
    expect(screen.queryByRole('link', { name: 'planet.showComparison' })).toBeNull();
    expect(screen.queryByLabelText('planet.comparison')).toBeNull();
  });

  it('includes the complete country pool when the supplied ranking covers only 32 rows', () => {
    const allCountries = Array.from({ length: 40 }, (_, index) => ({ code: `X${index}`, slug: `country-${index}`, name: `Страна ${index}` }));
    const valuesByCode = Object.fromEntries(allCountries.map((country, index) => [country.code, index]));
    const rankingItems = allCountries.slice(0, 32).map((country, index) => ({ country_code: country.code, value: index, rank: index + 1 }));
    render(<PlanetView countries={allCountries} valuesByCode={valuesByCode} rankingItems={rankingItems} colorDirection="asc" />);
    expect(countryList().getAllByRole('button')).toHaveLength(40);
    const lastCountry = countryList().getByRole('button', { name: /Страна 39/ });
    fireEvent.click(lastCountry);
    expect(screen.getByRole('heading', { name: 'Страна 39' })).toBeTruthy();
    expect(lastCountry.getAttribute('aria-pressed')).toBe('true');
  });

  it('starts the coarse-pointer scene with interaction disabled, enables Rotate and disables it on Done', async () => {
    vi.spyOn(window, 'matchMedia').mockImplementation((query) => ({
      matches: query === '(pointer: coarse)', media: query,
      addEventListener: vi.fn(), removeEventListener: vi.fn(),
    }));
    render(<PlanetView countries={countries} />);
    await screen.findByTestId('planet-scene');
    expect(scene.props.touchNavigation).toBe(true);
    expect(scene.props.interactive).toBe(false);
    fireEvent.click(screen.getByRole('button', { name: 'planet.rotate' }));
    expect(scene.props.interactive).toBe(true);
    fireEvent.click(screen.getByRole('button', { name: 'planet.doneRotating' }));
    expect(scene.props.interactive).toBe(false);
  });

  it('falls back after a scene error and retains country selection and CTA through retry', async () => {
    scene.fail = true;
    vi.spyOn(console, 'warn').mockImplementation(() => {});
    const onSelect = vi.fn();
    const { container } = render(<PlanetView countries={countries} detailsByCode={{ DE: germanyDetail }} onSelect={onSelect} />);
    await screen.findByTestId('fallback-map');
    expect(screen.getByText('planet.unavailable')).toBeTruthy();
    expect(container.querySelector('[data-scene-ready="true"]')).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: 'Select on map' }));
    expect(onSelect).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: 'planet.openIndicator' }));
    expect(onSelect).toHaveBeenCalledWith(countries[0], germanyDetail);
    scene.fail = false;
    fireEvent.click(screen.getByRole('button', { name: 'planet.retry' }));
    await screen.findByTestId('planet-scene');
    await waitFor(() => expect(container.querySelector('[data-scene-ready="true"]')).toBeTruthy());
    expect(scene.props.selectedCode).toBe('DE');
  });
});
