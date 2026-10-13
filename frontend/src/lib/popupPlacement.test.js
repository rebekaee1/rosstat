import { describe, expect, it } from 'vitest';
import { placeMenu } from './popupPlacement';

const rect = (left, width, top = 100) => ({ left, right: left + width, top, bottom: top + 36 });

describe('placeMenu', () => {
  it('места хватает: меню начинается у левого края кнопки, не уезжает в сторону', () => {
    expect(placeMenu(rect(700, 120), { viewportW: 1024, viewportH: 800 }).left).toBe(0);
    // «Скачать данные» под графиком сравнения: кнопка у левого края страницы, меню под ней (раньше сдвигалось на -72 px).
    expect(placeMenu(rect(80, 160), { viewportW: 1920, viewportH: 900 }).left).toBe(0);
  });

  it('кнопка у правого края: меню выравнивается по правому краю кнопки', () => {
    const r = rect(900, 100);
    const { left } = placeMenu(r, { viewportW: 1024, viewportH: 800 });
    expect(r.left + left + 248).toBeLessThanOrEqual(1024 - 8);
    expect(r.right).toBeGreaterThanOrEqual(r.left + left + 100);
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
