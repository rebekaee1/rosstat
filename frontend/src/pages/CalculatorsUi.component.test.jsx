// Ипотечный калькулятор и сложные проценты: появление блоков через CSS (.fe-reveal), поля суммы
// с десятичной клавиатурой и видимым сообщением об ошибке, значения ползунков с единицами.
import { describe, it, expect, afterEach, vi } from 'vitest';
import { fireEvent, screen } from '@testing-library/react';
import MortgageCalculatorPage from './MortgageCalculatorPage';
import CompoundCalculatorPage from './CompoundCalculatorPage';
import { renderPage, mockApiGet } from '../test/renderPage';

vi.mock('../lib/track', async (importOriginal) => {
  const actual = await importOriginal();
  return { ...actual, track: vi.fn() };
});

afterEach(() => vi.restoreAllMocks());

const ROUTES = [
  ['/auth/me', { user: null }],
  [/^\/indicators\/key-rate\/data/, { data: [{ date: '2026-09-01', value: 14 }] }],
];

describe('Ипотечный калькулятор', () => {
  it('блоки появляются средствами CSS, а не gsap-твином', () => {
    mockApiGet(ROUTES);
    const { container } = renderPage(<MortgageCalculatorPage />, { path: '/calculator/mortgage', route: '/calculator/mortgage' });
    expect(container.querySelector('[data-animate]')).toBeNull();
    const revealed = container.querySelectorAll('.fe-reveal');
    expect(revealed.length).toBeGreaterThan(4);
    revealed.forEach((el) => {
      expect(parseFloat(el.style.getPropertyValue('--fe-delay'))).toBeLessThanOrEqual(0.2);
    });
  });

  it('поле цены: decimal-клавиатура; неверный ввод — сообщение, расчёт остаётся по прошлому значению', () => {
    mockApiGet(ROUTES);
    const { container } = renderPage(<MortgageCalculatorPage />, { path: '/calculator/mortgage', route: '/calculator/mortgage' });
    const price = screen.getByLabelText(/Стоимость недвижимости/);
    expect(price.getAttribute('inputmode')).toBe('decimal');
    const resultBefore = container.querySelector('[aria-live="polite"]').textContent;
    expect(resultBefore).toMatch(/98\s772/);

    fireEvent.change(price, { target: { value: 'много' } });
    expect(screen.getByRole('alert').textContent).toMatch(/только цифры/);
    expect(container.querySelector('[aria-live="polite"]').textContent).toBe(resultBefore);
  });

  it('значения ползунков читаются с единицами: «20 лет», «18%»', () => {
    mockApiGet(ROUTES);
    renderPage(<MortgageCalculatorPage />, { path: '/calculator/mortgage', route: '/calculator/mortgage' });
    expect(screen.getByText('20 лет')).toBeTruthy();
    expect(screen.getByText('18%')).toBeTruthy();
    expect(screen.getByLabelText('Срок кредита').getAttribute('aria-valuetext')).toBe('20 лет');
  });

  it('раунд 2: форма слева, итог справа, подсказка о переплате; по-русски пояснения про Россию нет', () => {
    mockApiGet(ROUTES);
    const { container } = renderPage(<MortgageCalculatorPage />, { path: '/calculator/mortgage', route: '/calculator/mortgage' });
    expect(container.querySelector('.fe-z8-calc__side .fe-z8-card')).toBeTruthy();
    expect(container.querySelector('.fe-z8-calc__out .fe-z8-result')).toBeTruthy();
    const hint = container.querySelector('[data-block="calc-hint"]');
    expect(hint.textContent).toMatch(/Переплата за 20 лет/);
    expect(hint.textContent).toMatch(/Это .* от суммы кредита/);
    expect(container.querySelector('[data-testid="mortgage-en-note"]')).toBeNull();
  });

  it('раунд 2: английская версия объясняет, что калькулятор для рублёвой ипотеки в России', () => {
    mockApiGet(ROUTES);
    const { container } = renderPage(<MortgageCalculatorPage />, { path: '/calculator/mortgage', route: '/calculator/mortgage', locale: 'en' });
    const note = container.querySelector('[data-testid="mortgage-en-note"]');
    expect(note.textContent).toMatch(/mortgages in Russia/);
    expect(note.textContent).toMatch(/Russian rubles/);
    expect(note.textContent).toMatch(/"m" means million/);
  });

  it('результат читается экранным дикторам один раз (анимируемая копия скрыта)', () => {
    mockApiGet(ROUTES);
    const { container } = renderPage(<MortgageCalculatorPage />, { path: '/calculator/mortgage', route: '/calculator/mortgage' });
    const live = container.querySelector('[aria-live="polite"]');
    expect(live.querySelector('[aria-hidden="true"] .calc-result-number, .calc-result-number[aria-hidden="true"]')).toBeTruthy();
    expect(live.querySelector('.sr-only').textContent).toMatch(/98\s772/);
  });
});

describe('Сложные проценты', () => {
  it('стартовая сумма и пополнение допускают ноль; срок показывает единицу', () => {
    mockApiGet(ROUTES);
    renderPage(<CompoundCalculatorPage />, { path: '/calculator/compound', route: '/calculator/compound' });
    const monthly = screen.getByLabelText(/Пополнение каждый месяц/);
    expect(monthly.getAttribute('inputmode')).toBe('decimal');
    fireEvent.change(monthly, { target: { value: '0' } });
    expect(screen.queryByRole('alert')).toBeNull();
    expect(screen.getByText('10 лет')).toBeTruthy();
  });

  it('раунд 2: подсказка «Капитал вырастет за N лет» с кратностью роста', () => {
    mockApiGet(ROUTES);
    const { container } = renderPage(<CompoundCalculatorPage />, { path: '/calculator/compound', route: '/calculator/compound' });
    const hint = container.querySelector('[data-block="calc-hint"]');
    expect(hint.textContent).toMatch(/Капитал вырастет за 10 лет/);
    expect(hint.querySelector('.fe-z8-hint__big').textContent).toMatch(/^×\d/);
    expect(container.querySelector('.fe-z8-calc__side [data-block="calc-hint"]')).toBeTruthy();
  });

  it('на английском единицы и сообщения тоже переведены', () => {
    mockApiGet(ROUTES);
    renderPage(<CompoundCalculatorPage />, { path: '/calculator/compound', route: '/calculator/compound', locale: 'en' });
    expect(screen.getByText('10 years')).toBeTruthy();
    fireEvent.change(screen.getByLabelText(/Initial amount/), { target: { value: 'lots' } });
    expect(screen.getByRole('alert').textContent).toMatch(/digits only/);
  });
});
