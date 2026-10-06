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

  it('док — графитовое стекло .72 с размытием, активный пункт — светлый текст и линия сверху', () => {
    expect(k3).toMatch(/--k3-dock-bg:\s*rgba\(30, 38, 56, 0\.72\)/);
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
