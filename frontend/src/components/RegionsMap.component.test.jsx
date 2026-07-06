// Т-13: RegionsMap — choropleth рендерит все субъекты и красит их по данным.
import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import RegionsMap from './RegionsMap';
import mapData from '../lib/regionsMap.json';

function renderMap(props = {}) {
  return render(
    <MemoryRouter>
      <RegionsMap {...props} />
    </MemoryRouter>,
  );
}

describe('RegionsMap', () => {
  it('рендерит SVG-полигон для каждого региона из геометрии', () => {
    const { container } = renderMap();
    const paths = container.querySelectorAll('svg path[role="button"]');
    expect(paths.length).toBe(mapData.regions.length);
  });

  it('красит регионы со значениями и оставляет прочие нейтральными', () => {
    const values = new Map(
      mapData.regions.slice(0, 5).map((r, i) => [r.slug, (i + 1) * 10]),
    );
    const { container } = renderMap({ valuesBySlug: values, unit: '%' });
    const paths = [...container.querySelectorAll('svg path[role="button"]')];
    const colored = paths.filter((p) => values.has(p.getAttribute('aria-label')));
    const neutral = paths.find((p) => !values.has(p.getAttribute('aria-label')));
    // aria-label = slug (nameBySlug не передан) — надёжный идентификатор.
    expect(colored.length).toBeGreaterThan(0);
    const fills = new Set(colored.map((p) => p.getAttribute('fill')));
    expect(fills.has(neutral.getAttribute('fill'))).toBe(false);
  });
});
