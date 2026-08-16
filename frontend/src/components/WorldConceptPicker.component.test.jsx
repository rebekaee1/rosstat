/** @vitest-environment jsdom */
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import { fireEvent, render, screen, act } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { LocaleProvider } from '../i18n';
import WorldConceptPicker from './WorldConceptPicker';

vi.mock('../lib/track', () => ({
  track: vi.fn(),
  events: { SEARCH_QUERY: 'search_query' },
}));

import { track } from '../lib/track';

function renderPicker(ui) {
  return render(
    <LocaleProvider>
      <MemoryRouter>{ui}</MemoryRouter>
    </LocaleProvider>,
  );
}

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
  beforeEach(() => {
    vi.useFakeTimers();
    track.mockClear();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('течёт плашками в одном потоке с подписями групп и фильтрует поиском', () => {
    const onChange = vi.fn();
    renderPicker(
      <WorldConceptPicker
        concepts={CONCEPTS}
        value="unemployment-rate"
        onChange={onChange}
      />,
    );
    expect(screen.getByText('Рынок труда')).toBeTruthy();
    expect(screen.getByText('Цены')).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Безработица' }).getAttribute('aria-pressed')).toBe('true');
    fireEvent.change(screen.getByRole('searchbox'), { target: { value: 'насел' } });
    expect(screen.getByRole('button', { name: 'Население' })).toBeTruthy();
    expect(screen.queryByRole('button', { name: 'Безработица' })).toBeNull();
  });

  it('при query ≥2 через debounce пишет search_query world-concept-picker', () => {
    renderPicker(
      <WorldConceptPicker
        concepts={CONCEPTS}
        value="unemployment-rate"
        onChange={vi.fn()}
      />,
    );
    fireEvent.change(screen.getByRole('searchbox'), { target: { value: 'насел' } });
    expect(track).not.toHaveBeenCalled();
    act(() => {
      vi.advanceTimersByTime(900);
    });
    expect(track).toHaveBeenCalledWith('search_query', {
      q: 'насел',
      results: 1,
      context: 'world-concept-picker',
    });
  });

  it('при большом каталоге сворачивается в выпадающий список', () => {
    renderPicker(
      <WorldConceptPicker
        concepts={MANY}
        value="unemployment-rate"
        onChange={vi.fn()}
      />,
    );
    const trigger = screen.getByRole('button', { name: /Безработица/ });
    expect(trigger.getAttribute('aria-expanded')).toBe('false');
    fireEvent.click(trigger);
    expect(trigger.getAttribute('aria-expanded')).toBe('true');
    expect(screen.getByRole('listbox')).toBeTruthy();
  });
});
