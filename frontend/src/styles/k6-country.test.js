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

  it('медали: золото, лёд-серебро и бронза из плана K6.5', () => {
    expect(k6).toContain('#E9C97A');
    expect(k6).toContain('#C9D7EA');
    expect(k6).toContain('#E0B08E');
    expect(k6).toMatch(/\.w2-rank-pos\[data-medal='2'\]/);
    expect(k6).toMatch(/\.w2-rank-pos\[data-medal='3'\]/);
  });

  it('золотая гравировка цифр «Главного»: градиент в тексте, единица 50 % размера', () => {
    expect(z5).toMatch(/\.z5-key__value > span:not\(\.sr-only\)\s*\{[^}]*background-clip: text/);
    expect(z5).toMatch(/\.z5-key__value small\s*\{[^}]*font-size: clamp\(14px, 0\.5em, 24px\)/);
  });

  it('«год назад»: стеклянная пилюля с бусиной-свечением, цвет по знаку без красного', () => {
    expect(z5).toMatch(/\.z5-key__ago\.fe-tone--good/);
    expect(z5).toMatch(/\.z5-key__ago\.fe-tone--bad/);
    expect(z5).toMatch(/\.z5-key__ago > \[aria-hidden='true'\]\s*\{[^}]*radial-gradient/);
    expect(z5).not.toMatch(/\.z5-key__ago[^{]*\{[^}]*#DC2626/i);
  });

  it('346 строк страны: blur только у первых шести, дальше content-visibility', () => {
    expect(z5).toMatch(/\.z5-row:nth-child\(-n \+ 6\)\s*\{[^}]*backdrop-filter: blur/);
    expect(z5).toMatch(/\.z5-row:nth-child\(n \+ 13\)\s*\{[^}]*content-visibility: auto/);
    expect(z5).toMatch(/max-width: 767px[\s\S]*?nth-child\(n \+ 3\)\s*\{[^}]*backdrop-filter: none/);
  });

  it('профиль страны: сапфир, силуэт заливается градиентом кристалла', () => {
    expect(z5).toMatch(/fill: url\(#fe-k6-crystal\) #C9A24D/);
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
