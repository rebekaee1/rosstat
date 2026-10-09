// Круг 11, зона E: ипотека (досрочное погашение, таблица, две ставки, пределы), инфляция (деноминация, длинные суммы,
// адрес и своя валюта), поле суммы (курсор и выделение), график курса (период и вторая пара).
import { describe, it, expect, afterEach, beforeEach, vi } from 'vitest';
import { act, fireEvent, screen, waitFor, within } from '@testing-library/react';
import CalculatorPage from './CalculatorPage';
import MortgageCalculatorPage from './MortgageCalculatorPage';
import { renderPage, mockApiGet } from '../test/renderPage';
import CurrencyPairChart from '../components/CurrencyPairChart';
import CalcMoneyField from '../components/CalcMoneyField';
import { LocaleProvider } from '../i18n';
import { useState } from 'react';

vi.mock('gsap', () => ({
  default: { fromTo: () => ({ kill: () => {} }), to: () => ({ kill: () => {} }) },
}));
vi.mock('../lib/track', async (importOriginal) => {
  const actual = await importOriginal();
  return { ...actual, track: vi.fn() };
});
const downloadGrid = vi.fn(() => Promise.resolve('ok'));
vi.mock('../lib/calcExport', () => ({ downloadGrid: (...args) => downloadGrid(...args) }));

beforeEach(() => downloadGrid.mockClear());
afterEach(() => { vi.restoreAllMocks(); try { window.localStorage.clear(); } catch { /* нет хранилища */ } });

const monthly = (from, to, value) => {
  const out = [];
  for (let y = from; y <= to; y += 1) for (let m = 1; m <= 12; m += 1) out.push({ date: `${y}-${String(m).padStart(2, '0')}-01`, value });
  return out;
};

const MORTGAGE_ROUTES = [
  ['/auth/me', { user: null }],
  [/^\/indicators\/key-rate\/data/, { data: [{ date: '2026-09-01', value: 14 }] }],
  [/^\/indicators\/mortgage-rate\/data/, { data: [{ date: '2026-08-01', value: 12.5 }] }],
];

function mortgage(route = '/calculator/mortgage') {
  mockApiGet(MORTGAGE_ROUTES);
  return renderPage(<MortgageCalculatorPage />, { path: '/calculator/mortgage', route });
}

describe('CalcMoneyField: курсор и выделение (круг 11)', () => {
  function Harness() {
    const [value, setValue] = useState(8000000);
    return (
      <LocaleProvider>
        <CalcMoneyField id="amt" label="Сумма" value={value} onChange={setValue} prefix="₽" />
      </LocaleProvider>
    );
  }

  it('касание выделяет всё число, и новая цифра заменяет старое значение', () => {
    vi.useFakeTimers();
    try {
      renderPage(<Harness />);
      const input = screen.getByLabelText('Сумма');
      input.focus();
      act(() => { vi.runAllTimers(); });
      expect(input.selectionStart).toBe(0);
      expect(input.selectionEnd).toBe(input.value.length);
    } finally {
      vi.useRealTimers();
    }
  });

  it('при вводе курсор остаётся там же после расстановки пробелов, «12000000» не портится', () => {
    renderPage(<Harness />);
    const input = screen.getByLabelText('Сумма');
    input.focus();
    // Нативная запись значения и положение курсора, как при наборе на телефоне.
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(input, '12000000');
    input.setSelectionRange(3, 3);
    fireEvent.input(input);
    expect(input.value).toBe('12 000 000');
    expect(input.selectionStart).toBe(4);
  });
});

