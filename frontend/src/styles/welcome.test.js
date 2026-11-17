import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';
import { MESSAGES } from '../i18n/messages';

const read = (rel) => readFileSync(fileURLToPath(new URL(rel, import.meta.url)), 'utf8');
const css = read('./welcome.css').replace(/\/\*[\s\S]*?\*\//g, '');
const art = read('../components/welcome/WelcomeArt.jsx');

/** Страж приветственного экрана: принципы владельца и правила движения (docs/design-system.md). */
describe('welcome.css', () => {
  it('без рамок, колец и размытия', () => {
    expect(css).not.toMatch(/\bborder(-(top|right|bottom|left))?\s*:/);
    expect(css).not.toMatch(/backdrop-filter/);
    expect(css).not.toMatch(/box-shadow:[^;]*\b0 0 0 [12]px/);
    // Обводка только у фокуса с клавиатуры.
    for (const m of css.matchAll(/([^{}]+)\{[^{}]*outline:\s*\d[^;]*;[^{}]*\}/g)) {
      expect(m[1]).toMatch(/:focus-visible/);
    }
  });

  it('в кадрах анимации меняются только transform и прозрачность', () => {
    const frames = [...css.matchAll(/@keyframes\s+[\w-]+\s*\{((?:[^{}]*\{[^{}]*\})*)\s*\}/g)];
    expect(frames.length).toBeGreaterThan(8);
    for (const [, body] of frames) {
      for (const [, prop] of body.matchAll(/([a-z-]+)\s*:/g)) {
        expect(['transform', 'opacity', 'fill-opacity']).toContain(prop);
      }
    }
    expect(css).not.toMatch(/transition:[^;]*\b(width|height|top|left|margin|padding|filter)\b/);
  });

  it('«меньше движения» гасит всё: и системная настройка, и data-wl-motion="off"', () => {
    expect(css).toMatch(/@media \(prefers-reduced-motion: reduce\)\s*\{\s*\.fe-wl, \.fe-wl \*, \.fe-wl \*::before, \.fe-wl \*::after\s*\{\s*animation: none !important;\s*transition: none !important;/);
    expect(css).toMatch(/\.fe-wl\[data-wl-motion='off'\] \*,[\s\S]*?animation: none !important;/);
    // Фоновое плавание только в полном режиме.
    // Бесконечные циклы: фоновый свет только в полном режиме; маленькая живая точка сцены — везде, кроме «меньше движения».
    for (const m of css.matchAll(/([^{}]+)\{[^{}]*infinite[^{}]*\}/g)) expect(m[1]).toMatch(/\[data-wl-motion='full'\]|:not\(\[data-wl-motion='off'\]\)/);
    // Целевые кнопки подпрыгивают конечное число раз и успокаиваются сами.
    for (const m of css.matchAll(/animation: fe-wl-(?:hop|hop-soft|nod|under) [^;]*;/g)) expect(m[0]).not.toMatch(/infinite/);
    for (const m of css.matchAll(/([^{}]+)\{[^{}]*animation: fe-wl-(?:hop|hop-soft|nod|under) [^{}]*\}/g)) expect(m[1]).toContain(":not([data-wl-motion='off'])");
  });

  it('одно тёплое пятно не ярче .18, золото только чертой и у кнопки аккаунта', () => {
    const warm = [...css.matchAll(/rgba\(236, 214, 156, ([\d.]+)\)/g)].map((m) => Number(m[1]));
    expect(warm.length).toBeGreaterThan(0);
    expect(Math.max(...warm)).toBeLessThanOrEqual(0.18);
    // Золотая заливка кнопки — одна: «Создать аккаунт».
    const goldFills = [...css.matchAll(/([^{}]+)\{[^{}]*background:[^;{}]*#E3C273[^{}]*\}/g)].map((m) => m[1].trim());
    expect(goldFills).toEqual(['.fe-wl__btn--gold']);
  });

  it('картинка F — кадр 2× из реестра бренда; высота показа не больше половины кадра (1519 px)', () => {
    expect(css).toContain("url('/brand/emblem-f-2x.webp')");
    const caps = [...css.matchAll(/--wl-hfh: min\([\d.]+d?vh, (\d+)px\)/g)].map((m) => Number(m[1]));
    expect(caps.length).toBeGreaterThan(2);
    // На шагах F увеличена масштабом до 1,62: там она фон с прозрачностью .2, резкость кадра не видна.
    expect(Math.max(...caps)).toBeLessThanOrEqual(760);
  });

  it('тёмная сцена: сапфир палитры сайта, размытия и светлого фона нет', () => {
    expect(css).toMatch(/\.fe-wl \{[^}]*background: radial-gradient\([^;]*#0A1227/);
    expect(css).not.toContain('#F4F5F7');
    expect(css).toMatch(/html\[data-fe-welcome='open'\], html\[data-fe-welcome='open'\] body \{ background: #0A1227 !important; \}/);
  });
});

describe('сцены и тексты приветственного экрана', () => {
  it('в сценах нет выдуманных чисел: ни одной цифры в подписях', () => {
    const texts = [...art.matchAll(/<text[^>]*>([^<{]*)</g)].map((m) => m[1].trim()).filter(Boolean);
    for (const text of texts) expect(text).not.toMatch(/\d/);
    for (const locale of ['ru', 'en']) {
      for (const key of ['welcome.find.word', 'welcome.account.saved', 'welcome.telegram.subscribe', 'welcome.scene.indicator', 'welcome.scene.home', 'welcome.scene.peer', 'welcome.scene.daily', 'welcome.scene.saved1', 'welcome.scene.saved2']) {
        expect(MESSAGES[locale][key]).not.toMatch(/\d/);
      }
    }
  });

  it('тексты шагов короткие и без служебных слов', () => {
    for (const locale of ['ru', 'en']) {
      const dict = MESSAGES[locale];
      for (const step of ['hello', 'find', 'fresh', 'telegram', 'compare', 'account']) {
        expect(dict[`welcome.${step}.title`].length).toBeLessThanOrEqual(40);
        const body = dict[`welcome.${step}.body`];
        if (body) expect(body.length).toBeLessThanOrEqual(150);
      }
      const all = Object.entries(dict).filter(([k]) => k.startsWith('welcome.')).map(([, v]) => v).join(' ');
      expect(all).not.toMatch(/API|ETL|парсер|parser|localStorage|cookie|SSR|JSON/i);
      // Прогноз на экране не обещан диапазоном, рассылка по почте не обещана вовсе.
      expect(all).not.toMatch(/диапазон|коридор|range|письм|e-?mail|почт/i);
    }
  });
});
