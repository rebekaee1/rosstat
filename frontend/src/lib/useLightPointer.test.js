// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { installLightPointer } from './useLightPointer';

function mockMatchMedia(fine) {
  window.matchMedia = vi.fn((q) => ({
    matches: q.includes('pointer: fine') ? fine : false,
    addEventListener: () => {},
    removeEventListener: () => {},
  }));
}

describe('useLightPointer: свет за курсором', () => {
  let box;
  let off;

  beforeEach(() => {
    vi.useFakeTimers();
    window.requestAnimationFrame = (cb) => setTimeout(() => cb(Date.now()), 0);
    window.cancelAnimationFrame = (id) => clearTimeout(id);
    box = document.createElement('div');
    box.className = 'fe-cursor-light';
    box.getBoundingClientRect = () => ({ left: 100, top: 50, right: 300, bottom: 150, width: 200, height: 100 });
    document.body.appendChild(box);
  });

  afterEach(() => {
    if (off) off();
    off = null;
    box.remove();
    vi.useRealTimers();
  });

  it('ставит --mx/--my внутри элемента и data-fe-lit, один слушатель на документ', () => {
    mockMatchMedia(true);
    const add = vi.spyOn(document, 'addEventListener');
    off = installLightPointer(window);
    const second = installLightPointer(window);
    expect(add.mock.calls.filter(([type]) => type === 'pointermove')).toHaveLength(1);

    box.dispatchEvent(new window.PointerEvent('pointermove', { bubbles: true, clientX: 160, clientY: 90 }));
    vi.advanceTimersByTime(5);
    expect(box.style.getPropertyValue('--mx')).toBe('60px');
    expect(box.style.getPropertyValue('--my')).toBe('40px');
    expect(box.hasAttribute('data-fe-lit')).toBe(true);

    // Курсор ушёл на другой элемент: свет гаснет.
    document.body.dispatchEvent(new window.PointerEvent('pointermove', { bubbles: true, clientX: 5, clientY: 5 }));
    vi.advanceTimersByTime(5);
    expect(box.hasAttribute('data-fe-lit')).toBe(false);
    second();
    add.mockRestore();
  });

  it('на тач-экране (pointer: coarse) свет за курсором не подключается', () => {
    mockMatchMedia(false);
    off = installLightPointer(window);
    box.dispatchEvent(new window.PointerEvent('pointermove', { bubbles: true, clientX: 160, clientY: 90 }));
    vi.advanceTimersByTime(5);
    expect(box.hasAttribute('data-fe-lit')).toBe(false);
  });
});

describe('useLightPointer: блик-проход при появлении', () => {
  it('элемент .fe-glint получает data-fe-glint=on, когда попадает в окно, и done после анимации', () => {
    mockMatchMedia(false);
    const observed = [];
    let callback;
    class FakeIO {
      constructor(cb) { callback = cb; }
      observe(el) { observed.push(el); }
      unobserve() {}
      disconnect() {}
    }
    const realIO = window.IntersectionObserver;
    window.IntersectionObserver = FakeIO;

    const el = document.createElement('div');
    el.className = 'fe-glint';
    document.body.appendChild(el);

    const stop = installLightPointer(window);
    expect(observed).toContain(el);
    callback([{ isIntersecting: true, target: el }]);
    expect(el.getAttribute('data-fe-glint')).toBe('on');

    const ev = new window.Event('animationend', { bubbles: true });
    Object.defineProperty(ev, 'animationName', { value: 'fe-glint-once' });
    el.dispatchEvent(ev);
    expect(el.getAttribute('data-fe-glint')).toBe('done');

    stop();
    el.remove();
    window.IntersectionObserver = realIO;
  });
});