describe('Ипотека (круг 11)', () => {
  it('адрес задаёт расчёт: сумма, взнос, ставка и срок', () => {
    mortgage('/calculator/mortgage?price=6000000&down=10&rate=12&years=15');
    expect(screen.getByLabelText(/Стоимость недвижимости/).value).toBe('6 000 000');
    expect(screen.getByLabelText('Ввести число: Срок кредита').value).toBe('15');
  });

  it('предел суммы с подсказкой под полем; огромная сумма не ломает плитки и сокращается', () => {
    const { container } = mortgage();
    expect(screen.getByText(/Сумма до 10 000 000 000/)).toBeTruthy();
    fireEvent.change(screen.getByLabelText(/Стоимость недвижимости/), { target: { value: '9000000000' } });
    const values = [...container.querySelectorAll('.w5-tile__value')].map((n) => n.textContent);
    expect(values.every((text) => text.length <= 14)).toBe(true);
    expect(values.some((text) => /млрд/.test(text))).toBe(true);
    fireEvent.change(screen.getByLabelText(/Стоимость недвижимости/), { target: { value: '90000000000' } });
    expect(screen.getByRole('alert').textContent).toMatch(/максимум 10.000.000.000/);
  });

  it('место под ключевую ставку занято, пока она грузится', () => {
    const { container } = mortgage();
    expect(container.querySelector('.w5-keyrate--ghost')).toBeTruthy();
  });

  it('досрочное погашение: доплата сокращает срок и показывает экономию', () => {
    const { container } = mortgage('/calculator/mortgage?price=8000000&down=20&rate=12&years=20');
    expect(container.querySelector('[data-testid="early-result"]')).toBeNull();
    fireEvent.change(screen.getByLabelText(/Доплата каждый месяц/), { target: { value: '20000' } });
    const result = container.querySelector('[data-testid="early-result"]');
    expect(result).toBeTruthy();
    expect(result.textContent).toMatch(/Кредит закроется через/);
    expect(result.textContent).toMatch(/Меньше процентов/);
    expect(result.textContent).toMatch(/Раньше срока/);
    // Разовое погашение открывает выбор: срок или платёж.
    fireEvent.change(screen.getByLabelText(/Разовое погашение/), { target: { value: '1000000' } });
    expect(screen.getByRole('button', { name: 'Уменьшить платёж' })).toBeTruthy();
  });

  it('две ставки рядом: открывается, считает разницу, закрывается', async () => {
    const { container } = mortgage('/calculator/mortgage?price=8000000&down=20&rate=12&years=20');
    expect(container.querySelector('[data-testid="rate-compare-table"]')).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: /Сравнить с другой ставкой/ }));
    const table = container.querySelector('[data-testid="rate-compare-table"]');
    expect(table).toBeTruthy();
    expect(within(table).getAllByRole('row').length).toBe(4);
    expect(table.textContent).toMatch(/платёж/i);
    // Готовая ставка из чипа: ключевая ставка ЦБ 14 %.
    fireEvent.click(await screen.findByRole('button', { name: /Ключевая ставка 14,0%/ }));
    expect(table.textContent).toMatch(/14,0%/);
    fireEvent.click(screen.getByRole('button', { name: 'Убрать' }));
    expect(container.querySelector('[data-testid="rate-compare-table"]')).toBeNull();
  });

  it('таблица платежей по годам и по месяцам; скачать CSV идёт через выгрузку сетки', async () => {
    const { container } = mortgage('/calculator/mortgage?price=8000000&down=20&rate=12&years=20');
    const section = container.querySelector('[data-block="calc-schedule"]');
    expect(section.querySelectorAll('tbody tr').length).toBe(20);
    fireEvent.click(within(section).getByRole('button', { name: 'По месяцам' }));
    expect(section.querySelectorAll('tbody tr').length).toBe(24);
    fireEvent.click(within(section).getByRole('button', { name: /Показать ещё 24/ }));
    expect(section.querySelectorAll('tbody tr').length).toBe(48);
    fireEvent.click(screen.getByTestId('schedule-download'));
    await waitFor(() => expect(downloadGrid).toHaveBeenCalledTimes(1));
    const call = downloadGrid.mock.calls[0][0];
    expect(call.format).toBe('csv');
    expect(call.grid.rows).toHaveLength(240);
    expect(call.history.source).toBe('calc-mortgage');
  });
});

