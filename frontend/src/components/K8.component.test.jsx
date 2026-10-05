/** @vitest-environment jsdom */
// K8 (раунд 3): ползунок знает долю заполнения, результат липнет снизу, блик повторяется при пересчёте, вкладки знают активную.
import { createRef } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { LocaleProvider } from '../i18n';
import CalcSlider from './CalcSlider';
import CalcStickyResult from './CalcStickyResult';
import CalculatorShowcase from './CalculatorShowcase';
import { replayGlint } from '../lib/calcGlint';

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe('CalcSlider: жидкое золото в жёлобе', () => {
  it('передаёт долю заполнения в --k8-r', () => {
    render(
      <LocaleProvider locale="ru">
        <CalcSlider label="Ставка" value={15} min={0} max={30} onChange={() => {}} />
      </LocaleProvider>,
    );
    const input = screen.getByLabelText('Ставка');
    expect(input.style.getPropertyValue('--k8-r')).toBe('0.5');
    expect(input.className).toContain('calc-slider');
  });

  it('не выходит за 0 и 1 и не делит на ноль', () => {
    const { rerender } = render(
      <LocaleProvider locale="ru">
        <CalcSlider label="Срок" value={99} min={1} max={30} onChange={() => {}} />
      </LocaleProvider>,
    );
    expect(screen.getByLabelText('Срок').style.getPropertyValue('--k8-r')).toBe('1');
    rerender(
      <LocaleProvider locale="ru">
        <CalcSlider label="Срок" value={5} min={5} max={5} onChange={() => {}} />
      </LocaleProvider>,
    );
    expect(screen.getByLabelText('Срок').style.getPropertyValue('--k8-r')).toBe('0');
  });
});

describe('CalculatorShowcase: бегунок под активной вкладкой', () => {
  it('ставит --k8-i по номеру текущего калькулятора', () => {
    const { container } = render(
      <MemoryRouter>
        <LocaleProvider locale="ru">
          <CalculatorShowcase current="compound" />
        </LocaleProvider>
      </MemoryRouter>,
    );
    expect(container.querySelector('nav.fe-z8-tabs').style.getPropertyValue('--k8-i')).toBe('2');
  });
});

describe('CalcStickyResult: результат липнет снизу', () => {
  let observer;
  beforeEach(() => {
    observer = null;
    vi.stubGlobal('IntersectionObserver', class {
      constructor(callback) { this.callback = callback; observer = this; }
      observe() {}
      disconnect() {}
    });
  });

  function setup(props = {}) {
    const target = document.createElement('section');
    target.scrollIntoView = vi.fn();
    document.body.appendChild(target);
    const ref = { current: target };
    render(
      <LocaleProvider locale="ru">
        <CalcStickyResult targetRef={ref} value="57 991 ₽" active {...props} />
      </LocaleProvider>,
    );
    return { target };
  }

  it('показывается, когда блок результата вне окна, и прячется, когда он виден', () => {
    setup();
    expect(screen.queryByTestId('calc-sticky-result')).toBeNull();
    act(() => observer.callback([{ isIntersecting: false }]));
    const bar = screen.getByTestId('calc-sticky-result');
    expect(bar.textContent).toContain('57 991 ₽');
    expect(bar.textContent).toContain('Результат');
    expect(bar.parentElement).toBe(document.body);
    act(() => observer.callback([{ isIntersecting: true }]));
    expect(screen.queryByTestId('calc-sticky-result')).toBeNull();
  });

  it('по нажатию прокручивает к результату', () => {
    const { target } = setup({ label: 'Платёж' });
    act(() => observer.callback([{ isIntersecting: false }]));
    fireEvent.click(screen.getByTestId('calc-sticky-result'));
    expect(target.scrollIntoView).toHaveBeenCalledTimes(1);
  });

  it('молчит, пока результата нет', () => {
    setup({ active: false, value: '' });
    expect(observer).toBeNull();
    expect(screen.queryByTestId('calc-sticky-result')).toBeNull();
  });

  it('без IntersectionObserver ничего не рисует', () => {
    vi.stubGlobal('IntersectionObserver', undefined);
    const ref = createRef();
    ref.current = document.createElement('div');
    render(
      <LocaleProvider locale="ru">
        <CalcStickyResult targetRef={ref} value="1 ₽" active />
      </LocaleProvider>,
    );
    expect(screen.queryByTestId('calc-sticky-result')).toBeNull();
  });
});

describe('replayGlint: блик при пересчёте', () => {
  it('возвращает done в on и больше ничего не трогает', () => {
    const el = document.createElement('div');
    expect(replayGlint(el)).toBe(false);
    el.setAttribute('data-fe-glint', 'on');
    expect(replayGlint(el)).toBe(false);
    el.setAttribute('data-fe-glint', 'done');
    expect(replayGlint(el)).toBe(true);
    expect(el.getAttribute('data-fe-glint')).toBe('on');
    expect(replayGlint(null)).toBe(false);
  });
});
