// Страж зоны B круга 11: кабинет и кнопки действия без рамок, колец, размытия и золотой заливки.
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';

const here = dirname(fileURLToPath(import.meta.url));
const css = readFileSync(join(here, 'c11b-cabinet.css'), 'utf8').replace(/\/\*[\s\S]*?\*\//g, '');

describe('c11b-cabinet.css', () => {
  it('нет рамок и колец', () => {
    expect(css).not.toMatch(/(^|[;\s{])border(-(top|bottom|left|right))?\s*:\s*[0-9.]+(px|rem)?\s*(solid|dashed|dotted)/);
    expect(css).not.toMatch(/box-shadow\s*:[^;}]*0\s+0\s+0\s+[12](\.\d+)?px/);
  });

  it('нет нового размытия и золотой заливки', () => {
    expect(css).not.toMatch(/backdrop-filter/);
    // Золото разрешено только в контуре фокуса с клавиатуры (исключение 1 раздела 4 дизайн-системы).
    const withoutFocus = css.replace(/[^{}]*:focus-visible[^{}]*\{[^{}]*\}/g, '');
    expect(withoutFocus).not.toMatch(/#(c9a24d|b08a3e|ad8a48)/i);
    expect(css).not.toMatch(/--fe-glass-gold|fe-cta-gold/);
  });

  it('анимирует только transform и opacity', () => {
    const transitions = [...css.matchAll(/transition\s*:\s*([^;]+);/g)].map((m) => m[1]);
    for (const value of transitions) {
      expect(value).toMatch(/^(none|transform|opacity)\b/);
    }
    for (const m of css.matchAll(/@keyframes[^{]+\{([\s\S]*?)\}\s*\}/g)) {
      expect(m[1]).not.toMatch(/\b(width|height|top|left|margin|padding)\s*:/);
    }
  });

  it('движение гасится при reduced-motion', () => {
    expect(css).toMatch(/prefers-reduced-motion:\s*reduce/);
    expect(css).toMatch(/data-fe-motion='off'/);
  });
});
