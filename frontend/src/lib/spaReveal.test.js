/** @vitest-environment jsdom */
import { afterEach, describe, expect, it, vi } from 'vitest';
import { revealSpaNow, scheduleSpaReveal } from './spaReveal';

afterEach(() => {
  document.documentElement.classList.remove('fe-js');
  delete window.__feRevealSpa;
  vi.unstubAllGlobals();
});

describe('spaReveal', () => {
  it('вызывает __feRevealSpa, если SSR объявил его', () => {
    const spy = vi.fn(() => document.documentElement.classList.add('fe-js'));
    window.__feRevealSpa = spy;
    revealSpaNow();
    expect(spy).toHaveBeenCalledTimes(1);
    expect(document.documentElement.classList.contains('fe-js')).toBe(true);
  });

  it('ставит fe-js сама, если inline-скрипта нет (Vite shell)', () => {
    revealSpaNow();
    expect(document.documentElement.classList.contains('fe-js')).toBe(true);
  });

  it('держит заставку, пока полный CSS не загрузился, и снимает её по загрузке', () => {
    document.head.innerHTML = '<link data-fe-css media="print">';
    const spy = vi.fn();
    window.__feRevealSpa = spy;
    vi.stubGlobal('requestAnimationFrame', (cb) => { cb(); return 1; });
    scheduleSpaReveal();
    expect(spy).not.toHaveBeenCalled();
    document.querySelector('link[data-fe-css]').dispatchEvent(new Event('load'));
    expect(spy).toHaveBeenCalledTimes(1);
    document.head.innerHTML = '';
  });

  it('снимает заставку по ошибке стилей и не позже предела ожидания', () => {
    vi.useFakeTimers();
    document.head.innerHTML = '<link data-fe-css media="print">';
    const spy = vi.fn();
    window.__feRevealSpa = spy;
    vi.stubGlobal('requestAnimationFrame', (cb) => { cb(); return 1; });
    scheduleSpaReveal();
    expect(spy).not.toHaveBeenCalled();
    vi.advanceTimersByTime(10000);
    expect(spy).toHaveBeenCalledTimes(1);
    vi.advanceTimersByTime(20000);
    expect(spy).toHaveBeenCalledTimes(1);
    vi.useRealTimers();
    document.head.innerHTML = '';
  });

  it('откладывает клип на requestAnimationFrame', () => {
    const spy = vi.fn();
    window.__feRevealSpa = spy;
    vi.stubGlobal('requestAnimationFrame', (cb) => {
      cb();
      return 1;
    });
    const id = scheduleSpaReveal();
    expect(id).toBe(1);
    expect(spy).toHaveBeenCalledTimes(1);
  });
});
