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

  it('течёт плашками одним потоком без подписей групп и фильтрует поиском', () => {
    const onChange = vi.fn();
    renderPicker(
      <WorldConceptPicker
        concepts={CONCEPTS}
        value="unemployment-rate"
        onChange={onChange}
      />,
    );
    // Группы сняты: показатель ищут поиском, а не разбором рубрик.
    expect(screen.queryByText('Рынок труда')).toBeNull();
    expect(screen.getByRole('button', { name: 'Безработица' }).getAttribute('aria-pressed')).toBe('true');
    fireEvent.change(screen.getByRole('searchbox'), { target: { value: 'насел' } });
    expect(screen.getByRole('button', { name: 'Население' })).toBeTruthy();
    expect(screen.queryByRole('button', { name: 'Безработица' })).toBeNull();
  });

  it('ищет по синонимам показателя, а не только по подписи', () => {
    renderPicker(
      <WorldConceptPicker
        concepts={[
          { slug: 'budget-balance-gdp', name: 'Сальдо бюджета', keywords: ['дефицит бюджета', 'профицит'] },
          { slug: 'population', name: 'Население' },
        ]}
        value="population"
        onChange={vi.fn()}
      />,
    );
    fireEvent.change(screen.getByRole('searchbox'), { target: { value: 'дефицит' } });
    expect(screen.getByRole('button', { name: 'Баланс бюджета' })).toBeTruthy();
    expect(screen.queryByRole('button', { name: 'Население' })).toBeNull();
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

  it('без поиска (главная) поле скрыто и виден весь закрытый набор', () => {
    renderPicker(
      <WorldConceptPicker
        concepts={CONCEPTS}
        value="unemployment-rate"
        onChange={vi.fn()}
        searchable={false}
        hint={<span>подсказка</span>}
      />,
    );
    expect(screen.queryByRole('searchbox')).toBeNull();
    expect(screen.getByText('подсказка')).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Население' })).toBeTruthy();
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
    // «насел» матчится и в «Население», и в «Экономическая активность населения».
    expect(track).toHaveBeenCalledWith('search_query', {
      q: 'насел',
      results: 2,
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

  it('лента на телефоне: затухание не накрывает выбранную пилюлю, а у невыбранных остаётся', () => {
    const offsets = { left: 0 };
    const spies = [
      vi.spyOn(HTMLElement.prototype, 'offsetLeft', 'get').mockImplementation(function () {
        return this.getAttribute('aria-pressed') === 'true' ? offsets.left : 0;
      }),
      vi.spyOn(HTMLElement.prototype, 'offsetWidth', 'get').mockReturnValue(100),
      vi.spyOn(HTMLElement.prototype, 'clientWidth', 'get').mockReturnValue(360),
    ];
    try {
      offsets.left = 4;
      const { unmount } = renderPicker(
        <WorldConceptPicker concepts={CONCEPTS} value="unemployment-rate" onChange={vi.fn()} searchable={false} mobileScroll />,
      );
      const row = document.querySelector('.fe-chip-row--mscroll');
      // Выбранная пилюля у самого края: левое затухание выключено, правое остаётся.
      expect(row.style.getPropertyValue('--fe-mask-l')).toBe('0px');
      expect(row.style.getPropertyValue('--fe-mask-r')).toBe('28px');
      unmount();

      offsets.left = 120;
      renderPicker(
        <WorldConceptPicker concepts={CONCEPTS} value="unemployment-rate" onChange={vi.fn()} searchable={false} mobileScroll />,
      );
      const rowMid = document.querySelector('.fe-chip-row--mscroll');
      expect(rowMid.style.getPropertyValue('--fe-mask-l')).toBe('14px');
      expect(rowMid.style.getPropertyValue('--fe-mask-r')).toBe('28px');
    } finally {
      spies.forEach((spy) => spy.mockRestore());
    }
  });

  it('волна 6: пока список показателей грузится, вместо «Нет данных» стоят серые заготовки', () => {
    renderPicker(<WorldConceptPicker concepts={[]} value="" onChange={vi.fn()} searchable={false} loading />);
    expect(screen.getByTestId('concept-picker-skeleton')).toBeTruthy();
    expect(screen.queryByText('Нет данных')).toBeNull();
  });

  it('волна 6: когда загрузка закончилась и показателей правда нет, пишем «Нет данных»', () => {
    renderPicker(<WorldConceptPicker concepts={[]} value="" onChange={vi.fn()} searchable={false} />);
    expect(screen.queryByTestId('concept-picker-skeleton')).toBeNull();
    expect(screen.getByText('Нет данных')).toBeTruthy();
  });
});
