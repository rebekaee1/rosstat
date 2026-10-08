import { useEffect } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter, useLocation } from 'react-router-dom';
import PlanetView from './PlanetView';

const scene = vi.hoisted(() => ({ fail: false, hold: false, props: null, mapProps: null, locale: 'ru' }));

vi.mock('../i18n', () => ({
  useT: () => (key, vars) => (vars?.count == null ? key : `${key}: ${vars.count}`),
  useLocale: () => ({ locale: scene.locale }),
}));
vi.mock('./PlanetScene', () => ({
  default: function MockPlanetScene(props) {
    scene.props = props;
    const { onReady, onError } = props;
    useEffect(() => {
      if (scene.hold) return;
      if (scene.fail) onError(new Error('No WebGL'));
      else onReady();
    }, [onError, onReady]);
    return <div data-testid="planet-scene"><button type="button" onClick={() => props.onSelect('DE')}>Pick Germany</button><button type="button" onClick={() => props.onSelect('ZZ')}>Pick unavailable country</button></div>;
  },
}));
vi.mock('./WorldMap', () => ({
  default: (props) => {
    scene.mapProps = props;
    return <div data-testid="fallback-map"><button type="button" onClick={() => props.onSelect(props.countries[0], props.detailsByCode?.get(props.countries[0]?.code))}>Select on map</button></div>;
  },
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

// Круг 8: по умолчанию показывается плоская карта. Тесты шара ниже явно выбирают шар (как человек, нажавший «Шар»);
// новое поведение карты проверяет отдельный блок в конце файла.
beforeEach(() => {
  window.localStorage.clear();
  window.localStorage.setItem('fe_planet_view', 'globe');
  scene.fail = false;
  scene.hold = false;
  scene.props = null;
  scene.mapProps = null;
  scene.locale = 'ru';
});
afterEach(() => vi.restoreAllMocks());

describe('PlanetView interaction contract', () => {
  it('starts in Earth and selects a country before opening its actual row', async () => {
    const onSelect = vi.fn();
    const { container } = render(<PlanetView initialMode="earth" showLayerSwitch countries={countries} detailsByCode={new Map([['DE', germanyDetail]])} valuesByCode={new Map([['DE', 3.2]])} metricName="Безработица" unit="%" onSelect={onSelect} />);
    fireEvent.click(await screen.findByRole('button', { name: 'Pick Germany' }));
    expect(scene.props.mode).toBe('earth');
    expect(container.querySelector('[data-scene-ready="true"]')).toBeTruthy();
    expect(container.querySelector('[data-selected-country="DE"]')).toBeTruthy();
    expect(screen.getByText('июнь 2026')).toBeTruthy();
    expect(onSelect).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: 'planet.openIndicator' }));
    expect(onSelect).toHaveBeenCalledWith(countries[0], germanyDetail);
  });

  it('opens the country on a second press of the same country, on the surface and in the list', async () => {
    const onSelect = vi.fn();
    render(<PlanetView countries={countries} detailsByCode={new Map([['DE', germanyDetail], ['MT', maltaDetail]])} valuesByCode={new Map([['DE', 3.2], ['MT', 1.7]])} metricName="Безработица" unit="%" onSelect={onSelect} />);
    const surface = await screen.findByRole('button', { name: 'Pick Germany' });
    fireEvent.click(surface);
    expect(onSelect).not.toHaveBeenCalled();
    fireEvent.click(surface);
    expect(onSelect).toHaveBeenCalledWith(countries[0], germanyDetail);
    // Another country is only previewed first, however many times the previous one was pressed.
    selectListCountry('Мальта');
    expect(onSelect).toHaveBeenCalledTimes(1);
    selectListCountry('Мальта');
    expect(onSelect).toHaveBeenLastCalledWith(countries[1], maltaDetail);
  });

  it('names hovered land without a catalogue page and explains the next press for catalogue countries', async () => {
    const { container } = render(<PlanetView countries={countries} detailsByCode={new Map([['DE', germanyDetail]])} valuesByCode={new Map([['DE', 3.2]])} metricName="Безработица" unit="%" onSelect={() => {}} />);
    await screen.findByTestId('planet-scene');
    act(() => scene.props.onHover(null, 'Чад'));
    const muted = container.querySelector('.planet-hover-label--muted');
    expect(muted.textContent).toContain('Чад');
    expect(muted.textContent).toContain('planet.notInCatalog');
    act(() => scene.props.onHover('DE'));
    expect(container.querySelector('.planet-hover-label--muted')).toBeNull();
    expect(container.querySelector('.planet-hover-label').textContent).toContain('planet.pressToSelect');
    fireEvent.click(screen.getByRole('button', { name: 'Pick Germany' }));
    act(() => scene.props.onHover('DE'));
    expect(container.querySelector('.planet-hover-label').textContent).toContain('planet.pressToOpen');
    act(() => scene.props.onHover(null));
    expect(container.querySelector('.planet-hover-label')).toBeNull();
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
    const { container } = render(<PlanetView initialMode="earth" showLayerSwitch countries={countries} valuesByCode={{ DE: -5, MT: 10 }} unit="%" metricName="Сальдо" colorMode="diverging" initialMode="data" />);
    await screen.findByTestId('planet-scene');
    const layers = within(screen.getByRole('group', { name: 'planet.layerLabel' }));
    expect(layers.getAllByRole('button').map((button) => button.textContent)).toEqual(['planet.earth', 'planet.data']);
    expect(screen.queryByRole('button', { name: 'planet.map' })).toBeNull();

    // The range is always visible as a colour strip with its own unit; intervals stay behind the disclosure.
    const ends = container.querySelector('.planet-key-ends').textContent;
    expect(ends).toContain('-5,0 %');
    expect(ends).toContain('10,0 %');
    const summary = container.querySelector('details summary');
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
      unit: '%',
      initialMode: 'data',
      onSelect,
    };
    const { container, rerender } = render(<PlanetView initialMode="earth" showLayerSwitch {...initialProps} />);
    fireEvent.click(await screen.findByRole('button', { name: 'Pick Germany' }));
    fireEvent.click(screen.getByRole('button', { name: 'planet.earth' }));
    expect(scene.props.mode).toBe('earth');
    expect(scene.props.valuesByCode.get('DE')).toBe(3.2);
    expect(scene.props.unit).toBe('%');

    const currentDetail = { ...germanyDetail, date: '2026-07-01', value: 5.1 };
    rerender(<PlanetView initialMode="earth" showLayerSwitch {...initialProps} detailsByCode={{ DE: currentDetail }} valuesByCode={{ DE: 5.1 }} />);
    expect(container.querySelector('[data-selected-country="DE"]')).toBeTruthy();
    expect(screen.getByText('июль 2026')).toBeTruthy();
    expect(screen.queryByText('июнь 2026')).toBeNull();
    expect(screen.getByLabelText('planet.value').textContent).toBe('5,1');
    expect(scene.props.valuesByCode.get('DE')).toBe(5.1);

    fireEvent.click(screen.getByRole('button', { name: 'planet.data' }));
    expect(scene.props.selectedCode).toBe('DE');
    expect(scene.props.mode).toBe('data');
    expect(onSelect).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: 'planet.openIndicator' }));
    expect(onSelect).toHaveBeenCalledWith(countries[0], currentDetail);
  });

  it('passes the card observation fallback and zero to the surface with the current localized unit', async () => {
    const props = { countries, detailsByCode: { DE: germanyDetail }, valuesByCode: { DE: null }, unit: '%' };
    const { rerender } = render(<PlanetView {...props} />);
    await screen.findByTestId('planet-scene');
    expect(scene.props.valuesByCode.get('DE')).toBe(3.2);
    expect(scene.props.unit).toBe('%');
    scene.locale = 'en';
    rerender(<PlanetView {...props} valuesByCode={{ DE: 0 }} unit="млрд $" />);
    expect(scene.props.valuesByCode.get('DE')).toBe(0);
    expect(scene.props.unit).toBe('billion $');
  });

  it('keeps the same effective observation in SVG fallback and preserves real zero', async () => {
    scene.fail = true;
    vi.spyOn(console, 'warn').mockImplementation(() => {});
    const props = { countries, detailsByCode: { DE: germanyDetail, MT: { ...maltaDetail, value: null } }, valuesByCode: { DE: null }, unit: '%' };
    const { rerender } = render(<PlanetView {...props} />);
    await screen.findByTestId('fallback-map');
    expect(scene.mapProps.valuesByCode.get('DE')).toBe(3.2);
    expect(scene.mapProps.valuesByCode.get('MT')).toBeNull();
    selectListCountry('Германия');
    expect(screen.getByLabelText('planet.value').textContent).toBe('3,20');
    rerender(<PlanetView {...props} valuesByCode={{ DE: 0 }} />);
    expect(scene.mapProps.valuesByCode.get('DE')).toBe(0);
    expect(screen.getByLabelText('planet.value').textContent).toBe('0,00');
  });

  it('passes the chosen year as a number without opening a country', () => {
    const onYearChange = vi.fn();
    const onSelect = vi.fn();
    render(<PlanetView countries={countries} years={[2024, 2025, 2026]} year={2026} onYearChange={onYearChange} onSelect={onSelect} />);
    fireEvent.click(screen.getByRole('button', { name: 'map.timeline.yearOnMap: 2026' }));
    expect(screen.getAllByRole('option').map((option) => option.textContent)).toEqual(['2026', '2025', '2024']);
    fireEvent.click(screen.getByRole('option', { name: '2025' }));
    expect(onYearChange).toHaveBeenCalledWith(2025);
    expect(screen.queryByRole('listbox')).toBeNull();
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

  it('starts the coarse-pointer scene with horizontal spin only and has no rotation toggle', async () => {
    vi.spyOn(window, 'matchMedia').mockImplementation((query) => ({
      matches: query === '(pointer: coarse)', media: query,
      addEventListener: vi.fn(), removeEventListener: vi.fn(),
    }));
    render(<PlanetView countries={countries} />);
    await screen.findByTestId('planet-scene');
    expect(scene.props.touchNavigation).toBe(true);
    expect(scene.props.interactive).toBe(false);
    expect(screen.queryByRole('button', { name: 'planet.rotate' })).toBeNull();
  });

  it('falls back after a scene error and retains country selection and CTA through retry', async () => {
    scene.fail = true;
    vi.spyOn(console, 'warn').mockImplementation(() => {});
    const onSelect = vi.fn();
    const { container } = render(<PlanetView countries={countries} detailsByCode={{ DE: germanyDetail }} onSelect={onSelect} />);
    await screen.findByText('planet.unavailable');
    await screen.findByTestId('fallback-map');
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

  it('shows flags instead of ISO codes, and a unit beside every number', async () => {
    const { container } = render(<PlanetView countries={countries} valuesByCode={{ DE: 3.2, MT: 1.7 }} metricName="Безработица" unit="%" />);
    await screen.findByTestId('planet-scene');
    const rows = countryList().getAllByRole('button');
    expect(rows[0].querySelector('.fe-flag').textContent).toBe('\u{1F1E9}\u{1F1EA}');
    expect(rows[0].textContent).not.toMatch(/\bDE\b/);
    expect(rows[0].textContent).toContain('%');
    fireEvent.focus(screen.getByRole('combobox'));
    const option = screen.getAllByRole('option')[0];
    expect(option.querySelector('.fe-flag')).toBeTruthy();
    expect(option.textContent).not.toMatch(/\bDE\b/);
    expect(container.querySelector('.planet-country-heading')).toBeNull();
  });

  it('says where the country stands and counts the value up inside the card', async () => {
    render(<PlanetView countries={countries} valuesByCode={{ DE: 3.2, MT: 1.7 }} metricName="Безработица" unit="%" colorDirection="desc" />);
    fireEvent.click(await screen.findByRole('button', { name: 'Pick Germany' }));
    expect(screen.getByText('w2.planet.rank')).toBeTruthy();
    expect(screen.getByLabelText('planet.value').textContent).toBe('3,20');
  });

  it('keeps technical wording off the screen: «median» becomes «middle of the ranking»', () => {
    render(<PlanetView countries={countries} valuesByCode={{ DE: 3.2, MT: 1.7 }} unit="%" benchmark={{ value: 2.5, label: 'Медиана по 55 странам с данными' }} />);
    expect(screen.queryByText(/Медиана по/)).toBeNull();
    expect(screen.getByText(/w2.planet.middle:/)).toBeTruthy();
  });

  it('draws a colour strip with both ends and a unit in data mode, and none in Earth mode', async () => {
    const { container, rerender } = render(<PlanetView countries={countries} valuesByCode={{ DE: 3.2, MT: 1.7 }} metricName="Безработица" unit="%" initialMode="data" periodLabel="2025" />);
    await screen.findByTestId('planet-scene');
    expect(container.querySelector('.planet-key-bar')).toBeTruthy();
    expect(container.querySelector('.planet-key-title').textContent).toContain('Безработица');
    expect(container.querySelector('.planet-key-title').textContent).toContain('2025');
    expect(container.querySelector('.planet-key-ends').textContent).toContain('1,70 %');
    expect(container.querySelector('.planet-key-ends').textContent).toContain('3,20 %');
    expect(scene.props.valueDigits).toBe(2);
    rerender(<PlanetView countries={countries} valuesByCode={{ DE: 3.2, MT: 1.7 }} metricName="Безработица" unit="%" initialMode="earth" periodLabel="2025" />);
  });

  it('legend is two compact rows: title with the colour-guide button, then the strip with both ends; the details sit behind the button', async () => {
    const { container } = render(<PlanetView countries={countries} valuesByCode={{ DE: 3.2, MT: 1.7 }} metricName="Безработица" unit="%" colorDirection="asc" periodLabel="2025" />);
    await screen.findByTestId('planet-scene');
    const key = container.querySelector('.planet-key');
    expect(key.querySelector('.planet-key-head .planet-key-title')).toBeTruthy();
    expect(key.querySelector('.planet-key-head details.planet-scale summary').textContent).toBe('planet.legend');
    expect(key.querySelector('.planet-key-scale .planet-key-bar')).toBeTruthy();
    expect(key.querySelectorAll('.planet-key-scale .planet-key-ends > span')).toHaveLength(2);
    // Порядок цвета, интервалы и пометка про страны с узором лежат за кнопкой, а не отдельными абзацами под шкалой.
    const legend = key.querySelector('details.planet-scale .planet-legend');
    expect(legend.querySelector('.planet-key-order').textContent).toBe('w6c.key.rule');
    expect(legend.querySelector('.planet-key-note').textContent).toBe('w6c.key.noData: 2');
    expect(key.querySelector(':scope > .planet-key-order, :scope > .planet-key-note')).toBeNull();
    expect(key.querySelector('details.planet-scale').hasAttribute('open')).toBe(false);
  });

  it('passes the start focus to the scene only when a page asks for one (the home page starts over Eurasia or the USA)', async () => {
    const { unmount } = render(<PlanetView countries={countries} valuesByCode={{ DE: 3.2 }} startFocus={[52, 38]} />);
    await screen.findByTestId('planet-scene');
    expect(scene.props.startFocus).toEqual([52, 38]);
    unmount();
    render(<PlanetView countries={countries} valuesByCode={{ DE: 3.2 }} />);
    await screen.findByTestId('planet-scene');
    expect(scene.props.startFocus).toBeNull();
  });

  it('on a narrow screen the country field asks for a short «Country», not a clipped long phrase', async () => {
    vi.spyOn(window, 'matchMedia').mockImplementation((query) => ({
      matches: query.includes('max-width: 520px'), media: query, addEventListener: vi.fn(), removeEventListener: vi.fn(),
    }));
    render(<PlanetView countries={countries} valuesByCode={{ DE: 3.2 }} />);
    await screen.findByTestId('planet-scene');
    expect(screen.getByRole('combobox').getAttribute('placeholder')).toBe('z3.planet.searchShort');
  });

  it('collapses a long list for phones to five rows and expands it on request without a nested scroll', () => {
    const many = Array.from({ length: 20 }, (_, index) => ({ code: `Y${index}`, slug: `y-${index}`, name: `Страна ${index}` }));
    const { container } = render(<PlanetView countries={many} valuesByCode={Object.fromEntries(many.map((country, index) => [country.code, index]))} />);
    expect(container.querySelector('.planet-country-list').classList.contains('is-compact')).toBe(true);
    fireEvent.click(screen.getByRole('button', { name: /w2.planet.showAll/ }));
    expect(container.querySelector('.planet-country-list').classList.contains('is-compact')).toBe(false);
    expect(screen.getByRole('button', { name: /w2.planet.showLess/ }).getAttribute('aria-expanded')).toBe('true');
  });

  it('picks the list row on the planet itself: the camera turns to the country and the stage is scrolled into view on a phone', async () => {
    vi.spyOn(window, 'matchMedia').mockImplementation((query) => ({
      matches: query.includes('max-width: 700px'), media: query, addEventListener: vi.fn(), removeEventListener: vi.fn(),
    }));
    const scrollIntoView = vi.fn();
    Element.prototype.scrollIntoView = scrollIntoView;
    const { container } = render(<PlanetView countries={countries} valuesByCode={{ DE: 3.2, MT: 1.7 }} metricName="Безработица" unit="%" />);
    await screen.findByTestId('planet-scene');
    vi.spyOn(container.querySelector('.planet-stage'), 'getBoundingClientRect').mockReturnValue({ top: -400, bottom: -100 });
    selectListCountry('Германия');
    expect(scene.props.selectedCode).toBe('DE');
    expect(scene.props.cameraCommand).toMatchObject({ type: 'focus', countryCode: 'DE' });
    expect(scrollIntoView).toHaveBeenCalledWith(expect.objectContaining({ block: 'start' }));
    expect(scrollIntoView.mock.instances[0]).toBe(container.querySelector('.planet-stage'));
    delete Element.prototype.scrollIntoView;
  });

  it('lays the country card on the globe itself: a tap never scrolls or moves the page', async () => {
    window.scrollBy = vi.fn();
    const { container } = render(<PlanetView countries={countries} valuesByCode={{ DE: 3.2, MT: 1.7 }} metricName="Безработица" unit="%" conceptSlug="unemployment-rate" />);
    const sheet = container.querySelector('.planet-country-card');
    expect(container.querySelector('.planet-stage').contains(sheet)).toBe(true);
    fireEvent.click(await screen.findByRole('button', { name: 'Pick Germany' }));
    expect(sheet.classList.contains('is-selected')).toBe(true);
    expect(container.querySelector('.planet-stage').classList.contains('has-card')).toBe(true);
    expect(window.scrollBy).not.toHaveBeenCalled();
    // Two buttons: details and compare.
    expect(within(sheet).getAllByRole('button').map((button) => button.textContent).filter(Boolean)).toEqual(expect.arrayContaining(['planet.openCountry', 'planet.addComparison']));
    delete window.scrollBy;
  });

  it('one metaphor, gold is better: «worse» on the left and «better» on the right with their numbers, for either direction', async () => {
    const props = { countries, valuesByCode: { DE: 3.2, MT: 1.7 }, metricName: 'Безработица', unit: '%', initialMode: 'data' };
    const { container, rerender } = render(<PlanetView {...props} colorDirection="asc" hideListOnPhone />);
    await screen.findByTestId('planet-scene');
    expect(container.querySelector('.planet-key-order').textContent).toBe('w6c.key.rule');
    const ends = [...container.querySelectorAll('.planet-key-ends span')].map((node) => node.textContent);
    // Lower is better: the best (right, gold) end is the smallest number.
    expect(ends[0]).toContain('w6c.key.worse');
    expect(ends[0]).toContain('3,20');
    expect(ends[1]).toContain('w6c.key.better');
    expect(ends[1]).toContain('1,70');
    expect(container.querySelector('.planet-view--no-phone-list')).toBeTruthy();
    rerender(<PlanetView {...props} colorDirection="desc" />);
    const desc = [...container.querySelectorAll('.planet-key-ends span')].map((node) => node.textContent);
    expect(desc[0]).toContain('1,70');
    expect(desc[1]).toContain('3,20');
    // Without a known order the plain «lower / higher» wording stays honest.
    rerender(<PlanetView {...props} />);
    expect(container.querySelector('.planet-key-order').textContent).toBe('w6c.key.ruleValue');
    expect(container.querySelector('.planet-key-ends span small').textContent).toBe('w2.planet.keyLow');
  });

  it('says how many countries have official data next to the patterned «no data» swatch', async () => {
    const { container } = render(<PlanetView countries={countries} valuesByCode={{ DE: 3.2 }} metricName="Безработица" unit="%" />);
    await screen.findByTestId('planet-scene');
    expect(container.querySelector('.planet-key-note').textContent).toBe('w6c.key.noData: 2');
  });

  it('keeps every country name off the globe until one is selected or hovered', async () => {
    render(<PlanetView initialMode="earth" showLayerSwitch countries={countries} valuesByCode={{ DE: 3.2, MT: 1.7 }} metricName="Безработица" unit="%" />);
    await screen.findByTestId('planet-scene');
    expect(scene.props.selectedCode).toBeNull();
    expect(scene.props.mode).toBe('earth');
  });
  it('по умолчанию показывает данные на шаре, без переключателя «Земля / Данные»', async () => {
    const { container } = render(<PlanetView countries={countries} valuesByCode={{ DE: 3.2, MT: 1.7 }} metricName="Безработица" unit="%" />);
    await screen.findByTestId('planet-scene');
    expect(screen.queryByRole('button', { name: 'planet.earth' })).toBeNull();
    expect(screen.queryByRole('button', { name: 'planet.data' })).toBeNull();
    expect(container.querySelector('.planet-stage').dataset.planetMode).toBe('data');
  });

  it('shows one gesture hint over the globe until the first touch, then never again', async () => {
    const { container, unmount } = render(<PlanetView countries={countries} valuesByCode={{ DE: 3.2 }} metricName="Безработица" unit="%" />);
    await screen.findByTestId('planet-scene');
    await waitFor(() => expect(container.querySelector('.planet-stage .planet-gesture-hint')).toBeTruthy());
    expect(container.querySelector('.planet-stage .planet-gesture-hint').textContent).toBe('w6c.hint.mouse');
    // The old service hints under and over the globe are gone.
    expect(container.querySelector('.planet-select-hint, .planet-stage-caption, .planet-controls-hint')).toBeNull();
    expect(scene.props.autoRotate).toBe(true);
    act(() => scene.props.onInteract());
    expect(container.querySelector('.planet-gesture-hint')).toBeNull();
    expect(scene.props.autoRotate).toBe(false);
    unmount();
    const again = render(<PlanetView countries={countries} valuesByCode={{ DE: 3.2 }} metricName="Безработица" unit="%" />);
    await screen.findByTestId('planet-scene');
    expect(again.container.querySelector('.planet-gesture-hint')).toBeNull();
  });

  it('puts +, - and home on the globe, with labels, and any camera command ends the self-rotation', async () => {
    const { container } = render(<PlanetView countries={countries} valuesByCode={{ DE: 3.2 }} metricName="Безработица" unit="%" />);
    await screen.findByTestId('planet-scene');
    const stack = container.querySelector('.planet-stage .planet-camera-controls');
    expect(stack).toBeTruthy();
    expect([...stack.querySelectorAll('button')].map((button) => button.getAttribute('aria-label'))).toEqual(['planet.zoomIn', 'planet.zoomOut', 'planet.reset']);
    expect([...stack.querySelectorAll('button')].every((button) => button.getAttribute('data-tip'))).toBe(true);
    await waitFor(() => expect(scene.props.autoRotate).toBe(true));
    fireEvent.click(screen.getByRole('button', { name: 'planet.zoomIn' }));
    expect(scene.props.cameraCommand.type).toBe('zoomIn');
    expect(scene.props.autoRotate).toBe(false);
  });

  it('offers a way back when only water is in view, and takes it away when countries return', async () => {
    render(<PlanetView countries={countries} valuesByCode={{ DE: 3.2 }} metricName="Безработица" unit="%" />);
    await screen.findByTestId('planet-scene');
    expect(screen.queryByRole('button', { name: 'w6c.backToCountries' })).toBeNull();
    act(() => scene.props.onOcean(true));
    fireEvent.click(screen.getByRole('button', { name: 'w6c.backToCountries' }));
    expect(scene.props.cameraCommand.type).toBe('reset');
    act(() => scene.props.onOcean(false));
    expect(screen.queryByRole('button', { name: 'w6c.backToCountries' })).toBeNull();
  });

  it('answers a tap on grey land with «no data yet», «soon» and a way to ask, instead of staying silent', async () => {
    const { container } = render(<PlanetView countries={countries} valuesByCode={{ DE: 3.2 }} metricName="Безработица" unit="%" />);
    await screen.findByTestId('planet-scene');
    act(() => scene.props.onSelect(null, { name: 'Чад', code: 'TD' }));
    const card = container.querySelector('.planet-place-card');
    expect(card.textContent).toContain('Чад');
    expect(card.textContent).toContain('w6c.place.noData');
    expect(card.textContent).toContain('w6c.place.soon');
    expect(card.querySelector('a').getAttribute('href')).toMatch(/^mailto:/);
    expect(scene.props.cameraCommand).toMatchObject({ type: 'focus', countryCode: 'TD' });
    // Water closes it.
    act(() => scene.props.onSelect(null, null));
    expect(container.querySelector('.planet-place-card')).toBeNull();
  });

  it('switches the indicator from chips on the globe', async () => {
    const onConceptChange = vi.fn();
    const { container } = render(<PlanetView countries={countries} valuesByCode={{ DE: 3.2 }} metricName="Безработица" unit="%" conceptSlug="unemployment-rate"
      quickConcepts={[{ slug: 'gdp-usd', label: 'ВВП' }, { slug: 'unemployment-rate', label: 'Безработица' }, { slug: 'inflation', label: 'Инфляция' }]} onConceptChange={onConceptChange} />);
    await screen.findByTestId('planet-scene');
    const group = container.querySelector('.planet-stage .planet-quick');
    expect(within(group).getByRole('button', { name: 'Безработица' }).getAttribute('aria-pressed')).toBe('true');
    fireEvent.click(within(group).getByRole('button', { name: 'Инфляция' }));
    expect(onConceptChange).toHaveBeenCalledWith('inflation');
    fireEvent.click(within(group).getByRole('button', { name: 'Безработица' }));
    expect(onConceptChange).toHaveBeenCalledTimes(1);
  });

  it('plays the years up to the last finished one and stops when a person picks a year', async () => {
    vi.useFakeTimers();
    try {
      const onYearChange = vi.fn();
      const years = [2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025, 2026, 2027];
      const props = { countries, valuesByCode: { DE: 3.2 }, metricName: 'ВВП', unit: '%', years, onYearChange, conceptSlug: 'gdp-usd' };
      const { rerender } = render(<PlanetView {...props} year={2025} />);
      await act(async () => { await vi.advanceTimersByTimeAsync(0); });
      fireEvent.click(screen.getByRole('button', { name: /w6c.play.start/ }));
      expect(onYearChange).toHaveBeenLastCalledWith(2018);
      rerender(<PlanetView {...props} year={2018} />);
      await act(async () => { await vi.advanceTimersByTimeAsync(1000); });
      expect(onYearChange).toHaveBeenLastCalledWith(2019);
      // A year chosen by hand ends the playback.
      rerender(<PlanetView {...props} year={2022} />);
      await act(async () => { await vi.advanceTimersByTimeAsync(3000); });
      expect(onYearChange).toHaveBeenCalledTimes(2);
      expect(screen.getByRole('button', { name: /w6c.play.start/ })).toBeTruthy();
    } finally { vi.useRealTimers(); }
  });

  it('marks years that are not facts yet: forecast for a coming year, estimate for the running annual one', async () => {
    const now = new Date();
    const annual = (year) => ({ DE: { ...germanyDetail, date: `${year}-01-01` } });
    const view = (year) => (
      <PlanetView countries={countries} valuesByCode={{ DE: 3.2 }} detailsByCode={annual(year)} metricName="ВВП" unit="%" years={[2023, 2024]} year={year} onYearChange={() => {}} periodLabel={String(year)} />
    );
    const { container, rerender } = render(view(now.getFullYear() + 1));
    await screen.findByTestId('planet-scene');
    expect(container.querySelector('.planet-key-title .planet-tag').textContent).toBe('w6c.tag.forecast');
    rerender(view(now.getFullYear()));
    expect(container.querySelector('.planet-key-title .planet-tag').textContent).toBe('w6c.tag.estimate');
    rerender(view(now.getFullYear() - 2));
    expect(container.querySelector('.planet-key-title .planet-tag')).toBeNull();
  });

  it('switches to the coverage layer: colour shows how many indicators a country has', async () => {
    const withCounts = [
      { code: 'DE', slug: 'germany', name: 'Германия', indicators_count: 400 },
      { code: 'MT', slug: 'malta', name: 'Мальта', indicators_count: 30 },
      { code: 'FR', slug: 'france', name: 'Франция', indicators_count: 380 },
      { code: 'ES', slug: 'spain', name: 'Испания', indicators_count: 210 },
    ];
    const { container } = render(<PlanetView countries={withCounts} valuesByCode={{ DE: 3.2 }} metricName="Безработица" unit="%" />);
    await screen.findByTestId('planet-scene');
    fireEvent.click(screen.getByRole('button', { name: 'w6c.coverage.toggle' }));
    expect(scene.props.valuesByCode.get('DE')).toBe(400);
    expect(scene.props.valuesByCode.get('MT')).toBe(30);
    expect(container.querySelector('.planet-key-title strong').textContent).toBe('w6c.coverage.title');
    expect(container.querySelector('.planet-key-order').textContent).toBe('w6c.key.ruleCoverage');
    fireEvent.click(screen.getByRole('button', { name: 'w6c.coverage.toggle' }));
    expect(scene.props.valuesByCode.get('MT')).toBeUndefined();
  });

  it('turns the sphere layers off when zoomed in: no minimap, glass circle or shadow over the map', async () => {
    const { container } = render(<PlanetView countries={countries} valuesByCode={{ DE: 3.2 }} metricName="Безработица" unit="%" />);
    await screen.findByTestId('planet-scene');
    const stage = container.querySelector('.planet-stage');
    expect(stage.classList.contains('is-zoomed')).toBe(false);
    act(() => scene.props.onView({ lon: 10, lat: 50, distance: 2 }));
    expect(stage.classList.contains('is-zoomed')).toBe(true);
    // The minimap rectangle is gone for good (round 6): nothing in the zoomed view looks like a second map.
    expect(container.querySelector('.planet-minimap')).toBeNull();
    act(() => scene.props.onView({ lon: 10, lat: 50, distance: 3.4 }));
    expect(stage.classList.contains('is-zoomed')).toBe(false);
  });

  it('keeps one block of camera buttons and one bottom row; the card marks the stage so the CSS can hide both', async () => {
    const { container } = render(<PlanetView countries={countries} valuesByCode={new Map([['DE', 3.2], ['MT', 1.7]])} detailsByCode={new Map([['DE', germanyDetail]])} years={[2023, 2024, 2025]} year={2025} onYearChange={() => {}} shareable metricName="Безработица" unit="%" />);
    await screen.findByTestId('planet-scene');
    const stage = container.querySelector('.planet-stage');
    expect(stage.querySelectorAll('.planet-camera-controls').length).toBe(1);
    expect(stage.querySelectorAll('.planet-stage-actions').length).toBe(1);
    expect(stage.querySelector('.planet-stage-actions .planet-round')).toBeTruthy();
    // Glossy round buttons with their own glass are gone: the blocks carry the glass, the buttons are flat.
    expect(stage.querySelector('.planet-camera-controls button.fe-glass-2, .planet-round.fe-glass-2')).toBeNull();
    expect(stage.classList.contains('has-card')).toBe(false);
    fireEvent.click(await screen.findByRole('button', { name: 'Pick Germany' }));
    expect(stage.classList.contains('has-card')).toBe(true);
  });

  it('К1: золота первого места нет ни в модели цвета, ни в легенде', async () => {
    const { container } = render(<PlanetView countries={countries} valuesByCode={{ DE: 3.2, MT: 1.7 }} metricName="Безработица" unit="%" />);
    await screen.findByTestId('planet-scene');
    expect(scene.props.colorModel.isTop).toBeUndefined();
    expect(scene.props.colorModel.hasTop).toBeUndefined();
    expect(container.querySelector('.planet-key-note--top')).toBeNull();
  });

  it('selects the country from a shared link once the catalogue is here', async () => {
    const { container } = render(<PlanetView countries={countries} valuesByCode={{ DE: 3.2 }} metricName="Безработица" unit="%" initialCountry="de" />);
    await screen.findByTestId('planet-scene');
    expect(container.querySelector('[data-selected-country="DE"]')).toBeTruthy();
    expect(scene.props.cameraCommand).toMatchObject({ type: 'focus', countryCode: 'DE', instant: true });
  });

  it('keeps the value in the card as one final number, never a counting-up intermediate', async () => {
    render(<PlanetView countries={countries} valuesByCode={{ DE: 3855 }} detailsByCode={{ DE: germanyDetail }} metricName="ВВП" unit="млрд $" />);
    fireEvent.click(await screen.findByRole('button', { name: 'Pick Germany' }));
    expect(screen.getByLabelText('planet.value').textContent).toMatch(/^3\s?855$/);
  });
});

describe('PlanetView: flat map by default, globe by choice', () => {
  const manyCountries = [
    { code: 'DE', slug: 'germany', name: 'Германия', name_en: 'Germany', indicators_count: 400 },
    { code: 'MT', slug: 'malta', name: 'Мальта', name_en: 'Malta', indicators_count: 30 },
    { code: 'FR', slug: 'france', name: 'Франция', name_en: 'France', indicators_count: 380 },
    { code: 'ES', slug: 'spain', name: 'Испания', name_en: 'Spain', indicators_count: 210 },
  ];
  const switchGroup = () => screen.getByRole('group', { name: 'x8.planet.viewSwitch' });
  const mapButton = () => within(switchGroup()).getByRole('button', { name: /x8.planet.viewMap/ });
  const globeButton = () => within(switchGroup()).getByRole('button', { name: /x8.planet.viewGlobe/ });

  beforeEach(() => {
    window.localStorage.clear();
  });

  it('opens on the flat map with every country at once and never mounts the globe', async () => {
    const { container } = render(<PlanetView countries={countries} valuesByCode={{ DE: 3.2, MT: 1.7 }} detailsByCode={{ DE: germanyDetail }} metricName="Безработица" unit="%" />);
    await screen.findByTestId('fallback-map');
    expect(scene.props).toBeNull();
    expect(screen.queryByTestId('planet-scene')).toBeNull();
    expect(container.querySelector('canvas, .planet-orb, .planet-glass-sphere, .planet-caustic')).toBeNull();
    expect(container.querySelector('.planet-stage').getAttribute('data-planet-surface')).toBe('map');
    expect(container.querySelector('.planet-stage--map')).toBeTruthy();
    expect(scene.mapProps.embedded).toBe(true);
    expect(scene.mapProps.valuesByCode.get('DE')).toBe(3.2);
    expect(scene.mapProps.colorModel).toBeTruthy();
    expect(mapButton().getAttribute('aria-pressed')).toBe('true');
    expect(globeButton().getAttribute('aria-pressed')).toBe('false');
    // Сообщения о сбое нет: карта показана по выбору, а не вместо шара.
    expect(screen.queryByText('planet.unavailable')).toBeNull();
  });

  it('keeps the colour legend, ranking list, search and year picker on the map', async () => {
    const { container } = render(<PlanetView countries={countries} valuesByCode={{ DE: 3.2, MT: 1.7 }} metricName="Безработица" unit="%" years={[2024, 2025]} year={2025} onYearChange={() => {}} />);
    await screen.findByTestId('fallback-map');
    expect(container.querySelector('.planet-key .planet-key-bar')).toBeTruthy();
    expect(container.querySelector('.planet-scale summary')).toBeTruthy();
    expect(countryList().getAllByRole('button').length).toBe(2);
    expect(screen.getByRole('combobox')).toBeTruthy();
    expect(container.querySelector('.planet-year')).toBeTruthy();
    expect(container.querySelector('.planet-shell').classList.contains('has-key')).toBe(true);
  });

  it('lays the map out in flow: chips above, plate with its own proportions, one tools row below, selected-country card inside the map window', async () => {
    const quick = [{ slug: 'a', label: 'ВВП' }, { slug: 'b', label: 'Безработица' }];
    const { container } = render(<PlanetView countries={countries} valuesByCode={{ DE: 3.2, MT: 1.7 }} detailsByCode={{ DE: germanyDetail }} metricName="Безработица" unit="%"
      quickConcepts={quick} conceptSlug="a" shareable years={[2024, 2025]} year={2025} onYearChange={() => {}} onSelect={() => {}} />);
    await screen.findByTestId('fallback-map');
    const stage = container.querySelector('.planet-stage--map');
    expect(container.querySelector('.planet-shell').classList.contains('planet-shell--map')).toBe(true);
    const order = [...stage.children].map((node) => node.className.split(' ')[0]);
    expect(order).toEqual(['planet-quick', 'planet-map-stage', 'planet-map-legend', 'planet-map-tools']);
    // Кнопки масштаба и действия лежат под картой, а не поверх неё.
    const tools = stage.querySelector('.planet-map-tools');
    expect(tools.querySelector('.planet-camera-controls')).toBeTruthy();
    expect(tools.querySelector('.planet-stage-actions')).toBeTruthy();
    expect(stage.querySelector('.planet-map-stage .planet-camera-controls')).toBeNull();
    // Круг 9 (H3): карточка страны лежит внутри окна карты (на нижнем краю или под картой в узком окне), а не добавляет строку ниже кнопок.
    fireEvent.click(screen.getByText('Select on map'));
    const card = stage.querySelector('.planet-map-stage .planet-stage-bottom .planet-country-card.is-selected');
    expect(card).toBeTruthy();
    expect(stage.querySelector(':scope > .planet-stage-bottom')).toBeNull();
    expect(card.textContent).toContain('Германия');
  });

  it('puts the concept note next to the legend title and keeps «how to read colours» as a small button with a text label', async () => {
    const { container } = render(<PlanetView countries={countries} valuesByCode={{ DE: 3.2, MT: 1.7 }} metricName="ВВП" unit="%" conceptNote={<span data-testid="note">i</span>} />);
    await screen.findByTestId('fallback-map');
    expect(container.querySelector('.planet-key-title [data-testid="note"]')).toBeTruthy();
    const summary = container.querySelector('.planet-scale summary');
    expect(summary.querySelector('.planet-scale-text').textContent).toBe('planet.legend');
    expect(summary.getAttribute('title')).toBe('planet.legend');
  });

  it('switches Map and Globe, remembers the choice and unmounts the other surface', async () => {
    const { container } = render(<PlanetView countries={countries} valuesByCode={{ DE: 3.2 }} metricName="Безработица" unit="%" />);
    await screen.findByTestId('fallback-map');
    fireEvent.click(globeButton());
    await screen.findByTestId('planet-scene');
    // Плоская карта под шаром остаётся только как приглушённая заставка на время загрузки сцены, затем снимается.
    await waitFor(() => expect(screen.queryByTestId('fallback-map')).toBeNull());
    expect(container.querySelector('.planet-stage--map')).toBeNull();
    expect(window.localStorage.getItem('fe_planet_view')).toBe('globe');
    expect(globeButton().getAttribute('aria-pressed')).toBe('true');
    expect(mapButton().getAttribute('aria-pressed')).toBe('false');
    await waitFor(() => expect(container.querySelector('[data-scene-ready="true"]')).toBeTruthy());
    expect(container.querySelector('.planet-stage').getAttribute('data-planet-surface')).toBe('globe');
    fireEvent.click(mapButton());
    expect(screen.queryByTestId('planet-scene')).toBeNull();
    await screen.findByTestId('fallback-map');
    expect(window.localStorage.getItem('fe_planet_view')).toBe('map');
    expect(container.querySelector('[data-scene-ready="true"]')).toBeNull();
  });

  it('opens on the globe only when the person chose it before', async () => {
    window.localStorage.setItem('fe_planet_view', 'globe');
    render(<PlanetView countries={countries} valuesByCode={{ DE: 3.2 }} metricName="Безработица" unit="%" />);
    await screen.findByTestId('planet-scene');
    await waitFor(() => expect(screen.queryByTestId('fallback-map')).toBeNull());
    expect(globeButton().getAttribute('aria-pressed')).toBe('true');
  });

  it('works without storage: the map by default and a switch that still works', async () => {
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => { throw new Error('blocked'); });
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => { throw new Error('blocked'); });
    render(<PlanetView countries={countries} valuesByCode={{ DE: 3.2 }} metricName="Безработица" unit="%" />);
    await screen.findByTestId('fallback-map');
    fireEvent.click(globeButton());
    await screen.findByTestId('planet-scene');
    fireEvent.click(mapButton());
    await screen.findByTestId('fallback-map');
  });

  it('labels the switch for assistive tech and gives both parts a visible caption', async () => {
    render(<PlanetView countries={countries} valuesByCode={{ DE: 3.2 }} metricName="Безработица" unit="%" />);
    await screen.findByTestId('fallback-map');
    expect(switchGroup()).toBeTruthy();
    expect(mapButton().textContent).toBe('x8.planet.viewMap');
    expect(globeButton().textContent).toBe('x8.planet.viewGlobe');
    expect(mapButton().querySelector('svg')).toBeTruthy();
    expect(globeButton().querySelector('svg')).toBeTruthy();
  });

  it('keeps the selected country and its card when switching in both directions; the globe camera starts on the country', async () => {
    const onSelect = vi.fn();
    const { container } = render(<PlanetView countries={countries} valuesByCode={{ DE: 3.2, MT: 1.7 }} detailsByCode={{ DE: germanyDetail }} metricName="Безработица" unit="%" onSelect={onSelect} />);
    await screen.findByTestId('fallback-map');
    fireEvent.click(screen.getByRole('button', { name: 'Select on map' }));
    expect(container.querySelector('[data-selected-country="DE"]')).toBeTruthy();
    expect(scene.mapProps.selectedCode).toBe('DE');
    expect(scene.mapProps.command).toMatchObject({ type: 'focus', countryCode: 'DE' });
    expect(onSelect).not.toHaveBeenCalled();
    fireEvent.click(globeButton());
    await screen.findByTestId('planet-scene');
    expect(scene.props.selectedCode).toBe('DE');
    expect(scene.props.cameraCommand).toMatchObject({ type: 'focus', countryCode: 'DE', instant: true });
    expect(scene.props.autoRotate).toBe(false);
    expect(container.querySelector('[data-selected-country="DE"]')).toBeTruthy();
    fireEvent.click(mapButton());
    await screen.findByTestId('fallback-map');
    expect(scene.mapProps.selectedCode).toBe('DE');
    expect(container.querySelector('[data-selected-country="DE"]')).toBeTruthy();
  });

  it('resets the camera on a return to the globe when nothing is selected', async () => {
    render(<PlanetView countries={countries} valuesByCode={{ DE: 3.2 }} metricName="Безработица" unit="%" />);
    await screen.findByTestId('fallback-map');
    fireEvent.click(screen.getByRole('button', { name: 'map.zoomIn' }));
    expect(scene.mapProps.command.type).toBe('zoomIn');
    fireEvent.click(globeButton());
    await screen.findByTestId('planet-scene');
    expect(scene.props.cameraCommand).toBeNull();
    await waitFor(() => expect(scene.props.autoRotate).toBe(true));
  });

  it('first press on a map country previews it, the second press on the same one opens it', async () => {
    const onSelect = vi.fn();
    const { container } = render(<PlanetView countries={countries} valuesByCode={{ DE: 3.2 }} detailsByCode={{ DE: germanyDetail }} metricName="Безработица" unit="%" onSelect={onSelect} />);
    await screen.findByTestId('fallback-map');
    fireEvent.click(screen.getByRole('button', { name: 'Select on map' }));
    expect(onSelect).not.toHaveBeenCalled();
    expect(container.querySelector('.planet-value-line strong').textContent).toBe('3,20');
    fireEvent.click(screen.getByRole('button', { name: 'Select on map' }));
    expect(onSelect).toHaveBeenCalledWith(countries[0], germanyDetail);
  });

  it('finds any country by search on the map and sends the map a focus command (small states included)', async () => {
    const { container } = render(<PlanetView countries={countries} />);
    await screen.findByTestId('fallback-map');
    const search = screen.getByRole('combobox');
    fireEvent.focus(search);
    fireEvent.change(search, { target: { value: 'Мальта' } });
    fireEvent.keyDown(search, { key: 'Enter' });
    expect(scene.mapProps.selectedCode).toBe('MT');
    expect(scene.mapProps.command).toMatchObject({ type: 'focus', countryCode: 'MT', instant: true });
    expect(container.querySelector('[data-selected-country="MT"]')).toBeTruthy();
  });

  it('names the hovered country with a label on the map and drops it on leave; touch screens get no sticky label', async () => {
    const { container, unmount } = render(<PlanetView countries={countries} valuesByCode={{ DE: 3.2 }} metricName="Безработица" unit="%" />);
    await screen.findByTestId('fallback-map');
    expect(typeof scene.mapProps.onHover).toBe('function');
    act(() => scene.mapProps.onHover('DE'));
    expect(container.querySelector('.planet-hover-label').textContent).toContain('Германия');
    expect(container.querySelector('.planet-hover-label small').textContent).toBe('planet.pressToSelect');
    act(() => scene.mapProps.onHover(null));
    expect(container.querySelector('.planet-hover-label')).toBeNull();
    unmount();
    const originalMatchMedia = window.matchMedia;
    window.matchMedia = vi.fn().mockImplementation((query) => ({ matches: query === '(pointer: coarse)', addEventListener: () => {}, removeEventListener: () => {} }));
    try {
      render(<PlanetView countries={countries} valuesByCode={{ DE: 3.2 }} metricName="Безработица" unit="%" />);
      await screen.findByTestId('fallback-map');
      expect(scene.mapProps.onHover).toBeUndefined();
    } finally {
      window.matchMedia = originalMatchMedia;
    }
  });

  it('drives the map with the same +, − and home buttons (map captions) and clearing the selection resets the view', async () => {
    const { container } = render(<PlanetView countries={countries} valuesByCode={{ DE: 3.2 }} metricName="Безработица" unit="%" />);
    await screen.findByTestId('fallback-map');
    const stack = container.querySelector('.planet-stage .planet-camera-controls');
    expect([...stack.querySelectorAll('button')].map((button) => button.getAttribute('aria-label'))).toEqual(['map.zoomIn', 'map.zoomOut', 'map.zoomReset']);
    fireEvent.click(screen.getByRole('button', { name: 'map.zoomOut' }));
    expect(scene.mapProps.command.type).toBe('zoomOut');
    fireEvent.click(screen.getByRole('button', { name: 'map.zoomReset' }));
    expect(scene.mapProps.command.type).toBe('reset');
  });

  it('keeps indicator chips, years with Play, the coverage layer and Share on the map', async () => {
    const onConceptChange = vi.fn();
    const onYearChange = vi.fn();
    const { container } = render(<PlanetView countries={manyCountries} valuesByCode={{ DE: 3.2 }} metricName="Безработица" unit="%" conceptSlug="unemployment-rate"
      years={[2018, 2019, 2020, 2021]} year={2021} onYearChange={onYearChange} shareable
      quickConcepts={[{ slug: 'gdp-usd', label: 'ВВП' }, { slug: 'unemployment-rate', label: 'Безработица' }]} onConceptChange={onConceptChange} />);
    await screen.findByTestId('fallback-map');
    const chips = container.querySelector('.planet-stage .planet-quick');
    expect(chips).toBeTruthy();
    fireEvent.click(within(chips).getByRole('button', { name: 'ВВП' }));
    expect(onConceptChange).toHaveBeenCalledWith('gdp-usd');
    expect(screen.getByRole('button', { name: /w6c.play.start/ })).toBeTruthy();
    expect(screen.getByRole('button', { name: 'w6c.share' })).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: 'w6c.coverage.toggle' }));
    expect(scene.mapProps.valuesByCode.get('DE')).toBe(400);
    expect(scene.mapProps.valuesByCode.get('MT')).toBe(30);
    expect(container.querySelector('.planet-key-title strong').textContent).toBe('w6c.coverage.title');
    expect(screen.queryByTestId('planet-scene')).toBeNull();
  });

  it('shows the year Play overlay over the map and keeps the chips on top of the same stage as the globe', async () => {
    vi.useFakeTimers();
    try {
      const onYearChange = vi.fn();
      render(<PlanetView countries={countries} valuesByCode={{ DE: 3.2 }} metricName="ВВП" unit="%" years={[2018, 2019, 2020, 2021, 2022]} year={2022} onYearChange={onYearChange} conceptSlug="gdp-usd" />);
      await act(async () => { await vi.advanceTimersByTimeAsync(0); });
      fireEvent.click(screen.getByRole('button', { name: /w6c.play.start/ }));
      expect(onYearChange).toHaveBeenLastCalledWith(2018);
      expect(screen.getByRole('status').textContent).toContain('2022');
    } finally {
      vi.useRealTimers();
    }
  });

  it('hides the Earth/Data layer switch and the globe gesture hint on the map and brings them back with the globe', async () => {
    const { container } = render(<PlanetView initialMode="earth" showLayerSwitch countries={countries} valuesByCode={{ DE: 3.2 }} metricName="Безработица" unit="%" />);
    await screen.findByTestId('fallback-map');
    expect(container.querySelector('.planet-layer-switch')).toBeNull();
    expect(container.querySelector('.planet-gesture-hint')).toBeNull();
    // Режим «Земля без данных» бывает только у шара: у карты легенда цветов на месте.
    expect(container.querySelector('.planet-key')).toBeTruthy();
    fireEvent.click(globeButton());
    await screen.findByTestId('planet-scene');
    expect(container.querySelector('.planet-layer-switch')).toBeTruthy();
    expect(scene.props.mode).toBe('earth');
    expect(container.querySelector('.planet-key')).toBeNull();
  });

  it('does not use up the globe gesture hint while the person only used the map', async () => {
    const { container } = render(<PlanetView countries={countries} valuesByCode={{ DE: 3.2 }} metricName="Безработица" unit="%" />);
    await screen.findByTestId('fallback-map');
    fireEvent.click(screen.getByRole('button', { name: 'map.zoomIn' }));
    expect(window.localStorage.getItem('fe_planet_hint_seen')).toBeNull();
    fireEvent.click(globeButton());
    await screen.findByTestId('planet-scene');
    await waitFor(() => expect(container.querySelector('.planet-gesture-hint')).toBeTruthy());
  });

  it('falls back to the map with the message and Retry when the globe fails to start; the choice is not stuck on the globe', async () => {
    scene.fail = true;
    vi.spyOn(console, 'warn').mockImplementation(() => {});
    const { container } = render(<PlanetView countries={countries} detailsByCode={{ DE: germanyDetail }} />);
    await screen.findByTestId('fallback-map');
    expect(screen.queryByText('planet.unavailable')).toBeNull();
    fireEvent.click(globeButton());
    await screen.findByText('planet.unavailable');
    expect(screen.getByTestId('fallback-map')).toBeTruthy();
    expect(mapButton().getAttribute('aria-pressed')).toBe('true');
    expect(window.localStorage.getItem('fe_planet_view')).toBe('map');
    // «Карта» убирает сообщение; «Повторить» возвращает шар, как только он снова запускается.
    fireEvent.click(mapButton());
    expect(screen.queryByText('planet.unavailable')).toBeNull();
    fireEvent.click(globeButton());
    await screen.findByText('planet.unavailable');
    scene.fail = false;
    fireEvent.click(screen.getByRole('button', { name: 'planet.retry' }));
    await screen.findByTestId('planet-scene');
    await waitFor(() => expect(container.querySelector('[data-scene-ready="true"]')).toBeTruthy());
    expect(window.localStorage.getItem('fe_planet_view')).toBe('globe');
    expect(screen.queryByText('planet.unavailable')).toBeNull();
  });

  it('places the view switch above the scene and the stage keeps one slot for both surfaces', async () => {
    const { container } = render(<PlanetView countries={countries} valuesByCode={{ DE: 3.2 }} metricName="Безработица" unit="%" />);
    await screen.findByTestId('fallback-map');
    const shell = container.querySelector('.planet-shell');
    const children = [...shell.children].map((node) => node.className.split(' ')[0]);
    expect(children.indexOf('planet-viewbar')).toBe(0);
    expect(container.querySelectorAll('.planet-stage').length).toBe(1);
    fireEvent.click(globeButton());
    await screen.findByTestId('planet-scene');
    expect(container.querySelectorAll('.planet-stage').length).toBe(1);
  });

  it('explains the map colours in one line: grey for no data only, no gold first place (round 10, К1)', async () => {
    window.localStorage.setItem('fe_planet_view', 'map');
    const { container } = render(<PlanetView countries={countries} valuesByCode={{ DE: 3.2, MT: 1.7 }} metricName="Безработица" unit="%" />);
    await screen.findByTestId('fallback-map');
    const legend = container.querySelector('.planet-map-stage + .planet-map-legend');
    expect(legend).toBeTruthy();
    expect(legend.textContent).toContain('c8w.map.noData');
    expect(legend.textContent).not.toContain('c8w.map.top');
    expect(legend.querySelectorAll('i')).toHaveLength(1);
  });

  it('keeps the flat map under the globe while the scene loads, with its own caption, and hands over when ready (round 8, wave 2)', async () => {
    scene.hold = true;
    window.localStorage.setItem('fe_planet_view', 'globe');
    const { container } = render(<PlanetView countries={countries} valuesByCode={{ DE: 3.2 }} metricName="Безработица" unit="%" />);
    await screen.findByTestId('planet-scene');
    const veil = container.querySelector('.planet-globe-veil');
    expect(veil).toBeTruthy();
    expect(veil.querySelector('.planet-map-stage').getAttribute('aria-hidden')).toBe('true');
    expect(within(veil).getByRole('status').textContent).toBe('c8w.globe.loading');
    expect(container.querySelector('.planet-stage').getAttribute('data-planet-surface')).toBe('globe');
    // Сцена готова: заставка плавно гаснет, затем снимается.
    act(() => { scene.props.onReady(); });
    await waitFor(() => expect(container.querySelector('.planet-globe-veil')).toBeNull());
  });

  it('keeps the map when the globe scene fails while the veil is up (round 8, wave 2)', async () => {
    scene.hold = true;
    vi.spyOn(console, 'warn').mockImplementation(() => {});
    window.localStorage.setItem('fe_planet_view', 'globe');
    const { container } = render(<PlanetView countries={countries} valuesByCode={{ DE: 3.2 }} metricName="Безработица" unit="%" />);
    await screen.findByTestId('planet-scene');
    act(() => { scene.props.onError(new Error('No WebGL')); });
    await screen.findByText('planet.unavailable');
    expect(container.querySelector('.planet-globe-veil')).toBeNull();
    expect(container.querySelector('.planet-stage--map [data-testid="fallback-map"]')).toBeTruthy();
  });
});

