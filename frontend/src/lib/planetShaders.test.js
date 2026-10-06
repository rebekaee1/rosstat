import { describe, expect, it } from 'vitest';
import { PLANET_FRAGMENT } from './planetShaders';

/**
 * «Чёрные точки» на шаре (круг 6): насыщение `mix(gray, land, 1.16)` экстраполирует, и у текселя дневной карты с каналом около нуля
 * (густой лес, тёмная вода у берега: 0,2 % текселей карты 4096 по Кавказу, Каспию, Аралу, востоку США) канал уходит в минус;
 * `pow(отрицательное, 0.74)` в GLSL не определён, на Metal и ANGLE это NaN, а NaN рисуется твёрдой чёрной точкой в размер текселя.
 */
const LUMA = [0.2126, 0.7152, 0.0722];
const srgbToLinear = (c) => (c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4);
const luminance = (rgb) => rgb.reduce((sum, value, index) => sum + value * LUMA[index], 0);

/** Зеркало строк `land = ...` шейдера; clamp включается параметром, чтобы показать разницу. */
function landChannels(texel, { clamped }) {
  const day = texel.map((value) => srgbToLinear(value / 255));
  const lum = luminance(day);
  const soft = day.map((value) => value + (lum - value) * 0.08);
  const gray = luminance(soft);
  let land = soft.map((value) => gray + (value - gray) * 1.16);
  if (clamped) land = land.map((value) => Math.max(value, 0));
  return land.map((value) => value ** 0.74);
}

// Реальные тексели из earth_day_4096.jpg, на которых шейдер рисовал чёрную точку (RGB 0..255).
const SPECK_TEXELS = [[38, 55, 6], [34, 51, 4], [3, 26, 94], [1, 27, 78], [0, 3, 71], [37, 61, 7]];

describe('planet fragment shader: no NaN specks', () => {
  it('shows that the old saturation boost was undefined on dark saturated texels (the cause of the specks)', () => {
    for (const texel of SPECK_TEXELS) {
      expect(landChannels(texel, { clamped: false }).some(Number.isNaN)).toBe(true);
    }
  });

  it('clamps the boosted colour to zero before pow(), so every texel stays a number', () => {
    for (const texel of SPECK_TEXELS) {
      const land = landChannels(texel, { clamped: true });
      expect(land.every((value) => Number.isFinite(value) && value >= 0)).toBe(true);
    }
    const saturation = PLANET_FRAGMENT.indexOf('land = mix(vec3(dot(land');
    const clamp = PLANET_FRAGMENT.indexOf('land = max(land, vec3(0.0));');
    const power = PLANET_FRAGMENT.indexOf('land = pow(land');
    expect(saturation).toBeGreaterThan(-1);
    expect(clamp).toBeGreaterThan(saturation);
    expect(power).toBeGreaterThan(clamp);
  });

  it('keeps every pow() base provably non-negative', () => {
    const code = PLANET_FRAGMENT.replace(/\/\/.*$/gm, '');
    const bases = [];
    for (let at = code.indexOf('pow('); at !== -1; at = code.indexOf('pow(', at + 4)) {
      let depth = 0;
      let start = at + 4;
      for (let index = at + 3; index < code.length; index += 1) {
        const char = code[index];
        if (char === '(') depth += 1;
        if (char === ')') depth -= 1;
        if (char === ',' && depth === 1) { bases.push(code.slice(start, index).trim()); break; }
      }
    }
    expect(bases.length).toBe(4);
    const safe = [
      'land', // clamped with max() right above
      '(c + 0.055) / 1.055', // c is clamped to 0..1 in srgbToLinear
      'max(dot(reflect(-sunDirection, normal), toCamera), 0.0)',
      'max(1.0 - facing, 0.0)',
    ];
    for (const base of bases) expect(safe).toContain(base);
  });

  it('decodes colours through one clamped sRGB helper', () => {
    expect(PLANET_FRAGMENT).toContain('vec3 srgbToLinear(vec3 c)');
    expect(PLANET_FRAGMENT).toMatch(/srgbToLinear\(atlas\.rgb \/ max\(atlas\.a, 0\.004\)\)/);
  });
});

describe('planet fragment shader: round 6 palette', () => {
  it('draws the data globe in the agreed ocean and no-data land colours', () => {
    // #DCE8F3 and #E6E3DC as sRGB 0..1
    expect(PLANET_FRAGMENT).toContain('vec3(0.8627, 0.9098, 0.9529)');
    expect(PLANET_FRAGMENT).toContain('vec3(0.9020, 0.8902, 0.8627)');
    expect(Math.round(0.8627 * 255).toString(16) + Math.round(0.9098 * 255).toString(16) + Math.round(0.9529 * 255).toString(16)).toBe('dce8f3');
    expect(Math.round(0.902 * 255).toString(16) + Math.round(0.8902 * 255).toString(16) + Math.round(0.8627 * 255).toString(16)).toBe('e6e3dc');
  });

  it('outlines the selected country with a thin blue light, not gold', () => {
    expect(PLANET_FRAGMENT).toContain('SELECT_SRGB');
    expect(PLANET_FRAGMENT).not.toMatch(/goldSelected|goldHovered/);
  });
});
