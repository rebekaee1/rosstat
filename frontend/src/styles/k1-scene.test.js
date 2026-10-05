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
});
