import { act, renderHook } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import { useScrollDirection } from './useScrollDirection';

/** Прокрутка в тесте: ставим scrollY, шлём событие и ждём кадр (слушатель считает по requestAnimationFrame). */
async function scrollTo(y) {
  Object.defineProperty(window, 'scrollY', { value: y, configurable: true });
  await act(async () => {
    window.dispatchEvent(new Event('scroll'));
    await new Promise((resolve) => { setTimeout(resolve, 40); });
  });
}

afterEach(() => {
  Object.defineProperty(window, 'scrollY', { value: 0, configurable: true });
});

describe('useScrollDirection', () => {
  it('наверху страницы: не прокручено, направление вверх, прокрутка стоит', () => {
    const { result } = renderHook(() => useScrollDirection());
    expect(result.current).toEqual({ scrolled: false, deep: false, dir: 'up', idle: true });
  });

  it('вниз: scrolled с 24 px, deep с 96 px, направление down, пока идёт прокрутка', async () => {
    const { result } = renderHook(() => useScrollDirection());
    await scrollTo(40);
    expect(result.current).toMatchObject({ scrolled: true, deep: false, dir: 'down', idle: false });
    await scrollTo(300);
    expect(result.current).toMatchObject({ scrolled: true, deep: true, dir: 'down' });
  });

  it('вверх: направление меняется на up, дрожь меньше 6 px направление не меняет', async () => {
    const { result } = renderHook(() => useScrollDirection());
    await scrollTo(400);
    expect(result.current.dir).toBe('down');
    await scrollTo(398);
    expect(result.current.dir).toBe('down');
    await scrollTo(350);
    expect(result.current.dir).toBe('up');
  });

  it('возврат на самый верх сбрасывает всё', async () => {
    const { result } = renderHook(() => useScrollDirection());
    await scrollTo(500);
    await scrollTo(0);
    expect(result.current).toMatchObject({ scrolled: false, deep: false, dir: 'up' });
  });

  it('после остановки (700 мс) прокрутка считается завершённой', async () => {
    const { result } = renderHook(() => useScrollDirection());
    await scrollTo(200);
    expect(result.current.idle).toBe(false);
    await act(async () => { await new Promise((resolve) => { setTimeout(resolve, 800); }); });
    expect(result.current.idle).toBe(true);
    expect(result.current.dir).toBe('down');
  });
});