describe('Калькулятор инфляции (круг 11)', () => {
  beforeEach(() => { cpiValue = 101; });
  let cpiValue = 101;
  function inflation(route) {
    const CPI = { data: monthly(1991, 2026, cpiValue) };
    mockApiGet([
      ['/auth/me', { user: null }],
      ['/indicators/cpi/data', CPI],
      ['/indicators/cpi-food/data', CPI],
      ['/indicators/cpi-nonfood/data', CPI],
      ['/indicators/cpi-services/data', CPI],
      ['/world/compare/catalog', { items: [], total: 0 }],
    ]);
    return renderPage(<CalculatorPage />, { path: '/calculator', route });
  }

  it('1991 год: пояснение про деноминацию 1998 года с пересчётом в нынешние рубли', async () => {
    inflation('/calculator?amount=100000&from=1991&to=2026');
    const note = await screen.findByTestId('calc-denomination');
    expect(note.textContent).toMatch(/1 января 1998 года/);
    expect(note.textContent).toMatch(/1000 старых рублей/);
    expect(note.textContent).toMatch(/около \d/);
  });

  it('с 2000 года пояснения нет', async () => {
    inflation('/calculator?amount=100000&from=2000&to=2026');
    await waitFor(() => expect(document.querySelector('[data-block="calc-result"]')).toBeTruthy());
    expect(screen.queryByTestId('calc-denomination')).toBeNull();
  });

  it('длинное число не режется: рядом короткая запись, «Рост цен» с пробелами между разрядами', async () => {
    cpiValue = 103;
    inflation('/calculator?amount=100000&from=1991&to=2026');
    const compact = await screen.findByTestId('calc-hero-compact');
    expect(compact.textContent).toMatch(/^≈ [\d,\s\u00A0]+\s(млн|млрд|трлн)/);
    const total = document.querySelector('.fe-z8-hint__big').textContent;
    expect(total).toMatch(/\d\s\d{3}/);
  });
});

describe('График курса: период и вторая пара (круг 11)', () => {
  const day = 86_400_000;
  const rows = (n, start, f) => Array.from({ length: n }, (_, i) => ({
    date: new Date(Date.parse('2026-10-05T00:00:00Z') - (n - 1 - i) * day).toISOString().slice(0, 10),
    value: f(i, start),
  }));
  const EDGES = [
    { from: 'USD', to: 'RUB', rate: 80, code: 'usd-rub', date: '2026-10-05' },
    { from: 'EUR', to: 'RUB', rate: 90, code: 'eur-rub', date: '2026-10-05' },
  ];
  const PAIR = { code: 'usd-rub', base: 'USD', quote: 'RUB', invert: false };

  it('переключатель периода меняет заголовок и число запрошенных точек; «всё время» просит максимум', async () => {
    const spy = mockApiGet([['/auth/me', { user: null }], [/^\/indicators\/usd-rub\/data/, { data: rows(400, 80, (i, s) => s + i * 0.05) }]]);
    const { container } = renderPage(<CurrencyPairChart pair={PAIR} edges={EDGES} />);
    await waitFor(() => expect(container.querySelector('.fe-z8-chart__title')).toBeTruthy());
    expect(container.querySelector('.fe-z8-chart__title').textContent).toMatch(/^За год/);
    fireEvent.click(screen.getByRole('button', { name: 'Неделя' }));
    expect(container.querySelector('.fe-z8-chart__title').textContent).toMatch(/^За неделю/);
    fireEvent.click(screen.getByRole('button', { name: 'Всё время' }));
    await waitFor(() => expect(JSON.stringify(spy.mock.calls)).toContain('"limit":10000'));
  });

  it('вторая пара: обе линии в индексе, подпись объясняет «старт = 100»', async () => {
    mockApiGet([
      ['/auth/me', { user: null }],
      [/^\/indicators\/usd-rub\/data/, { data: rows(400, 80, (i, s) => s + i * 0.05) }],
      [/^\/indicators\/eur-rub\/data/, { data: rows(400, 90, (i, s) => s + i * 0.02) }],
    ]);
    const { container } = renderPage(<CurrencyPairChart pair={PAIR} edges={EDGES} />);
    await waitFor(() => expect(container.querySelector('.fe-z8-chart__title')).toBeTruthy());
    fireEvent.click(screen.getByRole('combobox', { name: /^Вторая пара/ }));
    fireEvent.click(screen.getByRole('option', { name: /Евро к рублю/ }));
    await waitFor(() => expect(container.querySelector('.fe-c11e-chartnote')).toBeTruthy());
    expect(container.querySelector('.fe-z8-chart__title').textContent).toMatch(/рост от начала периода/);
    expect(container.querySelector('.fe-c11e-chartnote').textContent).toMatch(/со 100/);
    expect(container.querySelectorAll('.w5-legend__item')).toHaveLength(2);
  });
});
