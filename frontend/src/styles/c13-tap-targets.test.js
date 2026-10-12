// Круг 13: цели нажатия хлебных крошек и декоративная подпись логотипа.
// Находки аудитора: «Главная» 50×18 px и «обрезана многоточием» (область нажатия давал ::before внутри
// ссылки с overflow:hidden, он обрезался); подпись логотипа 4,5–5,5 px и стрелка 7 px считались мелким текстом.
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';

const here = dirname(fileURLToPath(import.meta.url));
const css = readFileSync(join(here, 'indicator-russia.css'), 'utf8');
const brand = readFileSync(join(here, '..', 'components', 'Brand.jsx'), 'utf8');

describe('цели нажатия крошек', () => {
  it('высоту до 44 px даёт padding внутри ссылки, а не ::before (его обрезает overflow:hidden)', () => {
    expect(css).not.toMatch(/\.fe-crumbs__link::before/);
    const rule = css.match(/@media \(pointer: coarse\), \(max-width: 1023px\) \{\s*\.fe-crumbs__link \{([^}]*)\}/);
    expect(rule, 'правило для касаний и узких экранов').toBeTruthy();
    const padding = rule[1].match(/padding:\s*(\d+)px/);
    expect(Number(padding[1]) * 2 + 18).toBeGreaterThanOrEqual(44);
    // отрицательный margin возвращает прежнюю высоту строки крошек
    expect(rule[1]).toMatch(new RegExp(`margin:\\s*-${padding[1]}px`));
  });
});

describe('подпись логотипа', () => {
  it('скрыта от вспомогательных технологий: у ссылки есть своя подпись, надпись — часть рисунка', () => {
    expect(brand).toMatch(/<small aria-hidden="true">ECONOMIC INTELLIGENCE<\/small>/);
  });
});
