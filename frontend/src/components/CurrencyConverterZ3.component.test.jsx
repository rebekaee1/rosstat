// Z3 (круг 08.11): конвертер с мелкими валютами: популярные кнопки, пресеты под сум, поиск по стране, номинал в строке.
import { describe, it, expect, afterEach, beforeEach, vi } from 'vitest';
import { fireEvent, screen } from '@testing-library/react';
import CurrencyDesk from './CurrencyDesk';
import { renderPage, mockApiGet } from '../test/renderPage';

beforeEach(() => {
  vi.useFakeTimers({ toFake: ['Date'] });
  vi.setSystemTime(new Date('2026-11-08T12:00:00Z'));
  mockApiGet([['/auth/me', { user: null }], [/^\/indicators\/[a-z-]+\/data/, { data: [] }]]);
});
afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
});

const INDICATORS = [
  { code: 'usd-rub', name: 'Курс доллара США', current_value: 80, unit: 'руб.', current_date: '2026-11-07', change: 0.4, is_active: true },
  { code: 'uzs-rub', name: 'Узбекский сум к рублю', current_value: 68.6, unit: 'руб. за 10 000', current_date: '2026-11-07', change: 0.3, is_active: true },
  { code: 'kzt-rub', name: 'Казахский тенге к рублю', current_value: 16.4, unit: 'руб. за 100', current_date: '2026-11-07', change: 0.1, is_active: true },
];

describe('CurrencyDesk: мелкие валюты', () => {
  it('кнопка «Сум» считает рубли в сумы: 10 000 ₽ и результат по-человечески', () => {
    renderPage(<CurrencyDesk indicators={INDICATORS} />);
    fireEvent.click(screen.getByRole('button', { name: /Сум/ }));
    const out = screen.getByTestId('converter-result').textContent;
    expect(out).toContain('1 457 726');
    expect(out).toContain('10 000 сумов = 68,60 ₽');
    expect(screen.getByRole('button', { name: /^10\s000$/ })).toBeTruthy();
  });

  it('в строке списка номинал стоит рядом с ценой', () => {
    const { container } = renderPage(<CurrencyDesk indicators={INDICATORS} />);
    const per = [...container.querySelectorAll('.z3-val__per')].map((n) => n.textContent);
    expect(per).toContain('за 10 000 сумов');
    expect(per).toContain('за 100 тенге');
  });

  it('поиск в списке находит сум по стране', () => {
    const { container } = renderPage(<CurrencyDesk indicators={INDICATORS} />);
    fireEvent.change(screen.getAllByPlaceholderText('Валюта, страна, город или код')[0], { target: { value: 'узбекистан' } });
    const titles = [...container.querySelectorAll('.fe-trow__title')].map((n) => n.textContent);
    expect(titles).toEqual(['Узбекский сум к рублю']);
  });
});
