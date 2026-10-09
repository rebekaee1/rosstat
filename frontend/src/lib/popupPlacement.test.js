import { describe, expect, it } from 'vitest';
import { placeMenu } from './popupPlacement';

const rect = (left, width, top = 100) => ({ left, right: left + width, top, bottom: top + 36 });

describe('placeMenu', () => {
  it('кнопка справа: меню выравнивается по правому краю кнопки', () => {
    const { left } = placeMenu(rect(700, 120), { viewportW: 1024, viewportH: 800 });
    expect(left).toBe(-(248 - 120));
  });

  it('кнопка у левого края: меню не уходит за левый край окна', () => {
    const r = rect(20, 100);
    const { left } = placeMenu(r, { viewportW: 800, viewportH: 800 });
    expect(r.left + left).toBeGreaterThanOrEqual(8);
  });

  it('узкое окно: меню целиком внутри', () => {
    const r = rect(150, 100);
    const { left } = placeMenu(r, { viewportW: 360, viewportH: 800 });
    expect(r.left + left).toBeGreaterThanOrEqual(8);
    expect(r.left + left + 248).toBeLessThanOrEqual(360 - 8);
  });

  it('внизу нет места, вверху есть: открывается вверх', () => {
    expect(placeMenu(rect(10, 100, 700), { viewportW: 800, viewportH: 760 }).up).toBe(true);
    expect(placeMenu(rect(10, 100, 100), { viewportW: 800, viewportH: 760 }).up).toBe(false);
  });
});
