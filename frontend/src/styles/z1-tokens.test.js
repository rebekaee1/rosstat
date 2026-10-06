import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';

const here = dirname(fileURLToPath(import.meta.url));
const tokens = readFileSync(join(here, 'z1-tokens.css'), 'utf8');
const indexCss = readFileSync(join(here, '..', 'index.css'), 'utf8');

// Имена из брифа раунда 2: остальные зоны подставляют их как var(--fe-…, запасное значение).
const REQUIRED = [
  '--fe-gold', '--fe-gold-soft', '--fe-gold-ink', '--fe-bg-warm', '--fe-dark-surface', '--fe-text-muted',
  '--fe-container-data', '--fe-container-wide', '--fe-container-text', '--fe-reveal-dur', '--fe-lift',
  '--fe-card-shadow', '--fe-glow-gold', '--fe-shimmer',
];

function declared(name) {
  return new RegExp(`^\\s*${name.replace(/[-]/g, '\\-')}\\s*:`, 'm').test(tokens);
}

describe('z1-tokens.css', () => {
  it.each(REQUIRED)('объявляет токен %s', (name) => {
    expect(declared(name)).toBe(true);
  });

  it('подключён из index.css сразу после tailwind', () => {
    expect(indexCss).toMatch(/@import "tailwindcss";\s*@import "\.\/styles\/z1-tokens\.css";/);
  });

  it('контейнер данных растёт ступенями 1280 → 1600 → 1760 → 1920, текст держится 760', () => {
    expect(tokens).toMatch(/--fe-container-data:\s*1280px/);
    expect(tokens).toMatch(/min-width:\s*1700px\)[^}]*--fe-container-data:\s*1600px/);
    expect(tokens).toMatch(/min-width:\s*1920px\)[^}]*--fe-container-data:\s*1760px/);
    expect(tokens).toMatch(/min-width:\s*2400px\)[^}]*--fe-container-data:\s*1920px/);
    expect(tokens).toMatch(/--fe-container-text:\s*760px/);
  });

  it('ширина оболочки равна ширине страниц данных, чтобы края шапки и контента совпадали', () => {
    expect(tokens).toMatch(/--fe-container-wide:\s*var\(--fe-container-data\)/);
  });

  it('словарь движения: 340 мс, ступень 60 мс, подъём 2 px, блик 1,6 с', () => {
    expect(tokens).toMatch(/--fe-reveal-dur:\s*340ms/);
    expect(tokens).toMatch(/--fe-reveal-step:\s*60ms/);
    expect(tokens).toMatch(/--fe-lift:\s*-2px/);
    expect(tokens).toMatch(/--fe-shimmer-dur:\s*1\.6s/);
    expect(tokens).toMatch(/--fe-line-draw-dur:\s*700ms/);
  });

  it('движение уважает prefers-reduced-motion', () => {
    expect(tokens).toMatch(/@media \(prefers-reduced-motion: reduce\)[\s\S]*\.fe-stagger/);
  });

  it('контейнерные правила обнулены :where(), чтобы страничные стили зон могли их переопределить', () => {
    expect(tokens).toMatch(/:where\(\.fe-data-page\.max-w-7xl/);
    expect(tokens).toMatch(/:where\(\.fe-data-page\.max-w-3xl\)\s*\{\s*max-width:\s*var\(--fe-box-text\)/);
  });

  it('мелкий произвольный текст Tailwind поднимается до 13 px, заглавные ярлыки до 12 px', () => {
    expect(tokens).toMatch(/text-\[10px\][\s\S]*font-size:\s*0\.8125rem/);
    expect(tokens).toMatch(/\.uppercase:not\([^)]*\)\s*\{\s*font-size:\s*0\.75rem/);
  });

  it('единица рядом с числом не меньше 12 px', () => {
    expect(tokens).toMatch(/\.fe-unit\s*\{[^}]*font-size:\s*max\(12px/);
  });
});

describe('z1-tokens.css: хрусталь без границ (R3)', () => {
  const GLASS = [
    '--fe-glass-l1', '--fe-glass-l1-sheen', '--fe-glass-l2', '--fe-glass-active', '--fe-blur-l1', '--fe-blur-l2',
    '--fe-inset-glint', '--fe-inset-glint-bottom', '--fe-float-shadow', '--fe-float-shadow-hover', '--fe-shadow-l2', '--fe-dark-glass',
  ];
  it.each(GLASS)('объявляет токен слоя %s', (name) => {
    expect(declared(name)).toBe(true);
  });

  it('blur L1 18 px, на телефоне 12 px; L2 12 px', () => {
    expect(tokens).toMatch(/--fe-blur-l1:\s*18px/);
    expect(tokens).toMatch(/max-width:\s*767px\)\s*\{\s*:root\s*\{\s*--fe-blur-l1:\s*12px/);
    expect(tokens).toMatch(/--fe-blur-l2:\s*12px/);
  });

  it('утилитарные классы стекла объявлены и описаны в шапке', () => {
    for (const cls of ['fe-glass', 'fe-glass-2', 'fe-glass-active', 'fe-glass-dark', 'fe-float', 'fe-divider']) {
      expect(tokens).toMatch(new RegExp(`\\.${cls}\\b`));
      expect(tokens.slice(0, tokens.indexOf(':root {'))).toContain(`.${cls} `);
    }
  });

  it('есть плотный запасной вариант без backdrop-filter', () => {
    expect(tokens).toMatch(/@supports not \(\(backdrop-filter: blur\(1px\)\)/);
  });

  it('стекло полупрозрачное: альфа L1 и --fe-glass не выше 0,6', () => {
    const l1 = /--fe-glass-l1:\s*rgba\(255,\s*255,\s*255,\s*([0-9.]+)\)/.exec(tokens);
    expect(Number(l1[1])).toBeLessThanOrEqual(0.6);
    const glass = /--fe-glass:\s*linear-gradient\(130deg,\s*rgba\(255,\s*255,\s*255,\s*([0-9.]+)\)/.exec(indexCss);
    expect(Number(glass[1])).toBeLessThanOrEqual(0.6);
  });

  it('кромка и кольцо удалены: --fe-panel-edge нет, .fe-panel без top-center 1px слоя', () => {
    expect(tokens + indexCss).not.toMatch(/--fe-panel-edge/);
    expect(indexCss).not.toMatch(/top center \/ 100% 1px/);
  });
});

describe('z1-tokens.css: ширина страниц данных (DS1, круг 4)', () => {
  // Страница данных держит gutter padding-ом (:where(.fe-data-page), .fe-gutter), поэтому её max-width обязан быть
  // коробкой (--fe-box-*, с полями), а не шириной контента (--fe-container-*): иначе поля считаются дважды
  // (на 1440 было 112–1328 вместо 80–1360).
  const here = dirname(fileURLToPath(import.meta.url));
  const SKIP = new Set(['z1-tokens.css', 'z2-shell.css', 'k1-scene.css', 'z7-compare.css', 'k3-shell.css']);
  it('зоны не задают max-width страницы через --fe-container-data/-wide', async () => {
    const { readdirSync } = await import('node:fs');
    const bad = [];
    for (const f of readdirSync(here).filter((n) => n.endsWith('.css') && !SKIP.has(n))) {
      const text = readFileSync(join(here, f), 'utf8');
      if (/max-width\s*:\s*(?:min\(|max\()?var\(--fe-container-(?:data|wide)/.test(text)) bad.push(f);
    }
    expect(bad).toEqual([]);
  });

  it('коробка данных = контент + 2 поля: 1280 + 64 на 1440 даёт контент 80–1360', () => {
    expect(tokens).toMatch(/--fe-box-data:\s*calc\(var\(--fe-container-data\) \+ 2 \* var\(--fe-gutter\)\)/);
    expect(tokens).toMatch(/:where\(\.fe-data-page\.max-w-7xl[^)]*\)\s*\{\s*max-width:\s*var\(--fe-box-data\)/);
  });
});

describe('index.css: базовая палитра и типографика раунда 2', () => {
  it('фон страницы холодно-нейтральный (круг 6), а вторичный текст темнее прежнего', () => {
    expect(indexCss).toMatch(/--color-obsidian:\s*#F4F5F7/);
    expect(indexCss).toMatch(/--color-text-secondary:\s*#4B596F/);
    expect(indexCss).not.toMatch(/--color-obsidian:\s*#EEF0F4/);
  });

  it('text-xs стал 13 px, корневой размер плавно растёт до 18 px к 1920', () => {
    expect(indexCss).toMatch(/--text-xs:\s*0\.8125rem/);
    expect(indexCss).toMatch(/font-size:\s*clamp\(16px, calc\(16px \+ \(100vw - 1600px\) \* 0\.00625\), 18px\)/);
  });

  it('home page shell и .fe-data-page берут ширину из токенов', () => {
    expect(indexCss).toMatch(/\.fe-page-shell \{[^}]*max-width:\s*var\(--fe-box-wide/);
  });
});

// Круг 6, зона P: палитра «не жёлтая» (принципы владельца 2 и 3). Страж держит токены и список «игровых» приёмов, которые сняты.
describe('круг 6: холодная палитра, графит и синий, золото тонким акцентом', () => {
  const read = (name) => readFileSync(join(here, name), 'utf8').replace(/\/\*[\s\S]*?\*\//g, '');
  const css = Object.fromEntries(['k2-brand.css', 'k3-shell.css', 'k4-charts.css', 'k6-country.css', 'k7-home.css', 'k8-tools.css'].map((n) => [n, read(n)]));
  const tok = tokens.replace(/\/\*[\s\S]*?\*\//g, '');

  it('фон — холодный #F4F5F7 / #EEF1F5; активное состояние — графит со светлым текстом, а не золото', () => {
    expect(tok).toMatch(/--fe-bg-warm:\s*#F4F5F7/);
    expect(tok).toMatch(/--fe-bg-warm-2:\s*#EEF1F5/);
    expect(tok).toMatch(/--fe-glass-active:\s*linear-gradient\(135deg, #2A3550, #1E2638\)/);
    expect(tok).toMatch(/--fe-on-active:\s*#F3EFE6/);
    expect(tok).toMatch(/--fe-on-gold:\s*var\(--fe-on-active\)/);
    expect(tok).toMatch(/--fe-glass-primary:\s*linear-gradient\(135deg, #2C4A8A, #1E3A6E\)/);
  });

  it('цифры-герои графитовые; золотой градиент только у класса .fe-gold-text', () => {
    expect(tok).toMatch(/--fe-gold-gradient-text:\s*linear-gradient\(120deg, #1E2638/);
    expect(tok).toMatch(/\.fe-gold-text\s*\{\s*background:\s*var\(--fe-gold-gradient-true\)/);
    expect(css['k7-home.css']).toMatch(/--k7-gold-text:\s*linear-gradient\(170deg, #2A3550/);
    expect(css['k6-country.css']).toMatch(/--k6-engrave:\s*linear-gradient\(175deg, #1E2638/);
  });

  it('золото сцены — единственное тёплое пятно (альфа ≤ .18), остальные сияния холодные', () => {
    expect(tok).toMatch(/--fe-glow-gold-bg:\s*rgba\(201, 162, 77, 0\.1\)/);
    expect(tok).toMatch(/--fe-glow-ice-bg:\s*rgba\(196, 214, 238/);
  });

  it('«игровое» снято: бусины графика, камни, медали, гемма дока, флаги-капли, лампы плиток', () => {
    // бусина на конце линии: плоская точка 6 px, грани и блик скрыты
    expect(css['k4-charts.css']).toMatch(/\.k4-lastpoint > circle:nth-of-type\(2\)\s*\{\s*r:\s*3px/);
    expect(css['k4-charts.css']).toMatch(/\.k4-lastpoint > path,\s*\.k4-lastpoint > circle:nth-of-type\(3\)\s*\{\s*display:\s*none/);
    // легенда карты: тонкая шкала 4 px, без блика и бусин-делений
    expect(css['k4-charts.css']).toMatch(/\.k4-tube\s*\{[^}]*height:\s*4px/);
    expect(css['k4-charts.css']).toMatch(/\.k4-tube__beads\s*\{\s*display:\s*none/);
    // медаль — цифра в графитовом круге; гранёных conic-градиентов нет
    expect(css['k2-brand.css']).toMatch(/\.fe-medal\s*\{[^}]*border-radius:\s*50%[^}]*#2A3550/);
    expect(css['k6-country.css']).not.toContain('conic-gradient');
    // флаг без блика и цветного пятна
    expect(css['k2-brand.css']).toMatch(/\.fe-flag--glass::before\s*\{\s*content:\s*none/);
    expect(css['k2-brand.css']).toMatch(/\.fe-flag__drop::after\s*\{\s*content:\s*none/);
    // док: геммы нет, активный пункт — графитовая плашка
    expect(css['k3-shell.css']).not.toMatch(/fe-dock__gem|fe-mega__tile--gem\s*\{/);
    expect(css['k3-shell.css']).toMatch(/\.fe-dock__item\.is-active \.fe-dock__icon\s*\{\s*background:\s*var\(--fe-glass-active\)/);
    // лампы плиток «Мир сейчас» нейтральные: ни одной золотой и розовой
    expect(css['k7-home.css']).toMatch(/--k7-lamp-gold:\s*rgb\(196 210 234/);
    expect(css['k7-home.css']).not.toMatch(/--k7-lamp-(gold|rose|mint):\s*rgb\((233|244|172) /);
    // у кнопок, чипов и ручек нет радиального глянца «circle at 3x%»
    for (const name of ['k3-shell.css', 'k4-charts.css', 'k7-home.css', 'k8-tools.css']) {
      expect(css[name], name).not.toMatch(/radial-gradient\(circle at 3\d%/);
    }
  });

  it('золотая заливка — только CTA регистрации (.fe-cta-gold и кнопка в шапке), остальные primary синие', () => {
    expect(indexCss).toMatch(/\.fe-btn--primary\s*\{[^}]*var\(--fe-glass-primary\)/);
    expect(css['k3-shell.css']).toMatch(/nav\.fe-navbar--glass \.fe-button-primary,[\s\S]*?background:\s*var\(--fe-glass-gold\)/);
    expect(css['k8-tools.css']).not.toMatch(/glass-gold/);
  });
});
