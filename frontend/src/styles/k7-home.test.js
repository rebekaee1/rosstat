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

  it('круг 6: шкала места — тонкая полоса лёд → синий и плоская точка, без столбиков; кадр героя и карточка планеты поправлены', () => {
    expect(k7).toMatch(/\.fe-today__scale\s*\{[^}]*height:\s*4px[^}]*linear-gradient\(90deg, #C9D7EA/);
    expect(k7).toMatch(/\.fe-today__gem\s*\{[^}]*left:\s*calc\(var\(--fe-rank-pos/);
    expect(k7).not.toMatch(/fe-today__ladder/);
    expect(z3).not.toMatch(/fe-today__ladder|fe-today-bar/);
    expect(k7).not.toMatch(/--fe-hero-frame-right\s*:/);
    expect(hero).toMatch(/\.fe-hero-planet\s*\{\s*position:\s*sticky/);
  });

  it('круг 6 (зона B): пиксельный арт forecast-glass убран, вместо него стеклянная F в плите планеты и у заголовка на телефоне', () => {
    const indexCss = readFileSync(join(here, '..', 'index.css'), 'utf8');
    expect(indexCss).not.toContain('forecast-glass');
    expect(indexCss).not.toMatch(/\[data-block="home-hero"\]::before/);
    // Плита: кадр 2x, обычное смешение, прозрачность .35-.5, маска; подключается только по атрибуту после load.
    const plate = k7.match(/html\[data-fe-f="on"\] \.fe-dashboard \.fe-hero-planet \[data-block="home-workbench"\]::before \{[^}]*\}/)[0];
    expect(plate).toContain("/brand/emblem-f-2x.webp");
    expect(plate).toMatch(/aspect-ratio:\s*1149 \/ 1552/);
    expect(plate).toMatch(/height:\s*min\([^;]*70svh, 760px\)/);
    expect(plate).toMatch(/z-index:\s*-1/);
    expect(plate).toMatch(/mask-image:/);
    expect(plate).not.toMatch(/mix-blend-mode/);
    const op = Number(/opacity:\s*([0-9.]+)/.exec(plate)[1]);
    expect(op).toBeGreaterThanOrEqual(0.35);
    expect(op).toBeLessThanOrEqual(0.5);
    // Телефон: F справа от заголовка, ширина текста сужена на ширину F, поиск ниже.
    const phone = k7.match(/html\[data-fe-f="on"\] \.fe-dashboard \.fe-hero-text::after \{[^}]*\}/)[0];
    expect(phone).toContain("/brand/emblem-f-phone.webp");
    expect(k7).toMatch(/h1 \+ p \{ max-width: calc\(100% - 128px\); \}/);
  });

  it('у трёх панелей «Попробуйте сами» разные лампы, у плиток «Мир сейчас» четыре оттенка', () => {
    expect(k7).toMatch(/\.fe-tool:nth-child\(2\)\s*\{\s*--lamp:\s*var\(--k7-lamp-rose\)/);
    expect(k7).toMatch(/\.fe-tool:nth-child\(3\)\s*\{\s*--lamp:\s*var\(--k7-lamp-ice\)/);
    for (const tint of ['prices', 'jobs', 'home']) expect(k7).toContain(`data-tile='${tint}'`);
  });
});
