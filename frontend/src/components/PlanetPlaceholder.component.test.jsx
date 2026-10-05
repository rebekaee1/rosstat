import { describe, expect, it } from 'vitest';
import { render } from '@testing-library/react';
import PlanetPlaceholder from './PlanetPlaceholder';

describe('PlanetPlaceholder', () => {
  it('повторяет раскладку настоящей карточки: поиск и год, шар, легенда, рейтинг из бегущих строк', () => {
    const { container } = render(<PlanetPlaceholder />);
    expect(container.querySelector('[aria-busy="true"].planet-host')).toBeTruthy();
    const shell = container.querySelector('.planet-shell.has-key');
    expect(shell).toBeTruthy();
    // Те же блоки и классы, что у PlanetView: размеры совпадают, страница при подмене не прыгает.
    expect(shell.querySelector('.planet-toolbar .planet-search-field')).toBeTruthy();
    expect(shell.querySelector('.planet-toolbar .planet-year')).toBeTruthy();
    expect(shell.querySelector('.planet-geography .planet-stage .planet-orb')).toBeTruthy();
    expect(shell.querySelector('.planet-geography .planet-key .planet-key-bar')).toBeTruthy();
    expect(shell.querySelector('.planet-info .planet-list-heading')).toBeTruthy();
    expect(shell.querySelectorAll('.planet-ph-row').length).toBeGreaterThanOrEqual(6);
  });

  it('служебные каркасы спрятаны от скринридера и не содержат текста', () => {
    const { container } = render(<PlanetPlaceholder />);
    for (const node of container.querySelectorAll('.planet-toolbar, .planet-key, .planet-info')) {
      expect(node.getAttribute('aria-hidden')).toBe('true');
    }
    expect(container.textContent).toBe('');
  });
});
