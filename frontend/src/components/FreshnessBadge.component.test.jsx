import { describe, it, expect } from 'vitest';
import { screen } from '@testing-library/react';
import { renderPage } from '../test/renderPage';
import FreshnessBadge from './FreshnessBadge';

const NOW = Date.UTC(2026, 9, 9);

describe('FreshnessBadge (круг 11, F)', () => {
  it('свежий месячный ряд: «Данные до августа 2026», знак заполненный', () => {
    renderPage(<FreshnessBadge lastDate="2026-08-01" frequency="monthly" now={NOW} />);
    const badge = screen.getByTestId('data-freshness');
    expect(badge.getAttribute('data-level')).toBe('fresh');
    expect(badge.textContent.replace(/\u00a0/g, ' ')).toBe('Данные до августа 2026');
    expect(badge.getAttribute('title')).toBeTruthy();
  });

  it('устаревший ряд называет это словом', () => {
    renderPage(<FreshnessBadge lastDate="2025-03-01" frequency="monthly" now={NOW} />);
    const badge = screen.getByTestId('data-freshness');
    expect(badge.getAttribute('data-level')).toBe('stale');
    expect(badge.textContent.replace(/\u00a0/g, ' ')).toBe('Устарело: данные до марта 2025');
  });

  it('годовой ряд называет год; без даты значка нет', () => {
    const { unmount } = renderPage(<FreshnessBadge lastDate="2025-01-01" frequency="annual" now={NOW} />);
    expect(screen.getByTestId('data-freshness').textContent).toContain('2025');
    unmount();
    renderPage(<FreshnessBadge lastDate="" frequency="annual" now={NOW} />);
    expect(screen.queryByTestId('data-freshness')).toBeNull();
  });
});
