import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';

const here = dirname(fileURLToPath(import.meta.url));
const read = (name) => readFileSync(join(here, name), 'utf8').replace(/\/\*[\s\S]*?\*\//g, '');
const k7 = read('k7-home.css');
const hero = read('planet-hero.css');
const z3 = read('z3-home.css');

describe('k7-home.css, planet-hero.css, z3-home.css (главная в хрустале)', () => {
  it('нет рамок, контуров и колец вне фокуса', () => {
    for (const [name, css] of [['k7-home', k7], ['planet-hero', hero], ['z3-home', z3]]) {
      expect(css, name).not.toMatch(/(^|[;{\s])border(-top|-bottom|-left|-right)?\s*:\s*[0-9.]+(px|rem)/m);
      expect(css, name).not.toMatch(/box-shadow\s*:\s*0\s+0\s+0\s+[12]px/);
    }
    // outline допустим только в правилах :focus-visible (разрешённое исключение 1 эталона).
    for (const [name, css] of [['k7-home', k7], ['planet-hero', hero]]) {
      for (const block of css.matchAll(/([^{}]*)\{([^{}]*)\}/g)) {
        if (/(^|[;\s])outline\s*:\s*[0-9]/.test(block[2])) expect(block[1], `${name}: ${block[1].trim()}`).toMatch(/focus-visible/);
      }
    }
  });

  it('новые слои главной без blur: backdrop-filter только сбрасывается', () => {
    for (const [name, css] of [['k7-home', k7], ['planet-hero', hero]]) {
      for (const m of css.matchAll(/backdrop-filter\s*:\s*([^;}]+)/g)) {
        expect(m[1].trim(), `${name}: backdrop-filter`).toBe('none');
      }
    }
  });

  it('планета на главной: чипы, кнопки, подсказка без blur, чипы вынесены над шаром', () => {
    expect(hero).toMatch(/\.planet-quick-chip,[\s\S]*?\.planet-gesture-hint\s*\{[^}]*backdrop-filter:\s*none/);
    expect(hero).toMatch(/\.planet-stage:has\(> \.planet-quick\)\s*\{\s*margin-top:\s*52px/);
    expect(hero).toMatch(/\.planet-quick\s*\{[^}]*top:\s*-52px/);
  });

  it('высота карточки планеты считается от 100vh минус запас на остальное содержимое', () => {
    expect(hero).toMatch(/--planet-scene-height:\s*clamp\(380px,\s*calc\(100vh - 520px\)/);
    expect(hero).toMatch(/--planet-scene-height:\s*clamp\(380px,\s*calc\(100svh - 520px\)/);
  });

  it('движение только transform, opacity и background-position', () => {
    expect(k7).not.toMatch(/transition\s*:[^;]*(backdrop-filter|box-shadow|filter)/);
    for (const frames of k7.matchAll(/@keyframes\s+([\w-]+)\s*\{([\s\S]*?\})\s*\}/g)) {
      expect(frames[2], frames[1]).not.toMatch(/\b(filter|backdrop-filter|box-shadow|width|height|top|left)\s*:/);
    }
    expect(k7).toMatch(/prefers-reduced-motion: reduce/);
    expect(k7).toMatch(/html\[data-fe-motion='off'\]/);
  });

  it('длинный каталог: content-visibility у карточек после первых 16', () => {
    expect(k7).toMatch(/\.fe-country-grid > li:nth-child\(n \+ 17\)\s*\{[^}]*content-visibility:\s*auto/);
  });

  it('у трёх панелей «Попробуйте сами» разные лампы, у плиток «Мир сейчас» четыре оттенка', () => {
    expect(k7).toMatch(/\.fe-tool:nth-child\(2\)\s*\{\s*--lamp:\s*var\(--k7-lamp-rose\)/);
    expect(k7).toMatch(/\.fe-tool:nth-child\(3\)\s*\{\s*--lamp:\s*var\(--k7-lamp-ice\)/);
    for (const tint of ['prices', 'jobs', 'home']) expect(k7).toContain(`data-tile='${tint}'`);
  });
});
