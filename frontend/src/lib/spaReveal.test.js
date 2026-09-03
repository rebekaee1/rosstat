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
