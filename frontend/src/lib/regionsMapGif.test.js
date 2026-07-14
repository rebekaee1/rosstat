/**
 * @vitest-environment jsdom
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';

// gifenc тянет typed arrays — мокаем минимально через реальный модуль,
// но Path2D/canvas в jsdom ограничены: проверяем гейт «мало лет» и контракт API.
import { buildRegionsMapGif, GIF_FRAME_MS } from './regionsMapGif';

describe('regionsMapGif', () => {
  beforeEach(() => {
    // jsdom не умеет Path2D — подставляем заглушку для smoke.
    if (typeof Path2D === 'undefined') {
      globalThis.Path2D = class Path2D {
        constructor() { /* noop */ }
      };
    }
    HTMLCanvasElement.prototype.getContext = vi.fn(() => {
      const noop = () => {};
      return {
        fillRect: noop,
        fill: noop,
        stroke: noop,
        beginPath: noop,
        arc: noop,
        fillText: noop,
        save: noop,
        restore: noop,
        translate: noop,
        scale: noop,
        getImageData: () => ({
          data: new Uint8ClampedArray(720 * 420 * 4),
        }),
        fillStyle: '',
        strokeStyle: '',
        lineWidth: 0,
        font: '',
        textAlign: '',
        textBaseline: '',
      };
    });
  });

  it('отклоняет серию короче двух лет', async () => {
    await expect(buildRegionsMapGif({ years: [2020], values_by_year: {} }))
      .rejects.toThrow('need_at_least_two_years');
  });

  it('темп кадра по умолчанию в диапазоне 400–800 мс', () => {
    expect(GIF_FRAME_MS).toBeGreaterThanOrEqual(400);
    expect(GIF_FRAME_MS).toBeLessThanOrEqual(800);
  });

  it('собирает Blob image/gif для двух лет', async () => {
    const blob = await buildRegionsMapGif({
      years: [2020, 2021],
      values_by_year: {
        2020: { moskva: 10, 'sankt-peterburg': 20 },
        2021: { moskva: 15, 'sankt-peterburg': 25 },
      },
      indicator: { name: 'Тест' },
    });
    expect(blob).toBeInstanceOf(Blob);
    expect(blob.type).toBe('image/gif');
    expect(blob.size).toBeGreaterThan(0);
  });
});
