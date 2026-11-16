import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';
import { MESSAGES } from '../i18n/messages';

const read = (rel) => readFileSync(fileURLToPath(new URL(rel, import.meta.url)), 'utf8');
const css = read('./welcome.css').replace(/\/\*[\s\S]*?\*\//g, '');
const screenSrc = read('../components/welcome/WelcomeScreen.jsx');
const chartSrc = read('../components/welcome/WelcomeChart.jsx');

/** Страж приветственного экрана: принципы владельца и то, от чего третья версия отказалась (docs/design-system.md). */
describe('welcome.css', () => {
  it('без рамок, колец и размытия', () => {
    expect(css).not.toMatch(/\bborder(-(top|right|bottom|left))?\s*:/);
    expect(css).not.toMatch(/backdrop-filter/);
    expect(css).not.toMatch(/box-shadow:[^;]*\b0 0 0 \d/);
    // Обводка только у фокуса с клавиатуры.
    for (const m of css.matchAll(/([^{}]+)\{[^{}]*outline:\s*\d[^;]*;[^{}]*\}/g)) {
      expect(m[1]).toMatch(/:focus-visible/);
    }
  });

  it('движение — только проявление и один проход линии; слова не двигаются', () => {
    const frames = [...css.matchAll(/@keyframes\s+[\w-]+\s*\{((?:[^{}]*\{[^{}]*\})*)\s*\}/g)];
    expect(frames.length).toBeGreaterThan(2);
    for (const [, body] of frames) {
      for (const [, prop] of body.matchAll(/([a-z-]+)\s*:/g)) expect(['opacity', 'clip-path']).toContain(prop);
    }
    // Ни один текстовый блок не получает transform в анимации или переходе.
    expect(css).not.toMatch(/\.fe-wl3__(copy|phrase|body|label|caption|question)[^{}]*\{[^{}]*[^-]transform\s*:/);
    expect(css).not.toMatch(/infinite/);
    expect(css).not.toMatch(/cubic-bezier\([^)]*1\.[0-9]/); // без упругих перелётов
  });

  it('«меньше движения» гасит всё: и системная настройка, и data-wl-motion="off"', () => {
    expect(css).toMatch(/@media \(prefers-reduced-motion: reduce\)\s*\{\s*\.fe-wl3, \.fe-wl3 \*, \.fe-wl3 \*::before\s*\{\s*animation: none !important;\s*transition: none !important;/);
    expect(css).toMatch(/\.fe-wl3\[data-wl-motion='off'\] \*,[\s\S]*?animation: none !important;/);
  });

  it('палитра сайта: холодный светлый фон, графит, глубокий синий; золото только у «вашей» точки и фокуса', () => {
    expect(css).toMatch(/--wl-bg: #F4F5F7/);
    const gold = [...css.matchAll(/([^{}]+)\{[^{}]*(?:var\(--wl-gold\)|#B08A3E|#8A6A2A)[^{}]*\}/g)].map((m) => m[1].trim());
    for (const selector of gold) expect(selector).toMatch(/data-mode='account'|focus-visible|^\.fe-wl3$/);
    // Главное действие — графит, без градиентов и цветных свечений.
    expect(css).toMatch(/\.fe-wl3__go \{[^}]*background: var\(--wl-ink\);/);
    expect(css).not.toMatch(/\.fe-wl3__go \{[^}]*gradient/);
  });
});

describe('приветственный экран: чего в нём нет', () => {
  it('нет нарисованных «интерфейсов»: ни значков-галочек, ни звёзд и колокольчиков, ни заготовок вместо чисел', () => {
    expect(screenSrc).not.toMatch(/\b(Check|Star|Bell|Bot|Send|Download|Search)\b[^\n]*from 'lucide-react'/);
    expect(chartSrc).not.toMatch(/lucide-react/);
    expect(screenSrc + chartSrc).not.toMatch(/emblem-f|wl-pop|wl-ping|wl-sheen|glint/);
  });

  it('линия — настоящий ряд сайта, без сглаживания и без прогнозного коридора', () => {
    expect(screenSrc).toContain('fetchWorldCompareSeries');
    expect(chartSrc).not.toMatch(/lower|upper|range|band/i);
  });

  it('маленький знак — значок сайта', () => {
    expect(screenSrc).toContain('src="/favicon-512.png"');
  });

  it('тексты короткие, без служебных слов; число в словаре не зашито — оно приходит из данных', () => {
    for (const locale of ['ru', 'en']) {
      const dict = MESSAGES[locale];
      for (const step of ['find', 'fresh', 'telegram', 'compare', 'account']) {
        expect(dict[`welcome.${step}.phrase`].length).toBeLessThanOrEqual(48);
        expect(dict[`welcome.${step}.phrase`]).not.toMatch(/\d/);
        const body = dict[`welcome.${step}.body`];
        if (body) expect(body.length).toBeLessThanOrEqual(150);
      }
      const all = Object.entries(dict).filter(([k]) => k.startsWith('welcome.')).map(([, v]) => v).join(' ');
      expect(all).not.toMatch(/API|ETL|парсер|parser|localStorage|cookie|SSR|JSON/i);
      expect(all).not.toMatch(/диапазон|коридор|range|письм|e-?mail|почт/i);
    }
  });
});
