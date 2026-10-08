// @vitest-environment jsdom
// Волна 2, W5: мелкие общие блоки калькуляторов, подсказка про касание, оглавление, поле пароля.
import { describe, it, expect, afterEach, vi } from 'vitest';
import { act, fireEvent, render, renderHook, screen } from '@testing-library/react';
import { useRef } from 'react';
import { CalcStatGrid, CalcStatTile } from './CalcStatTile';
import CalcMethod from './CalcMethod';
import ChartTouchHint, { ChartLegend } from './ChartTouchHint';
import LegalToc from './LegalToc';
import PasswordField from './PasswordField';
import { useChartTouchHint } from '../lib/useChartTouchHint';
import { LocaleProvider } from '../i18n';
import { embedChangeColor, THEME_COLORS } from '../embed/useEmbedParams';

afterEach(() => {
  vi.restoreAllMocks();
  window.localStorage.clear();
});

const wrap = (ui) => render(<LocaleProvider>{ui}</LocaleProvider>);

describe('CalcStatTile', () => {
  it('рисует плитки с подписью и значением в одной сетке', () => {
    const { container } = wrap(
      <CalcStatGrid>
        <CalcStatTile label="Сумма кредита" value="6 400 000 ₽" />
        <CalcStatTile label="Переплата" value="5 717 984 ₽" accent />
        <CalcStatTile label="Всего выплат" value="12 117 984 ₽" />
      </CalcStatGrid>,
    );
    expect(container.querySelectorAll('.w5-tile')).toHaveLength(3);
    expect(container.querySelector('.w5-tiles')).toBeTruthy();
    expect(container.querySelector('.w5-tile--accent .w5-tile__value').textContent).toBe('5 717 984 ₽');
  });
});

describe('CalcMethod', () => {
  it('прячет объяснение в раскрывающийся блок «Как считаем», формул нет', () => {
    const { container } = wrap(<CalcMethod paragraphs={['Берём индекс цен.', 'Перемножаем.']} />);
    const details = container.querySelector('details.w5-method');
    expect(details).toBeTruthy();
    expect(details.hasAttribute('open')).toBe(false);
    expect(screen.getByText('Как считаем')).toBeTruthy();
    expect(details.textContent).not.toMatch(/∏|Π|CPI_i/);
  });
});

describe('подсказка про касание графика', () => {
  it('показывается один раз на сенсорном экране и запоминается', () => {
    vi.spyOn(window, 'matchMedia').mockImplementation((query) => ({
      matches: query.includes('pointer: coarse'),
      media: query,
      addEventListener() {},
      removeEventListener() {},
      addListener() {},
      removeListener() {},
    }));
    const { result } = renderHook(() => useChartTouchHint());
    expect(result.current.visible).toBe(true);
    act(() => result.current.dismiss());
    expect(result.current.visible).toBe(false);
    expect(window.localStorage.getItem('fe-chart-touch-hint')).toBe('1');
    const second = renderHook(() => useChartTouchHint());
    expect(second.result.current.visible).toBe(false);
  });

  it('на компьютере (мышь) подсказки нет', () => {
    const { result } = renderHook(() => useChartTouchHint());
    expect(result.current.visible).toBe(false);
  });

  it('текст подсказки и легенда рисуются', () => {
    wrap(
      <>
        <ChartTouchHint visible />
        <ChartLegend items={[{ color: '#000', label: 'Капитал' }, { color: '#111', label: 'Вложения', dashed: true }]} />
      </>,
    );
    expect(screen.getByRole('note').textContent).toContain('Коснитесь графика');
    expect(screen.getByText('Капитал')).toBeTruthy();
    expect(screen.getByText('Вложения')).toBeTruthy();
  });
});

describe('LegalToc', () => {
  it('собирает якоря по заголовкам второго уровня и проставляет им id', async () => {
    function Page() {
      const ref = useRef(null);
      return (
        <>
          <LegalToc articleRef={ref} />
          <article ref={ref}>
            <h2>1. Общие положения</h2>
            <h2>2. Данные</h2>
            <h2>3. Права</h2>
          </article>
        </>
      );
    }
    const { container } = wrap(<Page />);
    const link = await screen.findByRole('link', { name: '2. Данные' }, { timeout: 2000 });
    expect(link.getAttribute('href')).toBe('#legal-2');
    expect(container.querySelector('#legal-2').textContent).toBe('2. Данные');
  });
});

describe('PasswordField', () => {
  it('кнопка показывает и скрывает пароль', () => {
    wrap(<PasswordField label="Пароль" value="secret" onChange={() => {}} autoComplete="current-password" />);
    const input = screen.getByLabelText('Пароль');
    expect(input.getAttribute('type')).toBe('password');
    fireEvent.click(screen.getByRole('button', { name: 'Показать пароль' }));
    expect(input.getAttribute('type')).toBe('text');
    expect(screen.getByRole('button', { name: 'Скрыть пароль' }).getAttribute('aria-pressed')).toBe('true');
  });
});

describe('embedChangeColor', () => {
  it('рост инфляции или безработицы не зелёный, неизвестный смысл нейтрален, у котировок цвет по знаку', () => {
    const colors = THEME_COLORS.light;
    expect(embedChangeColor(0.5, 'light', colors, 'Инфляция')).toBe('#b91c1c');
    expect(embedChangeColor(-0.5, 'light', colors, 'Уровень безработицы')).toBe('#15803d');
    expect(embedChangeColor(1.2, 'light', colors, 'ВВП')).toBe('#15803d');
    expect(embedChangeColor(1.2, 'light', colors, 'Золото')).toBe('#15803d');
    expect(embedChangeColor(-2.8, 'light', colors, 'Биткоин (BTC/USD)')).toBe('#b91c1c');
    expect(embedChangeColor(1.2, 'light', colors, 'Население')).toBe('#15803d');
    expect(embedChangeColor(1.2, 'light', colors, 'Число отделений')).toBe(colors.textSecondary);
    expect(embedChangeColor(0, 'light', colors, 'ВВП')).toBe(colors.textSecondary);
  });
});
