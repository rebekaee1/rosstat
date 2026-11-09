import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { R6RussiaLine, R6RatingExtras, R6StaleNote } from './R6Annual';

const t = (k, p = {}) => `${k}${Object.keys(p).length ? JSON.stringify(p) : ''}`;

describe('R6Annual', () => {
  it('Russia line shows same-year value and gap', () => {
    render(<R6RussiaLine value={70.94} year={2023} series={[{ year: 2023, value: 73.41 }]} unit="число лет" locale="ru" t={t} />);
    expect(screen.getByTestId('r6c-russia').textContent).toContain('r6c.gapLower');
  });
  it('Russia line hidden if no same year', () => {
    const { container } = render(<R6RussiaLine value={1} year={2024} series={[{ year: 2023, value: 2 }]} unit="%" locale="ru" t={t} />);
    expect(container.textContent).toBe('');
  });
  it('rating extras: neighbours and bottom with own row highlighted', () => {
    const rank = {
      position: 61, total: 85, year: 2023,
      around: [59, 60, 61, 62, 63].map((p) => ({ position: p, slug: `r${p}`, name: `Регион ${p}`, value: 70 })),
      bottom: [83, 84, 85].map((p) => ({ slug: `r${p}`, name: `Регион ${p}`, value: 66 })),
    };
    render(<MemoryRouter><R6RatingExtras rank={rank} slug="r61" code="x" unit="лет" locale="ru" russiaSeries={[{ year: 2023, value: 73 }]} t={t} /></MemoryRouter>);
    expect(screen.getByText('Регион 61').closest('a').getAttribute('aria-current')).toBe('true');
    expect(screen.getByText('Регион 85')).toBeTruthy();
  });
  it('stale note only when data is 2+ years old', () => {
    const now = new Date(2026, 5, 1);
    const { container, rerender } = render(<R6StaleNote lastYear={2023} t={t} now={now} />);
    expect(container.textContent).toContain('r6c.stale');
    rerender(<R6StaleNote lastYear={2025} t={t} now={now} />);
    expect(container.textContent).toBe('');
  });
});
