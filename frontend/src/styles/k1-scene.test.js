import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';

const here = dirname(fileURLToPath(import.meta.url));
const css = readFileSync(join(here, 'k1-scene.css'), 'utf8');
const stripped = css.replace(/\/\*[\s\S]*?\*\//g, '');

describe('k1-scene.css', () => {
  it('нет рамок, колец и контуров', () => {
    expect(stripped).not.toMatch(/(^|[;{\s])border(-top|-bottom|-left|-right)?\s*:/m);
    expect(stripped).not.toMatch(/(^|[;{\s])outline\s*:/m);
    expect(stripped).not.toMatch(/box-shadow\s*:\s*0\s+0\s+0\s+\d/);
  });

  it('не анимирует blur, тени и filter (только transform, opacity, background-position)', () => {
    expect(stripped).not.toMatch(/transition\s*:[^;]*(backdrop-filter|box-shadow|filter)/);
    expect(stripped).not.toMatch(/animation[^;]*blur/);
    for (const frames of stripped.matchAll(/@keyframes\s+([\w-]+)\s*\{([\s\S]*?\})\s*\}/g)) {
      expect(frames[2], frames[1]).not.toMatch(/\b(filter|backdrop-filter|box-shadow|width|height|top|left)\s*:/);
    }
  });

  it('объявляет классы света для всех зон', () => {
    for (const cls of ['.fe-glint', '.fe-cursor-light', '.fe-drift', '.fe-cv-auto', '.fe-blur-cap']) {
      expect(stripped).toContain(cls);
    }
  });

  it('движение выключается и системной настройкой, и режимом сцены', () => {
    expect(stripped).toMatch(/@media \(prefers-reduced-motion: reduce\)/);
    expect(stripped).toMatch(/html\[data-fe-motion="off"\] \.fe-drift/);
    expect(stripped).toMatch(/html\[data-fe-lite="on"\] \.fe-scene-leak/);
  });

  it('на телефоне плавание каустик выключено (одна анимация в кадре)', () => {
    expect(stripped).toMatch(/@media \(max-width: 767px\)\s*\{\s*\.fe-scene__lamp \{ animation: none; \}/);
  });

  it('ссылается только на кадры, которые лежат в public/brand', () => {
    for (const m of stripped.matchAll(/url\('(\/brand\/[^']+)'\)/g)) {
      const file = join(here, '..', '..', 'public', m[1]);
      expect(() => readFileSync(file)).not.toThrow();
    }
  });

  it('герой лежит поверх страницы и смешивается multiply (приёмка F1.1: под страницей его закрывали панели)', () => {
    const base = stripped.match(/\.fe-scene-hero \{[^}]*\}/)[0];
    expect(base).toMatch(/z-index:\s*1;/);
    expect(base).toMatch(/mix-blend-mode:\s*multiply/);
    expect(base).toMatch(/pointer-events:\s*none/);
    expect(base).toMatch(/aspect-ratio:\s*1600 \/ 893/);
    for (const v of ['--fe-hero-frame-w', '--fe-hero-frame-right', '--fe-hero-frame-top']) {
      expect(base).toContain(v);
    }
    expect(stripped).toMatch(/\.fe-scene-hero\[data-fe-hero="country"\]/);
  });

  it('у каустик нет края: градиент гаснет до 85 %, элемент закрыт радиальной маской и больше пятна (F1.2)', () => {
    for (const name of ['gold', 'ice', 'rose']) {
      const rule = stripped.match(new RegExp(`\\.fe-scene__lamp--${name} \\{[^}]*\\}`))[0];
      expect(rule).toMatch(/transparent 82%/);
      expect(rule).not.toMatch(/closest-side, var\(--fe-scene-\w+\), transparent\)/);
    }
    const lamp = stripped.match(/\.fe-scene__lamp \{[^}]*\}/)[0];
    expect(lamp).toMatch(/mask-image:\s*radial-gradient\(closest-side/);
    expect(lamp).not.toMatch(/border-radius/);
  });

  it('у кадра героя нет прямых краёв: эллиптическая маска на десктопе и на телефоне (G1.1)', () => {
    const base = stripped.match(/\.fe-scene-hero \{[^}]*\}/)[0];
    expect(base).toMatch(/mask-image:[^;]*radial-gradient\(ellipse/);
    expect(base).toMatch(/mask-composite:\s*intersect, intersect/);
  });

  it('круг 6: на телефоне кристаллов героя нет, вместо них стеклянная F; кадр hero-phone убран', () => {
    expect(stripped).toMatch(/@media \(max-width: 767px\) \{\s*\.fe-scene-hero \{ display: none; \}/);
    expect(stripped).not.toContain('hero-phone');
    const f = stripped.match(/\.fe-scene__f \{[^}]*\}/)[0];
    expect(f).toMatch(/aspect-ratio:\s*1149 \/ 1552/);
    expect(f).toMatch(/height:\s*min\(64vh, 760px\)/);
    expect(f).toMatch(/mask-image:/);
    expect(f).not.toMatch(/mix-blend-mode/);
    expect(stripped).toMatch(/\.fe-scene__f\.is-ready \{ opacity: var\(--fe-scene-f-opacity, 0\.42\)/);
    expect(stripped).toMatch(/\.fe-scene__f\[data-fe-f-mode="phone"\] \{ display: none; \}/);
    expect(stripped).toMatch(/html\[data-fe-lite="on"\] \.fe-scene__f/);
  });

  it('круг 6: тёплое пятно сцены одно (альфа ≤ .18), лёд и «роза» холодные, на телефоне лёд .14 и пятно не у левого края', () => {
    const gold = /--fe-scene-gold:\s*rgba\(\d+, \d+, \d+, ([0-9.]+)\)/.exec(stripped);
    expect(Number(gold[1])).toBeLessThanOrEqual(0.18);
    expect(stripped).toMatch(/--fe-scene-ice:\s*rgba\(190, 212, 246, 0\.3\)/);
    expect(stripped).toMatch(/--fe-scene-rose:\s*rgba\(178, 192, 238, 0\.2\)/);
    expect(stripped).not.toMatch(/--fe-scene-spot-peach:\s*rgba\(244, 196, 164/);
    expect(stripped).toMatch(/\.fe-scene \{ --fe-scene-ice: rgba\(204, 222, 250, 0\.14\); \}/);
    expect(stripped).toMatch(/\.fe-scene__lamp--ice \{ left: 8vw;/);
  });

  it('круг 5: пятна и блики без blur и backdrop-filter, гаснут при Save-Data и не плавают на телефоне', () => {
    expect(stripped).not.toMatch(/backdrop-filter\s*:\s*blur/);
    for (const name of ['gold', 'sapphire', 'ice', 'peach']) {
      const rule = stripped.match(new RegExp(`\\.fe-scene__spot--${name} \\{[^}]*\\}`))[0];
      expect(rule).toMatch(/transparent 82%/);
    }
    expect(stripped).toMatch(/\.fe-scene__spot \{[^}]*mask-image:\s*radial-gradient\(closest-side/);
    expect(stripped).toMatch(/html\[data-fe-lite="on"\] \.fe-scene__spots/);
    expect(stripped).toMatch(/html\[data-fe-lite="on"\] \.fe-scene__glints/);
    expect(stripped).toMatch(/\.fe-scene \.fe-scene__spot \{ animation: none;/);
  });

  it('круг 5: базовый кадр целиком в окне, у 404 свой вариант кадра', () => {
    const base = stripped.match(/\.fe-scene-hero \{[^}]*\}/)[0];
    expect(base).toMatch(/--fe-hero-frame-w:\s*min\(32vw, 480px\)/);
    expect(base).toMatch(/--fe-hero-frame-right:\s*-1\.2vw/);
    expect(stripped).toMatch(/\.fe-scene-hero\[data-fe-hero="notfound"\] \{[^}]*--fe-hero-frame-right: 3vw/);
  });
});
