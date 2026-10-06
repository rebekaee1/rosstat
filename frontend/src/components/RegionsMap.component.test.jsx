// Т-13: RegionsMap — choropleth + hover-outline из той же геометрии, что fill.
import { describe, it, expect } from 'vitest';
import { render, fireEvent } from '@testing-library/react';
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
    expect(colored.length).toBeGreaterThan(0);
    const fills = new Set(colored.map((p) => p.getAttribute('fill')));
    expect(fills.has(neutral.getAttribute('fill'))).toBe(false);
  });

  it('hover-outline использует тот же path d, что и fill региона', () => {
    const target = mapData.regions[0];
    const { container } = renderMap();
    const fillPath = container.querySelector(`svg path[data-region-slug="${target.slug}"]`);
    expect(fillPath).toBeTruthy();
    fireEvent.mouseMove(fillPath);
    const outline = container.querySelector(`svg path[data-hover-outline="${target.slug}"]`);
    expect(outline).toBeTruthy();
    expect(outline.getAttribute('d')).toBe(fillPath.getAttribute('d'));
    expect(outline.getAttribute('d')).toBe(target.path);
    expect(outline.getAttribute('fill')).toBe('none');
    expect(outline.getAttribute('stroke')).toBe('#3D5F9E');
  });

  it('dark compact: ледяная заливка, тонкие обводки, светлый hover-stroke', () => {
    const target = mapData.regions[0];
    const { container } = renderMap({ variant: 'compact', theme: 'dark' });
    const svg = container.querySelector('svg');
    expect(svg?.getAttribute('viewBox')).toBe('8 6 984 526');
    const fillPath = container.querySelector(`svg path[data-region-slug="${target.slug}"]`);
    expect(fillPath.getAttribute('fill')).toBe('#B9CCE8');
    expect(fillPath.getAttribute('stroke-width')).toBe('0.35');
    fireEvent.mouseMove(fillPath);
    const outline = container.querySelector(`svg path[data-hover-outline="${target.slug}"]`);
    expect(outline.getAttribute('stroke')).toBe('#FFFFFF');
  });

  it('brandMark сидит в обёртке SVG, не уезжает к легенде', () => {
    const values = new Map([[mapData.regions[0].slug, 42]]);
    const { container } = renderMap({ valuesBySlug: values, brandMark: true });
    const brand = [...container.querySelectorAll('[data-no-export="true"]')]
      .find((el) => el.textContent?.includes('Forecast Economy'));
    expect(brand).toBeTruthy();
    const mapWrap = container.querySelector('svg')?.parentElement;
    expect(mapWrap?.contains(brand)).toBe(true);
    expect(container.textContent).toMatch(/42/);
  });

  it('живая карта с полями: Чукотка и Камчатка не упираются в рамку', () => {
    const { container } = renderMap();
    expect(container.querySelector('svg').getAttribute('viewBox')).toBe('-8 -8 1016 554');
  });

  it('кнопки «+» и «−» стоят в строке под картой, а не поверх неё; водяной знак — там же, мелко', () => {
    const { container } = renderMap({ brandMark: true });
    const bar = container.querySelector('.fe-map-bar');
    expect(bar.previousElementSibling.tagName.toLowerCase()).toBe('svg');
    expect(bar.querySelectorAll('button').length).toBeGreaterThanOrEqual(2);
    expect(bar.textContent).toContain('Forecast Economy');
    expect(container.querySelector('.absolute')).toBeNull();
  });

  it('подпись шкалы не переносится: значения и единица одной строкой', () => {
    const values = new Map(mapData.regions.slice(0, 4).map((r, i) => [r.slug, 40588 + i * 50000]));
    const { container } = renderMap({ valuesBySlug: values, unit: 'рублей' });
    const legend = container.querySelector('.fe-map-legend');
    expect(legend.textContent).toContain('40\u00A0588');
    expect(legend.textContent).toContain('\u00A0₽');
  });

  it('касание пальцем: первое выбирает регион и показывает карточку, переход — по «Открыть»', () => {
    const calls = [];
    const target = mapData.regions[0];
    const { container } = renderMap({ onSelect: (slug) => calls.push(slug), nameBySlug: { [target.slug]: 'Регион А' } });
    const path = container.querySelector(`svg path[data-region-slug="${target.slug}"]`);
    fireEvent.pointerDown(path, { pointerType: 'touch' });
    fireEvent.click(path);
    expect(calls).toEqual([]);
    const card = container.querySelector('.fe-map-pick');
    expect(card).toBeTruthy();
    expect(card.textContent).toContain('Регион А');
    expect(container.querySelector(`svg path[data-hover-outline="${target.slug}"]`)).toBeTruthy();
    fireEvent.click(card.querySelector('.fe-map-pick__open'));
    expect(calls).toEqual([target.slug]);
  });

  it('мышь: клик открывает регион сразу, без карточки', () => {
    const calls = [];
    const target = mapData.regions[0];
    const { container } = renderMap({ onSelect: (slug) => calls.push(slug) });
    const path = container.querySelector(`svg path[data-region-slug="${target.slug}"]`);
    fireEvent.pointerDown(path, { pointerType: 'mouse' });
    fireEvent.click(path);
    expect(calls).toEqual([target.slug]);
    expect(container.querySelector('.fe-map-pick')).toBeNull();
  });
});
