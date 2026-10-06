// K5 (раунд 3): стражи стилей зоны «показатель, сравнение, прогнозы».
// Рамок нет (общий страж no-borders), blur не добавляется и не анимируется, движение гаснет, золото читается.
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';

const here = dirname(fileURLToPath(import.meta.url));
const read = (name) => readFileSync(join(here, name), 'utf8');
const k5 = read('k5-pages.css');
const zb = read('zb-forecasts.css');
const z7 = read('z7-compare.css');

describe('k5-pages.css', () => {
  it('не анимирует blur, тени и фильтры', () => {
    expect(k5).not.toMatch(/transition\s*:[^;]*(backdrop-filter|box-shadow|filter)/);
    expect(k5).not.toMatch(/animation[^;]*blur/);
  });

  it('не добавляет blur: бюджет кадра держат слои T1 и K3', () => {
    expect(k5).not.toMatch(/backdrop-filter\s*:\s*blur/);
  });

  it('сигнальная точка и всё движение отключаются при prefers-reduced-motion', () => {
    expect(k5).toMatch(/@media \(prefers-reduced-motion: reduce\)[\s\S]*\.k5-signal::after\s*\{\s*animation:\s*none/);
    expect(k5).toMatch(/html\[data-fe-motion='off'\] \.k5-signal::after/);
  });

  it('анимирует только transform и opacity', () => {
    const frames = k5.match(/@keyframes[\s\S]*?\n\}/g) || [];
    expect(frames.length).toBeGreaterThan(0);
    for (const block of frames) {
      expect(block).not.toMatch(/box-shadow|filter|clip-path|width|height|top|left/);
    }
  });

  it('есть шов, торец плиты и осколок пустого места', () => {
    expect(k5).toMatch(/\.k5-seam::after/);
    expect(k5).toMatch(/\.fe-chart-card::after/);
    expect(k5).toMatch(/\.k5-shard/);
  });

  it('золотая гравировка не светлее #A07829 (контраст ≥ 3:1 на золотом сиянии шапки)', () => {
    const m = /--k5-gold-text:\s*linear-gradient\(([^;]*)\);/.exec(k5);
    expect(m).not.toBeNull();
    const hexes = [...m[1].matchAll(/#([0-9A-Fa-f]{6})/g)].map((x) => x[1]);
    const lum = (hex) => {
      const c = [0, 2, 4].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255)
        .map((v) => (v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4));
      return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2];
    };
    for (const hex of hexes) expect(lum(hex)).toBeLessThanOrEqual(0.2267);
  });
});

describe('K5 круг 5: стекло плиты и лента сравнения', () => {
  it('плита графика: альфа каждого слоя фона ≤ 0,6 (сквозь стекло видны лампы K1)', () => {
    const m = /--k5-plate:\s*([^;]*);/.exec(k5);
    expect(m).not.toBeNull();
    const alphas = [...m[1].matchAll(/rgba\([^)]*,\s*([0-9.]+)\)/g)].map((x) => Number(x[1]));
    expect(alphas.length).toBeGreaterThan(2);
    for (const a of alphas) expect(a).toBeLessThanOrEqual(0.6);
  });

  it('жёлоб периода целиком внутри плиты на телефоне', () => {
    expect(k5).toMatch(/\.z4-chart-wrap \.fe-brush \{ padding-inline: 14px; \}/);
  });
});

describe('forecasts и compare без пунктира и рамок', () => {
  it('прогнозная линия мини-графика не штриховая, ключи легенды без border', () => {
    expect(zb).not.toMatch(/stroke-dasharray/);
    expect(zb).not.toMatch(/border-top\s*:\s*[0-9.]+px\s+(solid|dashed)/);
  });

  it('подпись конца линии сравнения без border-left', () => {
    const end = /\.fe-compare-end\s*\{[^}]*\}/.exec(z7)?.[0] || '';
    expect(end).not.toMatch(/(^|[;\s{])border(-left|-top|-right|-bottom)?\s*:/);
  });
});
