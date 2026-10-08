import { beforeEach, describe, expect, it } from 'vitest';
import { render } from '@testing-library/react';
import PlanetPlaceholder from './PlanetPlaceholder';

describe('PlanetPlaceholder', () => {
  beforeEach(() => { window.localStorage.clear(); });

  it('повторяет раскладку настоящей карточки: переключатель, поиск и год, сцена, легенда, рейтинг из бегущих строк', () => {
    const { container } = render(<PlanetPlaceholder />);
    expect(container.querySelector('[aria-busy="true"].planet-host')).toBeTruthy();
    const shell = container.querySelector('.planet-shell.has-key');
    expect(shell).toBeTruthy();
    // Те же блоки и классы, что у PlanetView: размеры совпадают, страница при подмене не прыгает.
    expect(shell.firstElementChild.classList.contains('planet-viewbar')).toBe(true);
    expect(shell.querySelector('.planet-viewbar .planet-ph-view')).toBeTruthy();
    expect(shell.querySelector('.planet-toolbar .planet-search-field')).toBeTruthy();
    expect(shell.querySelector('.planet-toolbar .planet-year')).toBeTruthy();
    // По умолчанию окно сцены занимает ровная подложка карты, а не шар; подпись загрузки на месте.
    expect(shell.querySelector('.planet-geography .planet-stage .planet-map-ph')).toBeTruthy();
    expect(shell.querySelector('.planet-orb')).toBeNull();
    expect(shell.querySelector('.planet-geography .planet-stage .planet-loading').textContent).toBe('r6.planet.loading');
    expect(shell.querySelector('.planet-geography .planet-key .planet-key-bar')).toBeTruthy();
    expect(shell.querySelector('.planet-info .planet-list-heading')).toBeTruthy();
    expect(shell.querySelectorAll('.planet-ph-row').length).toBeGreaterThanOrEqual(6);
  });

  it('тому, кто выбрал шар, показывает матовую сферу с сеткой меридианов (SVG), а не картинку', () => {
    window.localStorage.setItem('fe_planet_view', 'globe');
    const { container } = render(<PlanetPlaceholder />);
    expect(container.querySelector('.planet-stage .planet-orb svg ellipse')).toBeTruthy();
    expect(container.querySelector('.planet-map-ph')).toBeNull();
  });

  it('служебные каркасы спрятаны от скринридера; единственный текст — подпись загрузки', () => {
    const { container } = render(<PlanetPlaceholder />);
    for (const node of container.querySelectorAll('.planet-toolbar, .planet-key, .planet-info')) {
      expect(node.getAttribute('aria-hidden')).toBe('true');
    }
    expect(container.textContent).toBe('r6.planet.loading');
  });

  it('не использует растровую картинку для шара', () => {
    const { container } = render(<PlanetPlaceholder />);
    expect(container.querySelector('img')).toBeNull();
    expect(container.innerHTML).not.toMatch(/\.webp|\.png|\.jpg/);
  });
});
