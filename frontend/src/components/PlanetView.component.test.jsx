import { useEffect } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import PlanetView from './PlanetView';

const scene = vi.hoisted(() => ({ fail: false, props: null }));

vi.mock('../i18n', () => ({
  useT: () => (key, vars) => (vars?.count == null ? key : `${key}: ${vars.count}`),
  useLocale: () => ({ locale: 'ru' }),
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
const germanyDetail = { country_code: 'DE', country_slug: 'germany', date: '2026-06-01', value: 3.2, indicator_code: 'unemployment-rate' };

beforeEach(() => {
  scene.fail = false;
  scene.props = null;
});

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

  it('finds a microstate by code using the keyboard without opening automatically', async () => {
    const onSelect = vi.fn();
    const { container } = render(<PlanetView countries={countries} onSelect={onSelect} />);
    const input = screen.getByRole('combobox');
    act(() => input.focus());
    fireEvent.change(input, { target: { value: 'mt' } });
    expect(screen.getAllByRole('option')).toHaveLength(1);
    fireEvent.keyDown(input, { key: 'Enter' });
    await waitFor(() => expect(scene.props.selectedCode).toBe('MT'));
    expect(scene.props.cameraCommand).toMatchObject({ type: 'focus', countryCode: 'MT' });
    expect(screen.queryByRole('listbox')).toBeNull();
    const card = container.querySelector('[data-selected-country="MT"]');
    expect(document.activeElement).toBe(card);
    expect(input.getAttribute('aria-expanded')).toBe('false');
    expect(onSelect).not.toHaveBeenCalled();

    // Choosing the same country again must still close search and leave focus
    // on the result, even though selectedCode itself does not change.
    act(() => input.focus());
    fireEvent.change(input, { target: { value: 'mt' } });
    fireEvent.keyDown(input, { key: 'Enter' });
    expect(screen.queryByRole('listbox')).toBeNull();
    expect(document.activeElement).toBe(card);
    fireEvent.click(screen.getByRole('button', { name: 'planet.openCountry' }));
    expect(onSelect).toHaveBeenCalledWith(countries[1], null);
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

  it('explains data colours with visible numeric endpoints, units and each interval', async () => {
    render(<PlanetView countries={countries} valuesByCode={{ DE: -5, MT: 10 }} unit="%" metricName="Сальдо" colorMode="diverging" initialMode="data" />);
    await screen.findByTestId('planet-scene');
    expect(screen.getByText('-5,00')).toBeTruthy();
    expect(screen.getByText('10,00')).toBeTruthy();
    expect(screen.getByText('%')).toBeTruthy();
    expect(screen.getByText('world.map.scaleZero')).toBeTruthy();
    const swatches = screen.getAllByRole('img');
    expect(swatches).toHaveLength(7);
    expect(swatches[0].getAttribute('title')).toContain('≤ -6,67 %');
    expect(swatches[3].getAttribute('aria-label')).toContain('0,00 %');
    expect(swatches[6].getAttribute('title')).toContain('≥ 6,67 %');
  });

  it('keeps the country selected across views and opens the current observation after the period changes', async () => {
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
    fireEvent.click(screen.getByRole('button', { name: 'planet.map' }));
    await screen.findByTestId('fallback-map');

    const currentDetail = { ...germanyDetail, date: '2026-07-01', value: 5.1 };
    rerender(<PlanetView {...initialProps} detailsByCode={{ DE: currentDetail }} valuesByCode={{ DE: 5.1 }} />);
    expect(container.querySelector('[data-selected-country="DE"]')).toBeTruthy();
    expect(screen.getByText('июль 2026')).toBeTruthy();
    expect(screen.queryByText('июнь 2026')).toBeNull();
    expect(screen.getByLabelText('planet.value').textContent).toBe('5,10');

    fireEvent.click(screen.getByRole('button', { name: 'planet.earth' }));
    await screen.findByTestId('planet-scene');
    expect(scene.props.selectedCode).toBe('DE');
    expect(scene.props.mode).toBe('data');
    expect(onSelect).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: 'planet.openIndicator' }));
    expect(onSelect).toHaveBeenCalledWith(countries[0], currentDetail);
  });

  it('falls back after a scene error and retains country selection and CTA', async () => {
    scene.fail = true;
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
