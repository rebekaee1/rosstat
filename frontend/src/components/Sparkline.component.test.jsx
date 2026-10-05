/** @vitest-environment jsdom */
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render } from '@testing-library/react';
import Sparkline from './Sparkline';

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe('Sparkline', () => {
  it('следит за появлением обёртки, а не svg, который рисуется позже замера ширины', () => {
    const observe = vi.fn();
    vi.stubGlobal('IntersectionObserver', class {
      observe(el) { observe(el); }
      disconnect() {}
    });
    vi.stubGlobal('matchMedia', () => ({ matches: false, addEventListener() {}, removeEventListener() {} }));
    const { container } = render(<Sparkline points={[1, 2, 3, 2]} trend="up" />);
    expect(observe).toHaveBeenCalledTimes(1);
    expect(observe.mock.calls[0][0]).toBe(container.querySelector('.sparkline-container'));
  });

  it('с одной точкой ничего не рисует и ничего не наблюдает', () => {
    const observe = vi.fn();
    vi.stubGlobal('IntersectionObserver', class {
      observe(el) { observe(el); }
      disconnect() {}
    });
    vi.stubGlobal('matchMedia', () => ({ matches: false, addEventListener() {}, removeEventListener() {} }));
    const { container } = render(<Sparkline points={[1]} />);
    expect(container.firstChild).toBeNull();
    expect(observe).not.toHaveBeenCalled();
  });
});
