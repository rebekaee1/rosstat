// Круг 9, зона C (страна мира, рейтинг, показатели): страж видимых решений.
// Строка рейтинга видна всегда (не стартует с opacity:0), мини-график-скелет без «пилюли», нет рамок и колец.
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';

const here = dirname(fileURLToPath(import.meta.url));
const read = (name) => readFileSync(join(here, name), 'utf8');
const z6 = read('z6-rating.css');
const z5 = read('z5-country.css');
const world = read('world.css');

/** Тело правила с точным селектором (первое совпадение). */
function rule(css, selector) {
  const escaped = selector.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const match = css.match(new RegExp(`(?:^|\\n)${escaped}\\s*\\{([^}]*)\\}`));
  expect(match, `нет правила «${selector}»`).toBeTruthy();
  return match[1];
}

describe('круг 9 C: рейтинг (R1, R2, S11)', () => {
  it('у строки таблицы нет анимации появления от opacity:0: она видна, даже если анимация не стартовала', () => {
    expect(z6).not.toMatch(/\.z6-row\s*\{[^}]*animation:\s*z6-row-in/);
    expect(z6).not.toMatch(/@keyframes z6-row-in/);
    expect(z6).not.toMatch(/z6-row-in/);
  });

  it('рост столбца идёт только у первых 12 строк и с fill-mode backwards, не both', () => {
    expect(z6).not.toMatch(/z6-bar-grow[^;]*\bboth\b/);
    expect(z6).toMatch(/\.z6-row:nth-child\(-n \+ 12\) \.w6d-bar > span\s*\{[^}]*z6-bar-grow[^;]*backwards/);
  });

  it('зазор между липкой шапкой и первой строкой закрыт продолжением шапки', () => {
    expect(z6).toMatch(/\.z6-table-card thead th::after\s*\{[^}]*top: 100%[^}]*height: 6px[^}]*background: inherit/);
  });

  it('название в карточке рейтинга переносится по словам, а не посреди слова', () => {
    expect(rule(world, '.w2-rank-name')).toMatch(/overflow-wrap: break-word/);
    expect(rule(world, '.w2-rank-name')).not.toMatch(/anywhere/);
  });
});

describe('круг 9 C: страница страны (W1, W4)', () => {
  it('скелет мини-графика в строке рисуется контуром линии (clip-path), а не серой пилюлей', () => {
    const skel = rule(z5, '.z5-spark-skel--row');
    expect(skel).toMatch(/clip-path:\s*polygon\(/);
    expect(skel).toMatch(/border-radius:\s*0/);
  });

  it('название показателя в карточке читается в три строки и не рвётся посреди слова', () => {
    const title = rule(z5, '.z5-row__title');
    expect(title).toMatch(/-webkit-line-clamp:\s*3/);
    expect(title).toMatch(/overflow-wrap:\s*break-word/);
  });

  it('новые правила круга без рамок и колец', () => {
    const added = [
      rule(z5, '.z5-spark-skel--row'),
      rule(z5, '.z5-row__title'),
      z6.slice(z6.indexOf('Круг 9 (S11)'), z6.indexOf('Круг 9 (S11)') + 600),
    ].join('\n');
    expect(added).not.toMatch(/\bborder\s*:/);
    expect(added).not.toMatch(/0 0 0 \d+px/);
    expect(added).not.toMatch(/\boutline\b/);
  });
});
