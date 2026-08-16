/** @vitest-environment jsdom */
import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import WorldConceptPicker from './WorldConceptPicker';

const CONCEPTS = [
  { slug: 'unemployment-rate', name: 'Уровень безработицы' },
  { slug: 'hicp-index', name: 'Цены' },
  { slug: 'activity-rate', name: 'Экономическая активность' },
  { slug: 'population', name: 'Население' },
  { slug: 'long-term-interest-rate', name: 'Ставки' },
  { slug: 'budget-balance-gdp', name: 'Баланс' },
  { slug: 'gdp-per-capita-eu', name: 'ВВП к ЕС' },
];

const MANY = [
  ...CONCEPTS,
  ...Array.from({ length: 10 }, (_, i) => ({
    slug: `extra-${i}`,
    name: `Доп ${i}`,
  })),
];

describe('WorldConceptPicker', () => {
  it('течёт плашками в одном потоке с подписями групп и фильтрует поиском', () => {
    const onChange = vi.fn();
    render(
      <MemoryRouter>
        <WorldConceptPicker
          concepts={CONCEPTS}
          value="unemployment-rate"
          onChange={onChange}
        />
      </MemoryRouter>,
    );
    expect(screen.getByText('Рынок труда')).toBeTruthy();
    expect(screen.getByText('Цены')).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Безработица' }).getAttribute('aria-pressed')).toBe('true');
    fireEvent.change(screen.getByRole('searchbox'), { target: { value: 'насел' } });
    expect(screen.getByRole('button', { name: 'Население' })).toBeTruthy();
    expect(screen.queryByRole('button', { name: 'Безработица' })).toBeNull();
  });

  it('при большом каталоге сворачивается в выпадающий список', () => {
    render(
      <MemoryRouter>
        <WorldConceptPicker
          concepts={MANY}
          value="unemployment-rate"
          onChange={vi.fn()}
        />
      </MemoryRouter>,
    );
    const trigger = screen.getByRole('button', { name: /Безработица/ });
    expect(trigger.getAttribute('aria-expanded')).toBe('false');
    fireEvent.click(trigger);
    expect(trigger.getAttribute('aria-expanded')).toBe('true');
    expect(screen.getByRole('listbox')).toBeTruthy();
  });
});
