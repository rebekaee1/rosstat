/**
 * @vitest-environment jsdom
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import {
  buildRegionsMapGif,
  downloadBlob,
  GIF_FRAME_MS,
  GIF_LOGICAL_W,
  GIF_LOGICAL_H,
  GIF_DPR,
} from './regionsMapGif';

describe('regionsMapGif', () => {
  beforeEach(() => {
    if (typeof Path2D === 'undefined') {
      globalThis.Path2D = class Path2D {
        constructor() { /* noop */ }
      };
    }
    HTMLCanvasElement.prototype.getContext = vi.fn(() => {
      const noop = () => {};
      const pxW = GIF_LOGICAL_W * GIF_DPR;
      const pxH = GIF_LOGICAL_H * GIF_DPR;
      return {
        fillRect: noop,
        clearRect: noop,
        fill: noop,
        stroke: noop,
        beginPath: noop,
        arc: noop,
        fillText: noop,
        strokeText: noop,
        strokeRect: noop,
        save: noop,
        restore: noop,
        translate: noop,
        scale: noop,
        setTransform: noop,
        measureText: () => ({ width: 40 }),
        getImageData: () => ({
          data: new Uint8ClampedArray(pxW * pxH * 4),
        }),
        fillStyle: '',
        strokeStyle: '',
        lineWidth: 0,
        lineJoin: '',
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

  it('рендерит в 2× DPR', () => {
    expect(GIF_DPR).toBe(2);
    expect(GIF_LOGICAL_W * GIF_DPR).toBeGreaterThanOrEqual(1440);
    expect(GIF_LOGICAL_H * GIF_DPR).toBeGreaterThanOrEqual(1000);
  });

  it('собирает настоящий GIF89a (image/gif) для двух лет', async () => {
    const BlobOrig = globalThis.Blob;
    let rawPart = null;
    globalThis.Blob = class extends BlobOrig {
      constructor(parts, opts) {
        rawPart = parts?.[0];
        super(parts, opts);
      }
    };
    try {
      const blob = await buildRegionsMapGif({
        years: [2020, 2021],
        values_by_year: {
          2020: { moskva: 10, 'sankt-peterburg': 20 },
          2021: { moskva: 15, 'sankt-peterburg': 25 },
        },
        indicator: { name: 'Тест', unit: 'чел.' },
      });
      expect(blob).toBeInstanceOf(BlobOrig);
      expect(blob.type).toBe('image/gif');
      expect(blob.size).toBeGreaterThan(0);
      const bytes = rawPart instanceof ArrayBuffer
        ? new Uint8Array(rawPart)
        : rawPart instanceof Uint8Array
          ? rawPart
          : null;
      expect(bytes).toBeTruthy();
      const header = String.fromCharCode(...bytes.slice(0, 6));
      expect(header).toBe('GIF89a');
    } finally {
      globalThis.Blob = BlobOrig;
    }
  });

  it('downloadBlob принудительно ставит .gif', () => {
    const click = vi.fn();
    const append = vi.spyOn(document.body, 'appendChild').mockImplementation((el) => {
      if (el?.click) el.click = click;
      return el;
    });
    const remove = vi.spyOn(document.body, 'removeChild').mockImplementation((el) => el);
    globalThis.URL.createObjectURL = vi.fn(() => 'blob:test');
    globalThis.URL.revokeObjectURL = vi.fn();

    downloadBlob(new Blob(['x'], { type: 'image/gif' }), 'regions-map_test');
    expect(click).toHaveBeenCalled();
    const a = append.mock.calls[0][0];
    expect(a.download).toBe('regions-map_test.gif');
    expect(a.type).toBe('image/gif');

    append.mockRestore();
    remove.mockRestore();
  });
});
