// Стражи K8 (раунд 3, «Инструменты в хрустале»): в k8-tools.css нет рамок, ни одна тень, blur или filter не анимируется,
// у новых движений есть выключатель, а свечение фокуса размыто не меньше чем на 8 px (не кольцо).
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';

const here = dirname(fileURLToPath(import.meta.url));
const css = readFileSync(join(here, 'k8-tools.css'), 'utf8');
const z8 = readFileSync(join(here, 'z8-tools.css'), 'utf8');
const noComments = (text) => text.replace(/\/\*[\s\S]*?\*\//g, '');
const k8 = noComments(css);

describe('k8-tools.css', () => {
  it('не рисует рамок и колец (кроме разрешённой нижней линии ошибки и глифов)', () => {
    expect(k8).not.toMatch(/(^|[;{\s])border(-top|-bottom|-left|-right)?\s*:\s*[0-9.]+(px|rem)\s+(solid|dashed|dotted)/);
    expect(k8).not.toMatch(/box-shadow\s*:[^;}]*0\s+0\s+0\s+[12](\.\d+)?px/);
    expect(k8).not.toMatch(/\boutline\s*:\s*[0-9.]+px/);
  });

  it('анимирует только transform, opacity и background-position', () => {
    const transitions = k8.match(/transition\s*:[^;}]+/g) || [];
    for (const decl of transitions) {
      expect(decl, decl).not.toMatch(/box-shadow|backdrop-filter|filter|blur|width|height/);
    }
    for (const keyframes of k8.match(/@keyframes[^{]+\{([^{}]*\{[^{}]*\})+[^{}]*\}/g) || []) {
      expect(keyframes, keyframes).not.toMatch(/box-shadow|filter|blur|width|height/);
    }
  });

  it('свечение фокуса размыто не меньше 8 px, это не кольцо', () => {
    const glow = /--k8-well-glow:\s*0\s+0\s+(\d+)px\s+(\d+)px/.exec(k8);
    expect(glow).not.toBeNull();
    expect(Number(glow[1])).toBeGreaterThanOrEqual(8);
    expect(k8).toMatch(/--k8-well-shadow:\s*inset 0 3px 8px rgba\(30, 38, 56, 0\.12\), inset 0 -1px 0 rgba\(255, 255, 255, 0\.85\)/);
  });

  it('у ползунка ручка 26 px (28 px на касании) и тонкий жёлоб с синей заливкой (круг 6)', () => {
    expect(k8).toMatch(/--k8-bead-size:\s*26px/);
    expect(k8).toMatch(/\(pointer: coarse\)[\s\S]*--k8-bead-size:\s*28px/);
    expect(k8).toMatch(/::-webkit-slider-runnable-track/);
    expect(k8).toMatch(/::-moz-range-progress/);
  });

  it('панель поиска: blur 28 на компьютере, плотный запасной вариант без backdrop-filter', () => {
    expect(k8).toMatch(/--k8-search-blur:\s*28px/);
    expect(k8).toMatch(/\.fe-search-panel\s*\{[^}]*blur\(var\(--k8-search-blur\)\)/);
    expect(k8).toMatch(/@supports not \(\(backdrop-filter: blur\(1px\)\)/);
  });

  it('есть выключатель движения', () => {
    expect(k8).toMatch(/@media \(prefers-reduced-motion: reduce\)/);
    expect(k8).toMatch(/\.fe-k8-sticky\s*\{\s*animation:\s*none/);
  });

  it('плашка результата на телефоне скрыта от 1024 px и стоит над доком', () => {
    expect(k8).toMatch(/\.fe-k8-sticky\s*\{[^}]*var\(--fe-dock-h, 0px\)/);
    expect(k8).toMatch(/@media \(min-width: 1024px\)\s*\{\s*\.fe-k8-sticky\s*\{\s*display:\s*none/);
  });
});

describe('k8-tools.css, круг 4', () => {
  it('подложка поиска тёплая, прозрачная (альфа ≤ 0,35 в светлой теме) и размыта не больше чем на 14 px', () => {
    const block = /\.fe-k8-scrim\s*\{([^}]*)\}/.exec(k8);
    expect(block).not.toBeNull();
    const alphas = [...block[1].matchAll(/rgba\([^)]*,\s*([0-9.]+)\)/g)].map((m) => Number(m[1]));
    expect(alphas.length).toBeGreaterThanOrEqual(3);
    for (const a of alphas) expect(a).toBeLessThanOrEqual(0.35);
    const blurs = [...k8.matchAll(/\.fe-k8-scrim[^{]*\{[^}]*blur\((\d+)px\)/g)].map((m) => Number(m[1]));
    expect(blurs.length).toBeGreaterThan(0);
    for (const b of blurs) expect(b).toBeLessThanOrEqual(14);
    expect(block[1]).not.toMatch(/rgba\(\s*(0|20|40|60|128),\s*(0|20|40|60|128),\s*(0|20|40|60|128)/);
  });

  it('плашка результата стоит над доком на 8 px, одной строкой не выше 44 px', () => {
    const block = /\.fe-k8-sticky\s*\{([^}]*)\}/.exec(k8)[1];
    expect(block).toMatch(/bottom:\s*calc\(var\(--fe-dock-h, 0px\) \+ 8px/);
    expect(block).toMatch(/min-height:\s*44px/);
    expect(k8).toMatch(/\.fe-k8-sticky__row\s*\{\s*display:\s*flex/);
  });
});

describe('z8-tools.css (K8)', () => {
  it('вкладки-жёлоб: бегунок едет только transform, номер задаёт разметка', () => {
    expect(z8).toMatch(/\.fe-z8-seg::before[\s\S]*translateX\(calc\(var\(--k8-i, 0\) \* 100%\)\)/);
    expect(z8).toMatch(/\.fe-z8-tabs::before[\s\S]*translateX\(calc\(var\(--k8-i, 0\) \* \(100% \+ 6px\)\)\)/);
    expect(z8).toMatch(/transition: transform 0\.26s var\(--k8-spring, ease\), opacity 0\.2s ease/);
  });

  it('кнопка «⇄» золотая бусина с поворотом на 180° за нажатие', () => {
    expect(z8).toMatch(/\.fe-z8-swap svg\s*\{\s*transform: rotate\(var\(--k8-turn, 0deg\)\)/);
  });

  it('карточка «Курс ЦБ» без золотой окантовки: свет задают заливка и тень', () => {
    const cb = /\.fe-z8-rate--cb\s*\{([^}]*)\}/.exec(noComments(z8));
    expect(cb).not.toBeNull();
    expect(cb[1]).not.toMatch(/border|0 0 0 \d/);
  });
});
