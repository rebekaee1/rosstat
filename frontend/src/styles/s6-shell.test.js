import { describe, expect, it } from 'vitest';
import { readdirSync, readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

// Круг 6, зона S (шапка, лента, док, cookie): страж «контент не под шапкой» и «строгая оболочка» (принципы владельца 2 и 3).
const here = dirname(fileURLToPath(import.meta.url));
const strip = (text) => text.replace(/\/\*[\s\S]*?\*\//g, '');
const read = (name) => strip(readFileSync(join(here, name), 'utf8'));
const k3 = read('k3-shell.css');
const z2 = read('z2-shell.css');

describe('круг 6 S: контент не уходит под шапку', () => {
  it('html получает scroll-padding-top = шапка + лента + 12 px из переменных, которые ставят Navbar и LiveTicker', () => {
    expect(k3).toMatch(/html\s*\{\s*scroll-padding-top:\s*calc\(var\(--fe-header-h\) \+ var\(--fe-ticker-h\) \+ 12px\)/);
    expect(k3).toMatch(/--fe-ticker-h:\s*var\(--k3-ticker-h\)/);
    expect(k3).toMatch(/--fe-header-h:\s*76px/);
  });

  it('у секций нет собственного scroll-margin-top больше нуля: он складывался бы с общим запасом', () => {
    const bad = [];
    for (const f of readdirSync(here).filter((n) => n.endsWith('.css'))) {
      for (const m of read(f).matchAll(/scroll-margin-top:\s*([^;}]+)/g)) {
        if (!/^0(px)?$/.test(m[1].trim())) bad.push(`${f}: ${m[1].trim()}`);
      }
    }
    expect(bad).toEqual([]);
  });

  it('сжатая шапка телефона — 52 px, стекло плотнее .8', () => {
    expect(k3).toMatch(/nav\.fe-navbar--glass\[data-compact='true'\]\s*\{[^}]*height:\s*52px/);
    expect(k3).toMatch(/nav\.fe-navbar--glass\s*\{\s*padding-block:\s*8px;\s*background:\s*rgb\(var\(--k3-paper\) \/ 0\.84\)/);
  });
});

describe('круг 6 S: строгая оболочка', () => {
  it('значки шапки плоские: без подложек-кружков, штрих 1,5 px', () => {
    expect(z2).toMatch(/\.fe-nav-round\s*\{[^}]*background:\s*transparent/);
    expect(k3).toMatch(/\.fe-nav-cluster\s*\{[^}]*background:\s*none;[^}]*box-shadow:\s*none/);
    expect(k3).toMatch(/nav\.fe-navbar svg\.lucide\s*\{\s*stroke-width:\s*1\.5/);
  });

  it('активный пункт шапки — графитовая черта 2 px, не золотая капля', () => {
    expect(z2).toMatch(/a\.fe-nav-link::after,[\s\S]*?height:\s*2px;[\s\S]*?background:\s*var\(--fe-ink/);
    expect(z2).not.toMatch(/radial-gradient\(closest-side, rgba\(201, 162, 77/);
  });

  it('док (круг 8, S4) — светлое стекло .9 с размытием, графитовые подписи, активный пункт — графит и линия сверху', () => {
    expect(k3).toMatch(/--k3-dock-bg:\s*rgb\(var\(--k3-paper\) \/ 0\.9\)/);
    expect(k3).toMatch(/--k3-dock-ink:\s*#1e2638/);
    expect(k3).toMatch(/\.fe-dock\s*\{[^}]*width:\s*fit-content/);
    expect(k3).toMatch(/\.fe-dock__item\.is-active::before\s*\{[^}]*top:\s*0;[^}]*height:\s*2px/);
    expect(k3).not.toMatch(/\.fe-dock__item\.is-active \.fe-dock__icon\s*\{/);
  });

  it('лента: разделитель — точка 3 px, рост/падение — зелёная и серо-синяя точки без свечения, «Все валюты» графитом', () => {
    expect(k3).toMatch(/\.fe-ticker__cell \+ \.fe-ticker__cell::before\s*\{[^}]*width:\s*3px;\s*height:\s*3px/);
    expect(k3).toMatch(/--k3-down:\s*#6b7c99/);
    expect(k3).not.toMatch(/glow|drop-shadow\(0 0 4px rgba\(201/);
    expect(k3).toMatch(/\.fe-ticker \.fe-ticker__all\s*\{\s*color:\s*var\(--fe-ink/);
  });

  it('cookie: кнопка «Принять» графитовая (--fe-glass-active), золота нет', () => {
    expect(k3).toMatch(/\.fe-cookie-compact__actions \.fe-cookie-accept\s*\{\s*background:\s*var\(--fe-glass-active\)/);
  });

  it('в оболочке нет золотых значений: ни #C9A24D, ни rgba(201, 162, 77) вне единственной золотой CTA', () => {
    const noCta = k3.replace(/nav\.fe-navbar--glass \.fe-button-primary,[\s\S]*?\n\}\n/g, '');
    expect(noCta).not.toMatch(/#c9a24d|rgba\(201, 162, 77/i);
  });
});


// Круг 8, зона Z0: переменные оболочки, на которые опираются остальные зоны, и общие правила S1-S9.
const z1 = read('z1-tokens.css');
const k1 = read('k1-scene.css');
const k2 = read('k2-brand.css');

describe('круг 8 Z0: переменные оболочки для всех зон', () => {
  it('объявлены запасные значения --fe-dock-h, --fe-cookie-h, --fe-shell-top, --fe-page-top, --fe-bottom-clear', () => {
    expect(z1).toMatch(/--fe-dock-h:\s*0px/);
    expect(z1).toMatch(/--fe-cookie-h:\s*0px/);
    expect(z1).toMatch(/--fe-shell-top:\s*calc\(var\(--fe-ticker-h, 40px\) \+ var\(--fe-header-h, 76px\)\)/);
    expect(z1).toMatch(/--fe-page-top:\s*calc\(var\(--fe-shell-top\) \+ 16px\)/);
    expect(z1).toMatch(/--fe-bottom-clear:\s*calc\(var\(--fe-dock-h\) \+ var\(--fe-cookie-h\)/);
  });

  it('компьютер: main отступает на низ шапки + 16 px минус 96 px страницы (содержимое не под шапкой), страницы pt-20 выровнены', () => {
    expect(k3).toMatch(/main#main-content\s*\{\s*padding-top:\s*max\(4px, calc\(var\(--fe-page-top\) - 96px\)\)/);
    expect(k3).toMatch(/main#main-content > \.fe-data-page\.pt-20\s*\{\s*padding-top:\s*6rem/);
  });

  it('шапка при прокрутке плотнее .9 суммарно (слой .8 поверх .66), на телефоне .6 поверх .84', () => {
    expect(k3).toMatch(/nav\.fe-navbar--glass::after\s*\{[^}]*background:\s*rgb\(var\(--k3-paper\) \/ 0\.8\)/);
    expect(k3).toMatch(/nav\.fe-navbar--glass::after\s*\{\s*background:\s*rgb\(var\(--k3-paper\) \/ 0\.6\)/);
  });

  it('док не добавляет запас в main (он один раз в подвале), подвал считает cookie и док', () => {
    expect(k3).toMatch(/main#main-content\s*\{\s*padding-bottom:\s*0;/);
    expect(z2).toMatch(/footer\.fe-footer\s*\{\s*padding-bottom:\s*calc\(var\(--fe-cookie-h, 0px\) \+ var\(--fe-dock-reserve, 0px\)\)/);
  });

  it('переход перед подвалом не выше 80 px', () => {
    expect(k2).toMatch(/footer\.fe-footer\.fe-k2-footer\s*\{\s*margin-top:\s*80px/);
    expect(k2).toMatch(/top:\s*-80px;[\s\S]*?height:\s*80px/);
  });

  it('«Все валюты» — плотный блок (.97) с затуханием слева; лента на телефоне 32 px', () => {
    expect(z2).toMatch(/\.fe-ticker__all\s*\{[^}]*background-color:\s*rgb\(var\(--k3-paper, 250 252 255\) \/ 0\.97\)/);
    expect(k3).toMatch(/:root\s*\{\s*--k3-ticker-h:\s*32px/);
  });

  it('cookie: на виду «Хорошо» и «Только необходимые», плашка прячется, пока открыта шторка меню', () => {
    expect(z2).toMatch(/\.fe-cookie-necessary/);
    expect(k3).toMatch(/body:has\(\.fe-bsheet-scrim\) \.fe-cookie-wrap\s*\{\s*visibility:\s*hidden/);
  });

  it('меню: у кнопок и ссылок один flex-вид; на планшете группы идут колонками браузера', () => {
    expect(k3).toMatch(/\.fe-mnav-link\s*\{[^}]*display:\s*flex/);
    expect(k3).toMatch(/\.fe-mnav-columns\s*\{\s*display:\s*block;\s*column-count:\s*2/);
  });

  it('стеклянная F на страницах данных тише .18 и ниже; панели с таблицами не прозрачнее .9', () => {
    const op = k1.match(/\.fe-scene__f\[data-fe-f-mode="all"\]\.is-ready\s*\{\s*opacity:\s*var\(--fe-scene-f-data-opacity, ([0-9.]+)\)/);
    expect(op).toBeTruthy();
    expect(Number(op[1])).toBeLessThanOrEqual(0.18);
    expect(z1).toMatch(/:has\(table, \[role='table'\][^)]*\)\s*\{\s*--fe-glass-l1:\s*rgba\(255, 255, 255, 0\.9\)/);
  });

  it('новых blur-слоёв оболочка не добавила: backdrop-filter только у шапки, ленты, дока, шторки, cookie и подвала-стекла', () => {
    const files = ['k3-shell.css', 'z2-shell.css'];
    const count = files.reduce((n, f) => n + (read(f).match(/backdrop-filter:\s*blur/g) || []).length, 0);
    // 19 вхождений в двух файлах было до круга 8 (часть из них взаимоисключающие медиазапросы): число не растёт; бюджет кадра: docs/design-system.md, раздел 5
    expect(count).toBeLessThanOrEqual(19);
  });
});
