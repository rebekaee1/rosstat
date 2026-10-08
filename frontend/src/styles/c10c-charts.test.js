import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';

const here = dirname(fileURLToPath(import.meta.url));
const read = (name) => readFileSync(join(here, name), 'utf8').replace(/\/\*[\s\S]*?\*\//g, '');
const k4 = read('k4-charts.css');
const delta = read('c10c-delta.css');

describe('k4-charts.css, круг 10 (зона «графики»)', () => {
  it('линии без размытой тени и градиента: нет «двойной линии» (Г1)', () => {
    // Тень со смещением вниз читалась как вторая линия под основной.
    expect(k4).not.toMatch(/\.k4-(ribbon|forecast)[^{]*\{[^}]*drop-shadow/);
    expect(k4).not.toMatch(/\.k4-glass[^{]*\{[^}]*drop-shadow/);
    expect(k4).not.toMatch(/\.sparkline-svg[^{]*\{[^}]*drop-shadow/);
    // Блик-штрих спрятан везде, включая сравнение.
    expect(k4).toMatch(/\.k4-gloss\s*\{\s*display:\s*none/);
    // Образцы в легенде того же цвета, что и линия.
    expect(k4).not.toMatch(/\.k4-swatch--(ribbon|sapphire|forecast)\s*\{[^}]*gradient/);
  });

  it('у спарклайна линия и заливка одного цвета', () => {
    const stops = [...k4.matchAll(/\.sparkline-svg linearGradient[^{]*\{\s*stop-color:\s*(#[0-9A-Fa-f]{6})/g)].map((m) => m[1]);
    expect(stops).toHaveLength(4);
    expect(new Set(stops).size).toBe(1);
  });

  it('граница прогноза не имеет свечения', () => {
    expect(k4).not.toMatch(/k4-beam__glow/);
  });
});

describe('c10c-delta.css (Г3)', () => {
  it('число изменения красится в цвет смысла, без рамок', () => {
    expect(delta).toMatch(/\.fe-delta-badge\.fe-tone--good,\s*\.fe-delta-badge\.fe-tone--bad\s*\{\s*color:\s*var\(--fe-delta-ink\)/);
    expect(delta).not.toMatch(/border|outline/);
  });
});
