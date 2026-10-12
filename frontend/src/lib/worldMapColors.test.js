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

const hexToRgb = (hex) => [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16));
const luminance = (hex) => {
  const [r, g, b] = hexToRgb(hex).map((v) => v / 255).map((v) => (v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4));
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
};
const contrast = (a, b) => {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
};
const hue = (hex) => {
  const [r, g, b] = hexToRgb(hex).map((v) => v / 255);
  const max = Math.max(r, g, b);
  const d = max - Math.min(r, g, b);
  if (d === 0) return null;
  const h = max === r ? ((g - b) / d) % 6 : max === g ? (b - r) / d + 2 : (r - g) / d + 4;
  return (h * 60 + 360) % 360;
};

describe('круг 12: двойной сине-коричневый градиент', () => {
  it('семь ступеней: синяя сторона, нейтральный центр, коричневая сторона', () => {
    expect(WORLD_RELATIVE_SCALE).toEqual(['#1D3A82', '#3F74BB', '#7BA2D3', '#ADB2BC', '#B9957A', '#8C5F42', '#52311F']);
    expect(WORLD_DIVERGING_SCALE).toEqual(WORLD_RELATIVE_SCALE);
    for (const hex of WORLD_RELATIVE_SCALE.slice(0, 3)) expect(hue(hex)).toBeGreaterThan(200); // синие
    for (const hex of WORLD_RELATIVE_SCALE.slice(4)) expect(hue(hex)).toBeLessThan(30); // коричневые: не рыжие (выше 30) и не золото (около 41)
    for (const hex of WORLD_RELATIVE_SCALE.slice(4)) {
      const [r, g, b] = hexToRgb(hex);
      expect(r).toBeGreaterThan(g);
      expect(g).toBeGreaterThan(b); // тёплая сторона, но без зелёного и красного смысла «хорошо/плохо»
    }
    const [r, g, b] = hexToRgb(WORLD_RELATIVE_SCALE[3]);
    expect(Math.max(r, g, b) - Math.min(r, g, b)).toBeLessThan(16); // центр почти серый
  });

  it('светлота падает от центра к обоим краям без скачков: оба края шкалы тёмные, центр самый светлый', () => {
    const lums = WORLD_RELATIVE_SCALE.map(luminance);
    for (let i = 1; i <= 3; i += 1) expect(lums[i]).toBeGreaterThan(lums[i - 1]);
    expect(lums[4]).toBeLessThan(lums[3]);
    for (let i = 5; i < 7; i += 1) expect(lums[i]).toBeLessThan(lums[i - 1]);
    expect(lums.indexOf(Math.max(...lums))).toBe(3);
  });

  it('все ступени отделены от океана и суши без данных, центр различим с ними по светлоте', () => {
    for (const hex of WORLD_RELATIVE_SCALE) {
      expect(contrast(hex, WORLD_OCEAN_COLOR)).toBeGreaterThanOrEqual(1.6);
      expect(contrast(hex, WORLD_NO_DATA)).toBeGreaterThanOrEqual(1.6);
    }
    expect(contrast(WORLD_RELATIVE_SCALE[0], WORLD_OCEAN_COLOR)).toBeGreaterThan(8);
    expect(contrast(WORLD_RELATIVE_SCALE[6], WORLD_OCEAN_COLOR)).toBeGreaterThan(8);
  });

  it('малые значения синие, большие коричневые; порядок «по возрастанию» меняет стороны местами', () => {
    const values = Object.fromEntries(Array.from({ length: 35 }, (_, index) => [`c${index}`, index + 1]));
    const desc = buildWorldColorModel(values, { direction: 'desc' });
    expect(desc.colorFor(1)).toBe('#1D3A82');
    expect(desc.colorFor(18)).toBe('#ADB2BC');
    expect(desc.colorFor(35)).toBe('#52311F');
    const asc = buildWorldColorModel(values, { direction: 'asc' });
    expect(asc.colorFor(1)).toBe('#52311F');
    expect(asc.colorFor(35)).toBe('#1D3A82');
  });

  it('режим diverging: ноль — серый центр, отрицательные синие, положительные коричневые', () => {
    const model = buildWorldColorModel({ a: -9, b: 0, c: 9 }, { mode: 'diverging' });
    expect(model.colorFor(-9)).toBe('#1D3A82');
    expect(model.colorFor(0)).toBe('#ADB2BC');
    expect(model.colorFor(9)).toBe('#52311F');
  });

  it('подписи полос читаются на светлом стекле (контраст не ниже 4,5:1) и принадлежат своей стороне', () => {
    const values = Object.fromEntries(Array.from({ length: 35 }, (_, index) => [`c${index}`, index + 1]));
    const model = buildWorldColorModel(values);
    const inks = [1, 5, 9, 18, 22, 28, 35].map((value) => model.labelColorFor(value));
    for (const ink of inks) expect(contrast(ink, '#FFFFFF')).toBeGreaterThanOrEqual(4.5);
    expect(hue(inks[0])).toBeGreaterThan(200);
    expect(hue(inks[6])).toBeLessThan(30);
  });

  it('держит океан #DCE8F3 и нейтральную сушу без данных #E6E3DC отдельно от шкалы', () => {
    expect(WORLD_OCEAN_COLOR).toBe('#DCE8F3');
    expect(WORLD_NO_DATA).toBe('#E6E3DC');
    expect(WORLD_RELATIVE_SCALE).not.toContain(WORLD_NO_DATA);
    expect(WORLD_RELATIVE_SCALE).not.toContain(WORLD_OCEAN_COLOR);
  });

  it('золото первого места убрано: модель не знает «первого места», страна на первом месте — край шкалы без особого цвета', () => {
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