describe('PlanetView: круг 9, зона B', () => {
  const withRussia = [
    { code: 'RU', slug: 'russia', name: 'Россия', name_en: 'Russia' },
    { code: 'US', slug: 'united-states', name: 'США', name_en: 'United States' },
  ];

  it('P12: у шара есть кнопка «К России», она подводит камеру к своей стране; на плоской карте её нет', async () => {
    const { container, rerender } = render(<PlanetView countries={withRussia} valuesByCode={{ RU: 2.2, US: 4.1 }} homeCountryCode="RU" metricName="Безработица" unit="%" />);
    const home = await screen.findByRole('button', { name: 'c9b.planet.toRussia' });
    fireEvent.click(home);
    await waitFor(() => expect(scene.props.cameraCommand).toMatchObject({ type: 'focus', countryCode: 'RU' }));
    // Без своей страны в каталоге кнопки нет.
    rerender(<PlanetView countries={[withRussia[1]]} valuesByCode={{ US: 4.1 }} homeCountryCode="RU" metricName="Безработица" unit="%" />);
    expect(screen.queryByRole('button', { name: 'c9b.planet.toRussia' })).toBeNull();
    expect(container.querySelector('.planet-home-button')).toBeNull();
  });

  it('P12: на плоской карте мир виден целиком, кнопка «К России» не рисуется', async () => {
    window.localStorage.setItem('fe_planet_view', 'map');
    render(<PlanetView countries={withRussia} valuesByCode={{ RU: 2.2, US: 4.1 }} homeCountryCode="RU" metricName="Безработица" unit="%" />);
    await screen.findByTestId('fallback-map');
    expect(screen.queryByRole('button', { name: 'c9b.planet.toRussia' })).toBeNull();
  });

  it('К1: под картой подписан только серый «нет данных», золота первого места нет', async () => {
    window.localStorage.setItem('fe_planet_view', 'map');
    const { container } = render(<PlanetView countries={withRussia} valuesByCode={{ RU: 5.6, US: 4.1 }} metricName="Инфляция" unit="%" />);
    await screen.findByTestId('fallback-map');
    const legend = container.querySelector('.planet-map-legend').textContent;
    expect(legend).toContain('c8w.map.noData');
    expect(legend).not.toContain('c8w.map.top');
  });

  it('H3: кнопки управления не имеют собственных title: нативная подсказка не зависает после ухода курсора', async () => {
    const { container } = render(<PlanetView countries={withRussia} valuesByCode={{ RU: 2.2, US: 4.1 }} metricName="Безработица" unit="%" />);
    await screen.findByTestId('planet-scene');
    for (const button of container.querySelectorAll('.planet-camera-controls button')) {
      expect(button.getAttribute('title')).toBeNull();
      expect(button.getAttribute('aria-label')).toBeTruthy();
    }
  });
});
