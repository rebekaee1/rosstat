import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';

const here = dirname(fileURLToPath(import.meta.url));
const read = (name) => readFileSync(join(here, name), 'utf8').replace(/\/\*[\s\S]*?\*\//g, '');
const k6 = read('k6-country.css');
const z5 = read('z5-country.css');
const z6 = read('z6-rating.css');
const world = read('world.css');
const w6d = read('w6d.css');

describe('k6-country.css (зона K6, хрусталь без границ)', () => {
  it('нет рамок, контуров и колец без размытия', () => {
    expect(k6).not.toMatch(/(^|[;{\s])border(-top|-bottom|-left|-right)?\s*:\s*[0-9.]/m);
    expect(k6).not.toMatch(/(^|[;{\s])outline\s*:/m);
    expect(k6).not.toMatch(/box-shadow\s*:\s*0\s+0\s+0\s+\d/);
  });

  it('не анимирует blur, тени и filter', () => {
    for (const css of [k6, z5, z6]) {
      expect(css).not.toMatch(/transition\s*:[^;]*(backdrop-filter|filter)/);
      expect(css).not.toMatch(/animation[^;]*blur/);
    }
    for (const frames of z5.matchAll(/@keyframes\s+([\w-]+)\s*\{([\s\S]*?\})\s*\}/g)) {
      expect(frames[2], frames[1]).not.toMatch(/\b(filter|backdrop-filter|box-shadow|width|height|top|left)\s*:/);
    }
  });

  it('круг 6: место первой тройки — цифра в графитовом круге, без гранёных медалей; золото только точкой у первого места', () => {
    expect(k6).not.toContain('#E9C97A');
    expect(k6).not.toContain('conic-gradient');
    expect(k6).toMatch(/--k6-medal:\s*linear-gradient\(135deg, #2A3550, #1E2638\)/);
    expect(k6).toMatch(/\.w2-rank-pos\[data-medal\]/);
    expect(k6).toMatch(/\.w2-rank-pos\[data-medal='1'\]::after/);
  });

  it('золотая гравировка цифр «Главного»: градиент в тексте, единица 50 % размера', () => {
    expect(z5).toMatch(/\.z5-key__value > span:not\(\.sr-only\)\s*\{[^}]*background-clip: text/);
    expect(z5).toMatch(/\.z5-key__value small\s*\{[^}]*font-size: clamp\(14px, 0\.5em, 24px\)/);
  });

  it('«год назад»: стеклянная пилюля с плоской точкой, цвет по знаку без красного', () => {
    expect(z5).toMatch(/\.z5-key__ago\.fe-tone--good/);
    expect(z5).toMatch(/\.z5-key__ago\.fe-tone--bad/);
    expect(z5).toMatch(/\.z5-key__ago > \[aria-hidden='true'\]\s*\{[^}]*background: var\(--k6-bead-b\)/);
    expect(z5).not.toMatch(/\.z5-key__ago > \[aria-hidden='true'\]\s*\{[^}]*radial-gradient/);
    expect(z5).not.toMatch(/\.z5-key__ago[^{]*\{[^}]*#DC2626/i);
  });

  it('346 строк страны: blur только у первых шести, дальше content-visibility', () => {
    expect(z5).toMatch(/\.z5-row:nth-child\(-n \+ 6\)\s*\{[^}]*backdrop-filter: blur/);
    expect(z5).toMatch(/\.z5-row:nth-child\(n \+ 13\)\s*\{[^}]*content-visibility: auto/);
    expect(z5).toMatch(/max-width: 767px[\s\S]*?nth-child\(n \+ 3\)\s*\{[^}]*backdrop-filter: none/);
  });

  it('профиль страны: сапфир, силуэт заливается градиентом кристалла', () => {
    expect(z5).toMatch(/fill: url\(#fe-k6-crystal\) #A9BFE0/);
    expect(z5).toMatch(/\.z5-profile::before\s*\{[^}]*radial-gradient/);
    expect(z5).not.toMatch(/\.z5-profile[^{]*\{[^}]*linear-gradient\(rgba\(255, 255, 255, 0\.07\) 1px/);
  });

  it('рейтинг: полки 52 px с зазором 6 px, трубка с концом-бусиной, плиты первого и последнего места', () => {
    expect(z6).toMatch(/border-spacing: 0 6px/);
    expect(z6).toMatch(/tbody td\s*\{[^}]*height: 52px/);
    expect(z6).toMatch(/\.w6d-bar > span::after/);
    expect(z6).toMatch(/\.z6-ribbon \.w2-fact\[data-place='last'\]/);
    expect(z6).not.toMatch(/inset 3px 0 0/);
    expect(z6).not.toMatch(/width: 4px;\s*background: linear-gradient\(180deg/);
  });

  it('годы рейтинга — одна лента L2, на телефоне прокрутка с маской', () => {
    expect(w6d).toMatch(/\.w6d-years__list\s*\{[^}]*inset 0 2px 6px/);
    expect(w6d).toMatch(/max-width: 639px\)\s*\{\s*\.w6d-years__list\s*\{[^}]*overflow-x: auto/);
  });

  it('круг 4: заливки топ-3 — лёгкий оттенок стекла, альфа не выше .35', () => {
    for (const m of k6.matchAll(/--k6-tint-[a-z-]+:\s*rgba\([^)]*,\s*([0-9.]+)\)/g)) {
      expect(Number(m[1]), m[0]).toBeLessThanOrEqual(0.35);
    }
    expect(z6).toMatch(/\[data-top='1'\] td \{ background: linear-gradient\(var\(--k6-tint-gold\)[^}]*var\(--fe-glass-l1\)/);
  });

  it('круг 4: пятна страны меньше и тише, текст героя не шире 58 %', () => {
    expect(z5).toMatch(/\.z5-mood::after\s*\{[^}]*width: 40%;[^}]*opacity: 0\.12/);
    expect(z5).toMatch(/\.z5-hero__lead \{[^}]*max-width: 58%/);
  });

  it('круг 5: крупные стёкла (герой, подложка, плитки, плиты) прозрачнее .6 и с внутренним бликом', () => {
    const light = k6.split(':root[data-theme')[0];
    for (const name of ['hero', 'tray', 'tile', 'plate', 'row']) {
      const m = light.match(new RegExp(`--k6-${name}-glass:\\s*linear-gradient\\(([^;]*)\\);`));
      expect(m, name).toBeTruthy();
      for (const alpha of m[1].matchAll(/rgba\(255, 255, 255, ([0-9.]+)\)/g)) {
        expect(Number(alpha[1]), `${name} ${alpha[0]}`).toBeLessThanOrEqual(0.52);
      }
    }
    expect(light).toMatch(/--k6-row-glass-alt:\s*linear-gradient\(135deg, rgba\(255, 255, 255, 0\.38\), rgba\(255, 255, 255, 0\.26\)\)/);
    expect(k6).toContain('--k6-glass-glint: inset 0 1px 0');
    expect(z5).toMatch(/\.fe-data-header\.z5-hero \{[^}]*var\(--k6-hero-glass/);
    expect(z5).toMatch(/\.z5-key-grid, \.z5-ru-main \{[^}]*var\(--k6-tray-glass/);
    expect(z5).toMatch(/\.z5-key \{[^}]*var\(--k6-tile-glass/);
  });

  it('круг 5: без backdrop-filter стёкла плотнеют, а плиты рейтинга на телефоне без blur', () => {
    expect(k6).toMatch(/@supports not \(\(backdrop-filter: blur\(1px\)\)[\s\S]*--k6-hero-glass: linear-gradient\(160deg, rgba\(255, 255, 255, 0\.9\)/);
    expect(z6).toMatch(/\.z6-ribbon \.w2-fact \{[^}]*backdrop-filter: blur/);
    expect(z6).toMatch(/max-width: 767px\)\s*\{\s*\.z6-ribbon \.w2-fact \{[^}]*backdrop-filter: none/);
  });

  it('кольца вокруг активных элементов заменены свечением с размытием', () => {
    for (const css of [z5, z6, world, w6d, k6]) {
      expect(css).not.toMatch(/box-shadow\s*:[^;]*0\s+0\s+0\s+[0-9.]+px/);
    }
  });

  it('движение выключается: плавание пятен страны и строки рейтинга', () => {
    expect(z5).toMatch(/prefers-reduced-motion: reduce\)\s*\{\s*\.z5-mood::before, \.z5-mood::after \{ animation: none; \}/);
    expect(z5).toMatch(/html\[data-fe-motion='off'\] \.z5-mood::before/);
    expect(z6).toMatch(/prefers-reduced-motion: reduce[\s\S]*\.z6-row, \.z6-table-card \.w6d-bar > span/);
  });
});
