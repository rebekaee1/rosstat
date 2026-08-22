/** @vitest-environment jsdom */
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { LocaleProvider } from '../i18n';
import WorldConceptPicker from './WorldConceptPicker';

vi.mock('../lib/track', () => ({
  track: vi.fn(),
  events: { SEARCH_QUERY: 'search_query' },
}));

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

describe('WorldConceptPicker', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('течёт плашками одним потоком без подписей групп и без поиска', () => {
    const onChange = vi.fn();
    renderPicker(
      <WorldConceptPicker
        concepts={CONCEPTS}
        value="unemployment-rate"
        onChange={onChange}
      />,
    );
    // Группы и поиск сняты: показатель выбирают плашками.
    expect(screen.queryByText('Рынок труда')).toBeNull();
    expect(screen.queryByRole('searchbox')).toBeNull();
    expect(screen.getByRole('button', { name: 'Безработица' }).getAttribute('aria-pressed')).toBe('true');
    expect(screen.getByRole('button', { name: 'Население' })).toBeTruthy();
  });

  it('переключает значение по клику на плашку', () => {
    const onChange = vi.fn();
    renderPicker(
      <WorldConceptPicker
        concepts={CONCEPTS}
        value="unemployment-rate"
        onChange={onChange}
      />,
    );
    fireEvent.click(screen.getByRole('button', { name: 'Население' }));
    expect(onChange).toHaveBeenCalledWith('population');
  });

  it('в режиме ссылок рендерит Link с aria-current у активного', () => {
    renderPicker(
      <WorldConceptPicker
        concepts={CONCEPTS}
        value="unemployment-rate"
        mode="link"
        linkForSlug={(slug) => `/world/rating/${slug}`}
      />,
    );
    const active = screen.getByRole('link', { name: 'Безработица' });
    expect(active.getAttribute('aria-current')).toBe('page');
    expect(active.getAttribute('href')).toBe('/world/rating/unemployment-rate');
  });

  it('без поиска поле скрыто, виден весь набор и подсказка', () => {
    renderPicker(
      <WorldConceptPicker
        concepts={CONCEPTS}
        value="unemployment-rate"
        onChange={vi.fn()}
        hint={<span>подсказка</span>}
      />,
    );
    expect(screen.queryByRole('searchbox')).toBeNull();
    expect(screen.getByText('подсказка')).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Население' })).toBeTruthy();
  });
});
