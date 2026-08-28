import { describe, expect, it } from 'vitest';
import {
  buildWorldColorModel,
  WORLD_DIVERGING_SCALE,
  WORLD_NO_DATA,
  WORLD_RELATIVE_SCALE,
} from './worldMapColors';

describe('buildWorldColorModel', () => {
  it('uses seven median-centred relative bands for one-directional values', () => {
    const model = buildWorldColorModel(new Map(
      Array.from({ length: 35 }, (_, index) => [`C${index}`, index + 1]),
    ));

    expect(model.kind).toBe('relative');
    expect(model.bins).toHaveLength(7);
    expect(model.colorFor(1)).toBe(WORLD_RELATIVE_SCALE[0]);
    expect(model.colorFor(35)).toBe(WORLD_RELATIVE_SCALE[6]);
    expect(model.median).toBe(18);
    expect(model.sampleSize).toBe(35);
    // Модуль отдаёт ключ словаря и процентиль: текст собирает компонент.
    expect(model.describe(1)).toEqual({ key: 'world.map.band.rel0', rank: 1 });
    expect(model.describe(18)).toEqual({ key: 'world.map.band.rel3', rank: 50 });
    expect(model.describe(35)).toEqual({ key: 'world.map.band.rel6', rank: 99 });
    expect(model.bins[0].labelKey).toBe('world.map.band.rel0');
  });

  it('centres on zero only when the caller asks for it', () => {
    const model = buildWorldColorModel(
      { deficit: -9, neutral: 0, surplus: 9 },
      { mode: 'diverging' },
    );

    expect(model.kind).toBe('diverging');
    expect(model.colorFor(-9)).toBe(WORLD_DIVERGING_SCALE[0]);
    expect(model.colorFor(0)).toBe(WORLD_DIVERGING_SCALE[3]);
    expect(model.colorFor(9)).toBe(WORLD_DIVERGING_SCALE[6]);
    expect(model.describe(-9)).toEqual({ key: 'world.map.band.zero0', rank: null });
    expect(model.describe(9)).toEqual({ key: 'world.map.band.zero6', rank: null });
  });

  it('keeps one palette and one anchoring regardless of the values in the slice', () => {
    // Год без дефляции и год с дефляцией на одном показателе должны выглядеть
    // одинаково: раньше второй срез переключал карту на другую гамму.
    const positiveYear = buildWorldColorModel({ a: 1.2, b: 2.4, c: 8.1 });
    const yearWithDeflation = buildWorldColorModel({ a: -1.8, b: 2.4, c: 8.1 });

    expect(positiveYear.kind).toBe('relative');
    expect(yearWithDeflation.kind).toBe('relative');
    expect(yearWithDeflation.scale).toEqual(positiveYear.scale);
    expect(WORLD_DIVERGING_SCALE).toEqual(WORLD_RELATIVE_SCALE);
  });

  it('can preserve deficit semantics when every observed value is negative', () => {
    const model = buildWorldColorModel(
      { a: -8, b: -3, c: -1 },
      { mode: 'diverging' },
    );
    expect(model.kind).toBe('diverging');
    expect(model.colorFor(-8)).toBe(WORLD_DIVERGING_SCALE[0]);
    expect(model.describe(-1)).toEqual({ key: 'world.map.band.zero2', rank: null });
  });

  it('keeps missing and non-numeric values neutral', () => {
    const model = buildWorldColorModel({ a: 1, b: 2 });
    expect(model.colorFor(null)).toBe(WORLD_NO_DATA);
    expect(model.colorFor('not-a-number')).toBe(WORLD_NO_DATA);
  });

  it('переворачивает шкалу при порядке по возрастанию (правка 16)', () => {
    const values = Object.fromEntries(
      Array.from({ length: 35 }, (_, index) => [`c${index}`, index + 1]),
    );
    const model = buildWorldColorModel(values, { direction: 'asc' });
    // Лидер нового порядка (минимум) получает насыщенный край палитры,
    // антилидер (максимум) — противоположный.
    expect(model.colorFor(1)).toBe(WORLD_RELATIVE_SCALE[WORLD_RELATIVE_SCALE.length - 1]);
    expect(model.colorFor(35)).toBe(WORLD_RELATIVE_SCALE[0]);
  });

  it('при порядке по убыванию лидер (максимум) — акцентный', () => {
    const values = Object.fromEntries(
      Array.from({ length: 35 }, (_, index) => [`c${index}`, index + 1]),
    );
    const model = buildWorldColorModel(values, { direction: 'desc' });
    expect(model.colorFor(35)).toBe(WORLD_RELATIVE_SCALE[WORLD_RELATIVE_SCALE.length - 1]);
    expect(model.colorFor(1)).toBe(WORLD_RELATIVE_SCALE[0]);
  });
});
