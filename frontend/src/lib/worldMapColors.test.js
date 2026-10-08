import { describe, expect, it } from 'vitest';
import {
  buildWorldColorModel,
  WORLD_DIVERGING_SCALE,
  WORLD_NO_DATA,
  WORLD_OCEAN_COLOR,
  WORLD_RELATIVE_SCALE,
  WORLD_SELECT_FILL,
  WORLD_SELECT_HALO,
  WORLD_SELECT_INK,
} from './worldMapColors';

describe('круг 10: двойной холодный градиент', () => {
  it('идёт от светлой морской волны #B4E0DC через средний синий к глубокому индиго #26327E в семь ступеней, без тёплых тонов', () => {
    expect(WORLD_RELATIVE_SCALE).toHaveLength(7);
    expect(WORLD_RELATIVE_SCALE[0]).toBe('#B4E0DC');
    expect(WORLD_RELATIVE_SCALE[3]).toBe('#5B93C7');
    expect(WORLD_RELATIVE_SCALE[6]).toBe('#26327E');
    for (const hex of WORLD_RELATIVE_SCALE) {
      const [r, , b] = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16));
      expect(b).toBeGreaterThan(r); // каждая ступень синее, чем красная: ничего жёлтого и золотого
    }
  });

  it('градиент двухцветный: у светлого края зелёного больше, чем у тёмного (бирюзовый → индиго), а светлота падает без скачков', () => {
    const lum = (hex) => {
      const [r, g, b] = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255)
        .map((v) => (v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4));
      return 0.2126 * r + 0.7152 * g + 0.0722 * b;
    };
    const greens = WORLD_RELATIVE_SCALE.map((hex) => parseInt(hex.slice(3, 5), 16));
    expect(greens[0] - greens[6]).toBeGreaterThan(100);
    const lums = WORLD_RELATIVE_SCALE.map(lum);
    for (let i = 1; i < lums.length; i += 1) expect(lums[i]).toBeLessThan(lums[i - 1]);
  });

  it('держит океан #DCE8F3 и нейтральную сушу без данных #E6E3DC отдельно от шкалы', () => {
    expect(WORLD_OCEAN_COLOR).toBe('#DCE8F3');
    expect(WORLD_NO_DATA).toBe('#E6E3DC');
    expect(WORLD_RELATIVE_SCALE).not.toContain(WORLD_NO_DATA);
    expect(WORLD_RELATIVE_SCALE).not.toContain(WORLD_OCEAN_COLOR);
  });

  it('золото первого места убрано: модель не знает «первого места», страна на первом месте — самая тёмная ступень', () => {
    const values = Object.fromEntries(Array.from({ length: 35 }, (_, index) => [`c${index}`, index + 1]));
    const model = buildWorldColorModel(values, { direction: 'desc' });
    expect(model.isTop).toBeUndefined();
    expect(model.hasTop).toBeUndefined();
    expect(model.colorFor(35)).toBe(WORLD_RELATIVE_SCALE[6]);
    const ascending = buildWorldColorModel(values, { direction: 'asc' });
    expect(ascending.colorFor(1)).toBe(WORLD_RELATIVE_SCALE[6]);
  });

  it('цвета выбранной страны: светлая заливка, белое гало и тёмная кромка', () => {
    expect(WORLD_SELECT_FILL).toMatch(/^rgba\(255,255,255/);
    expect(WORLD_SELECT_HALO).toBe('#FFFFFF');
    expect(WORLD_SELECT_INK).toBe('#16264F');
  });
});

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

  const invalidValues = [null, undefined, '', ' \t\n', false, true, NaN, Infinity, -Infinity, 'Infinity', 'not-a-number', [], {}];

  it.each(['relative', 'diverging'])('excludes no-data values from the %s sample and its median', (mode) => {
    const observations = [['DE', 3.2], ['US', 4.8]];
    const baseline = buildWorldColorModel(new Map(observations), { mode });
    const model = buildWorldColorModel(new Map([
      ...observations,
      ...invalidValues.map((value, index) => [`missing${index}`, value]),
    ]), { mode });

    expect(model.sampleSize).toBe(2);
    expect(model.median).toBe(3.2);
    expect(model.bins).toEqual(baseline.bins);
    expect(model.colorFor(3.2)).toBe(baseline.colorFor(3.2));
    for (const value of invalidValues) {
      expect(model.colorFor(value)).toBe(WORLD_NO_DATA);
      expect(model.labelColorFor(value)).toBe('#6F746F');
      expect(model.describe(value)).toBeNull();
    }
    const empty = buildWorldColorModel(Object.fromEntries(
      invalidValues.map((value, index) => [`missing${index}`, value]),
    ), { mode });
    expect(empty).toMatchObject({ kind: 'empty', sampleSize: 0, median: null, bins: [] });
  });

  it.each(['relative', 'diverging'])('retains real zero, negative values and numeric strings in the %s sample', (mode) => {
    const model = buildWorldColorModel({ negative: -3, zero: 0, positive: ' 2.5 ' }, { mode });
    expect(model.sampleSize).toBe(3);
    expect(model.median).toBe(0);
    expect(model.colorFor(0)).not.toBe(WORLD_NO_DATA);
    expect(model.colorFor('0')).toBe(model.colorFor(0));
    expect(model.colorFor(' -3 ')).toBe(model.colorFor(-3));
    expect(model.colorFor('2.5')).toBe(model.colorFor(2.5));
    expect(model.describe('0')).toEqual(model.describe(0));
    expect(model.describe(-3)).not.toBeNull();
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

