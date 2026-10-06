/** @vitest-environment jsdom */
import { afterEach, describe, expect, it } from 'vitest';
import { cleanup, render } from '@testing-library/react';
import ChartGlassDefs from './ChartGlassDefs';
import { useChartGlassIds } from '../lib/chartHooks';
import { CHART_THEME, RIBBON_STOPS } from '../lib/chartTheme';

afterEach(cleanup);

function Probe({ onIds }) {
  const ids = useChartGlassIds('t');
  onIds(ids);
  return (
    <svg>
      <defs>
        <ChartGlassDefs ids={ids} />
      </defs>
    </svg>
  );
}

describe('ChartGlassDefs', () => {
  it('рисует все градиенты ленты с разными id, без запрещённых символов в id', () => {
    let ids;
    const { container } = render(<Probe onIds={(v) => { ids = v; }} />);
    for (const [name, id] of Object.entries(ids)) {
      expect(id).toMatch(/^[A-Za-z0-9_-]+$/);
      // «Луч» рисует свой градиент сам (ему нужны координаты плота), в общем наборе только его id.
      if (name !== 'beam') expect(container.querySelector(`[id="${id}"]`)).not.toBeNull();
    }
    expect(new Set(Object.values(ids)).size).toBe(Object.values(ids).length);
  });

  it('золотая лента идёт по длине линии тремя оттенками из темы', () => {
    let ids;
    const { container } = render(<Probe onIds={(v) => { ids = v; }} />);
    const ribbon = container.querySelector(`[id="${ids.ribbon}"]`);
    expect(ribbon.getAttribute('x2')).toBe('1');
    expect(ribbon.getAttribute('y2')).toBe('0');
    const colors = [...ribbon.querySelectorAll('stop')].map((stop) => stop.getAttribute('stop-color'));
    expect(colors).toEqual(RIBBON_STOPS.map((stop) => stop.color));
    expect(colors[0]).toBe(CHART_THEME.goldLight);
  });

  it('заливка под лентой уходит в ноль у оси; градиента диапазона прогноза нет', () => {
    let ids;
    const { container } = render(<Probe onIds={(v) => { ids = v; }} />);
    const area = container.querySelector(`[id="${ids.area}"]`);
    const stops = [...area.querySelectorAll('stop')];
    expect(Number(stops[0].getAttribute('stop-opacity'))).toBeCloseTo(0.35);
    expect(Number(stops[1].getAttribute('stop-opacity'))).toBe(0);
    expect(ids.prism).toBeUndefined();
    expect(container.querySelector('[id$="-prism"]')).toBeNull();
  });

  it('с известной шириной градиенты ленты привязаны к графику (userSpaceOnUse): плоская линия не пропадает', () => {
    const ids = {
      ribbon: 'r', sapphire: 's', area: 'a', areaSapphire: 'as', forecast: 'f', bar: 'b', barForecast: 'bf', bead: 'bd',
    };
    const { container } = render(<svg><defs><ChartGlassDefs ids={ids} width={640} /></defs></svg>);
    for (const id of ['r', 's', 'f']) {
      const gradient = container.querySelector(`[id="${id}"]`);
      expect(gradient.getAttribute('gradientUnits')).toBe('userSpaceOnUse');
      expect(gradient.getAttribute('x2')).toBe('640');
    }
    // Вертикальная заливка под линией остаётся в долях рамки: у залитой фигуры высота есть всегда.
    expect(container.querySelector('[id="a"]').getAttribute('gradientUnits')).toBeNull();
  });
});
