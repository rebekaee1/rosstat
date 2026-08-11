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
    expect(model.describe(1)).toBe('Нижние 15% стран · 1-й процентиль');
    expect(model.describe(18)).toBe('Около медианы · 50-й процентиль');
    expect(model.describe(35)).toBe('Верхние 15% стран · 99-й процентиль');
  });

  it('uses a zero-centred diverging scale for signed values', () => {
    const model = buildWorldColorModel({ deficit: -9, neutral: 0, surplus: 9 });

    expect(model.kind).toBe('diverging');
    expect(model.colorFor(-9)).toBe(WORLD_DIVERGING_SCALE[0]);
    expect(model.colorFor(0)).toBe(WORLD_DIVERGING_SCALE[3]);
    expect(model.colorFor(9)).toBe(WORLD_DIVERGING_SCALE[6]);
    expect(model.describe(-9)).toBe('Сильно ниже нуля');
    expect(model.describe(9)).toBe('Сильно выше нуля');
  });

  it('can preserve deficit semantics when every observed value is negative', () => {
    const model = buildWorldColorModel(
      { a: -8, b: -3, c: -1 },
      { mode: 'diverging' },
    );
    expect(model.kind).toBe('diverging');
    expect(model.colorFor(-8)).toBe(WORLD_DIVERGING_SCALE[0]);
    expect(model.describe(-1)).toBe('Ниже нуля · близко к нулю');
  });

  it('keeps missing and non-numeric values neutral', () => {
    const model = buildWorldColorModel({ a: 1, b: 2 });
    expect(model.colorFor(null)).toBe(WORLD_NO_DATA);
    expect(model.colorFor('not-a-number')).toBe(WORLD_NO_DATA);
  });
});
