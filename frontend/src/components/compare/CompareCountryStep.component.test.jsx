/** @vitest-environment jsdom */
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { LocaleProvider } from '../../i18n';
import CompareCountryStep from './CompareCountryStep';

afterEach(cleanup);

const SLUGS = [
  ['russia', 'Россия'], ['germany', 'Германия'], ['united-states', 'США'], ['china', 'Китай'],
  ['france', 'Франция'], ['united-kingdom', 'Великобритания'], ['italy', 'Италия'], ['japan', 'Япония'],
  ['india', 'Индия'], ['brazil', 'Бразилия'], ['turkey', 'Турция'], ['poland', 'Польша'],
  ['albania', 'Албания'], ['austria', 'Австрия'], ['finland', 'Финляндия'], ['canada', 'Канада'],
];
const COUNTRIES = SLUGS.map(([key, label]) => ({ key, label }));

function renderStep(props = {}) {
  const onSelect = vi.fn();
  const onQuery = vi.fn();
  const utils = render(
    <LocaleProvider locale="ru">
      <CompareCountryStep countries={COUNTRIES} query="" onQuery={onQuery} onSelect={onSelect} {...props} />
    </LocaleProvider>,
  );
  return { ...utils, onSelect, onQuery };
}

describe('CompareCountryStep', () => {
  it('сначала популярные страны с флагами, остальные — по кнопке «Показать все»', () => {
    const { container } = renderStep();
    expect(screen.getByRole('button', { name: 'Германия' })).toBeTruthy();
    expect(screen.queryByRole('button', { name: 'Албания' })).toBeNull();
    // Флаг — украшение: в имя кнопки не попадает.
    const flag = container.querySelector('.fe-flag');
    expect(flag.getAttribute('aria-hidden')).toBe('true');
    expect(flag.textContent).toMatch(/\p{Regional_Indicator}/u);
    fireEvent.click(screen.getByRole('button', { name: /Показать все страны \(16\)/ }));
    expect(screen.getByRole('button', { name: 'Албания' })).toBeTruthy();
  });

  it('список не вложенная прокрутка: ни одного контейнера overflow-auto', () => {
    const { container } = renderStep();
    expect(container.querySelector('.overflow-auto, .overflow-y-auto')).toBeNull();
  });

  it('подборка «G7» оставляет только страны семёрки', () => {
    renderStep();
    fireEvent.click(screen.getByRole('button', { name: 'G7' }));
    expect(screen.getByRole('button', { name: 'Германия' })).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Канада' })).toBeTruthy();
    expect(screen.queryByRole('button', { name: 'Китай' })).toBeNull();
    expect(screen.queryByRole('button', { name: 'Россия' })).toBeNull();
  });

  it('«БРИКС» и «Соседи России» — свои составы', () => {
    renderStep();
    fireEvent.click(screen.getByRole('button', { name: 'БРИКС' }));
    expect(screen.getByRole('button', { name: 'Бразилия' })).toBeTruthy();
    expect(screen.queryByRole('button', { name: 'Германия' })).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: 'Соседи России' }));
    expect(screen.getByRole('button', { name: 'Финляндия' })).toBeTruthy();
    expect(screen.queryByRole('button', { name: 'Бразилия' })).toBeNull();
  });

  it('выбор страны сообщает ключ', () => {
    const { onSelect } = renderStep();
    fireEvent.click(screen.getByRole('button', { name: 'Франция' }));
    expect(onSelect).toHaveBeenCalledWith('france');
  });

  it('при поиске подборки скрыты, а пустой результат — дружелюбное сообщение с кнопкой сброса', () => {
    const { onQuery } = renderStep({ countries: [], query: 'атлантида' });
    expect(screen.queryByRole('group', { name: 'Быстрые подборки стран' })).toBeNull();
    expect(screen.getByText(/Такой страны в каталоге нет/)).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: 'Сбросить поиск' }));
    expect(onQuery).toHaveBeenCalledWith('');
  });

  it('если страны нет, но есть подходящие показатели России — предлагает их', () => {
    const onAddIndicator = vi.fn();
    renderStep({
      countries: [], query: 'дизель',
      indicatorMatches: [{ code: 'diesel', label: 'Дизельное топливо' }],
      onAddIndicator,
    });
    fireEvent.click(screen.getByRole('button', { name: /Дизельное топливо/ }));
    expect(onAddIndicator).toHaveBeenCalledWith({ code: 'diesel', label: 'Дизельное топливо' });
  });
});
