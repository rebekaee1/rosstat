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

describe('index.css: базовая палитра и типографика раунда 2', () => {
  it('фон страницы тёплый, а вторичный текст темнее прежнего', () => {
    expect(indexCss).toMatch(/--color-obsidian:\s*#F6F2EA/);
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
