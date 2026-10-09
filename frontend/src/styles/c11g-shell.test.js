import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

// Круг 11, зона G (оболочка и телефон): страж новых правил. Читает исходники, как остальные стражи styles/*.test.js.
const here = dirname(fileURLToPath(import.meta.url));
const src = join(here, '..');
const strip = (text) => text.replace(/\/\*[\s\S]*?\*\//g, '');
const css = (name) => strip(readFileSync(join(here, name), 'utf8'));
const index = strip(readFileSync(join(src, 'index.css'), 'utf8'));
const jsx = (name) => readFileSync(join(src, name), 'utf8');
const k3 = css('k3-shell.css');
const k1 = css('k1-scene.css');
const k2 = css('k2-brand.css');
const z1 = css('z1-tokens.css');
const z2 = css('z2-shell.css');

describe('круг 11 G: нижняя панель телефона (U29)', () => {
  it('ячейки не уже 64 px и между ними зазор; фон плотный (.95), в запасе .98', () => {
    expect(k3).toMatch(/\.fe-dock__list\s*\{[^}]*grid-template-columns:\s*repeat\(5, minmax\(64px, 1fr\)\);[^}]*column-gap:\s*2px/);
    expect(k3).toMatch(/--k3-dock-bg:\s*rgb\(var\(--k3-paper\) \/ 0\.95\)/);
    expect(k3).toMatch(/@supports not[\s\S]*?\.fe-dock\s*\{\s*--k3-dock-bg:\s*rgb\(var\(--k3-paper\) \/ 0\.98\)/);
  });

  it('панель прячется при вводе и на бегунке (хук подключён), анимируются только transform и opacity', () => {
    const dock = jsx('components/MobileDock.jsx');
    expect(dock).toMatch(/useDockSuppressed\(\)/);
    expect(dock).toMatch(/!suppressed/);
    const block = k3.match(/\.fe-dock\s*\{[^}]*\}/)[0];
    expect(block).toMatch(/transition:\s*transform[^;]*opacity/);
    expect(block).not.toMatch(/transition:[^;]*(height|width|top|bottom|left|right|blur)/);
  });

  it('якоря и фокус останавливаются выше панели с учётом выреза iPhone', () => {
    expect(k3).toMatch(/scroll-padding-bottom:\s*calc\([^;]*env\(safe-area-inset-bottom, 0px\)\)/);
  });
});

describe('круг 11 G: общие примитивы оболочки', () => {
  it('токены --fe-tap, --fe-pending-delay, --fe-avatar-size объявлены в :root', () => {
    expect(z1).toMatch(/--fe-tap:\s*44px/);
    expect(z1).toMatch(/--fe-pending-delay:\s*140ms/);
    expect(z1).toMatch(/--fe-avatar-size:\s*40px/);
  });

  it('аватар: графит как у активного чипа, золота и рамок нет, размеры sm/lg', () => {
    const block = k3.match(/\.fe-avatar\s*\{[^}]*\}/)[0];
    expect(block).toMatch(/background:\s*var\(--fe-glass-active\)/);
    expect(block).not.toMatch(/champagne|gold|#c9a|#b08|(^|[\s;])border\s*:/i);
    expect(k3).toMatch(/\.fe-avatar--sm\s*\{\s*--fe-avatar-size:\s*26px/);
    expect(k3).toMatch(/\.fe-avatar--lg\s*\{\s*--fe-avatar-size:\s*52px/);
    expect(k3).toMatch(/a\.fe-nav-account[\s\S]*?min-height:\s*44px/);
  });

  it('ожидание кнопки и чипа: кольцо поверх подписи, проявляется с задержкой, крутится только transform, в reduced-motion медленно', () => {
    expect(index).toMatch(/\.fe-chip\[aria-busy='true'\]\s*\{\s*position:\s*relative;\s*cursor:\s*progress/);
    const ring = index.match(/\.fe-chip__spinner,[^{]*\{[^}]*\}/)[0];
    expect(ring).toMatch(/animation:\s*fe-spin 0\.7s linear infinite,\s*fe-pending-in 0\.16s ease var\(--fe-pending-delay, 140ms\) both/);
    expect(ring).not.toMatch(/(^|[\s;])border\s*:|border-(top|left|right|bottom|width|color|style)|backdrop-filter/);
    expect(index).toMatch(/@media \(prefers-reduced-motion: reduce\)[\s\S]*?\.fe-chip__spinner[\s\S]*?animation-duration:\s*2\.4s/);
  });

  it('Button и Chip принимают pending, Chip не выкрасил кольцо золотом', () => {
    expect(jsx('components/Button.jsx')).toMatch(/pending = false/);
    expect(jsx('components/Chip.jsx')).toMatch(/pending = false/);
    expect(index).not.toMatch(/\.fe-chip__spinner[^}]*champagne/);
  });

  it('плотный фон диалога и меню «Скачать» (--fe-pop-bg, .97), не .8', () => {
    expect(index).toMatch(/\.fe-dialog-panel\s*\{\s*background:\s*var\(--fe-glass-l1-sheen\), var\(--fe-pop-bg, var\(--fe-nav-surface\)\)/);
  });
});

describe('круг 11 G: шапка, подвал, ссылка «к содержимому»', () => {
  it('шапка при прокрутке плотнее: слой .88 на компьютере и .7 на телефоне', () => {
    expect(k3).toMatch(/nav\.fe-navbar--glass::after\s*\{[^}]*background:\s*rgb\(var\(--k3-paper\) \/ 0\.88\)/);
    expect(k3).toMatch(/nav\.fe-navbar--glass::after\s*\{\s*background:\s*rgb\(var\(--k3-paper\) \/ 0\.7\)/);
  });

  it('ссылка «к содержимому» остаётся за краем окна, пока не нажат Tab', () => {
    expect(index).toMatch(/html\[data-fe-pointer\] \.fe-skip-link:focus-visible\s*\{\s*transform:\s*translateY\(/);
    expect(jsx('components/SkipLink.jsx')).toMatch(/data-fe-pointer/);
  });

  it('мелкий текст подвала светлее и не мельче 13 px', () => {
    expect(k2).toMatch(/\.fe-foot-requisites p\s*\{\s*color:\s*#D3D9E8;\s*font-size:\s*13px/);
    expect(k2).toMatch(/--color-text-tertiary:\s*#C6CEDF/);
  });

  it('значок языка темнее фона шапки, подсветка пункта «Инструменты» есть', () => {
    expect(k3).toMatch(/\.fe-locale-flag\s*\{\s*background:\s*rgb\(30 38 56 \/ 0\.1\)/);
    expect(z2).toMatch(/\.fe-nav-tools-btn\[data-active='true'\]::after/);
  });
});

describe('круг 11 G: сцена и крестик установки', () => {
  it('на планшете 768-1023 px стеклянная F ниже и меньше (не больше 520 px)', () => {
    expect(k1).toMatch(/@media \(min-width: 768px\) and \(max-width: 1023px\)\s*\{\s*\.fe-scene__f\s*\{[^}]*height:\s*min\(42vh, 520px\)/);
  });

  it('крестик карточки установки 44 × 44 pt на любом устройстве', () => {
    const card = jsx('components/PwaInstallCard.jsx');
    const closes = card.match(/aria-label=\{t\('common\.close'\)\}[\s\S]*?className=\{cn\([^)]*\)\}/g) || [];
    expect(closes.length).toBe(2);
    for (const block of closes) expect(block).toMatch(/h-11 w-11/);
  });
});
