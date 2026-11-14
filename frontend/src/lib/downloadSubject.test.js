// Содержание скачиваний (14.11.2026): каждое событие скачивания и упора в лимит несёт код показателя.
// Первая часть — сам помощник; вторая — обход исходников: новое место без содержания уронит тест.
import { readdirSync, readFileSync, statSync } from 'node:fs';
import { dirname, join, relative } from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';
import { MAX_LIST_CHARS, subjectParams } from './downloadSubject';

describe('subjectParams', () => {
  it('keeps only filled fields and skips Russia as a country', () => {
    expect(subjectParams({ code: 'cpi', country: 'russia' })).toEqual({ code: 'cpi' });
    expect(subjectParams({ code: 'de-gdp', country: 'germany' })).toEqual({ code: 'de-gdp', country: 'germany' });
    expect(subjectParams({ code: 'vrp', region: 'moskva' })).toEqual({ code: 'vrp', region: 'moskva' });
    expect(subjectParams({ codes: ['cpi', '', 'usd-rub'] })).toEqual({ codes: 'cpi,usd-rub' });
    expect(subjectParams({ regions: ['moskva', 'tatarstan'] })).toEqual({ regions: 'moskva,tatarstan' });
    expect(subjectParams()).toEqual({});
    const twelve = subjectParams({ codes: Array.from({ length: 12 }, (_, i) => `c${i}`) });
    expect(twelve.codes.split(',')).toHaveLength(8);
    expect(twelve.codes_more).toBe(4);
  });

  it('cuts long lists by whole codes within 200 chars and counts the rest', () => {
    const long = Array.from({ length: 6 }, (_, i) => `de-bop_its6_tot-s-mio-eur-ext-eu27-2020-cre-${i}`); // 46 знаков
    const out = subjectParams({ codes: long });
    expect(out.codes.length).toBeLessThanOrEqual(MAX_LIST_CHARS);
    expect(out.codes.split(',')).toEqual(long.slice(0, 4)); // 4×46 + 3 запятые = 187
    expect(out.codes_more).toBe(2);
    expect(subjectParams({ codes: ['x'.repeat(250)] })).toEqual({ codes_more: 1 });
    expect(subjectParams({ regions: ['moskva'] })).toEqual({ regions: 'moskva' });
  });
});

// События скачивания и упора (группы GROUP_DOWNLOAD и GROUP_WALL backend/app/services/goal_taxonomy.py).
const SUBJECT_EVENTS = [
  'DOWNLOAD_CSV', 'DOWNLOAD_EXCEL', 'CHART_IMAGE_DOWNLOAD', 'CHART_IMAGE_BLOCKED', 'COMPARE_IMAGE_DOWNLOAD',
  'COMPARE_IMAGE_BLOCKED', 'COMPARE_LIMIT_HIT', 'REGIONS_MAP_GIF_DOWNLOAD', 'REGIONS_MAP_GIF_BLOCKED',
  'DOWNLOAD_LIMIT_HIT',
];
// Места без показателя по смыслу: содержание задаёт сама страница или событие.
const EXEMPT = new Map([
  ['components/CalcMortgageSchedule.jsx', 'график платежей калькулятора: показателя нет, есть source'],
]);
// Событие передаётся переменной (`track(evt, …)` / `track(blockedEvent, …)`): проверяется так же.
const VARIABLE_EVENT_FILES = ['pages/RegionIndicatorPage.jsx', 'pages/WorldRegionIndicatorPage.jsx'];

const SRC = join(dirname(fileURLToPath(import.meta.url)), '..');

function sources(dir) {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name);
    if (statSync(path).isDirectory()) return sources(path);
    return /\.(jsx?|tsx?)$/.test(name) && !/\.test\./.test(name) ? [path] : [];
  });
}

// Текст вызова `track(` до парной скобки.
function callAt(text, start) {
  let depth = 0;
  for (let i = start; i < text.length; i += 1) {
    if (text[i] === '(') depth += 1;
    if (text[i] === ')') { depth -= 1; if (depth === 0) return text.slice(start, i + 1); }
  }
  return text.slice(start);
}

function trackCalls(text) {
  const out = [];
  let i = text.indexOf('track(');
  while (i !== -1) {
    out.push(callAt(text, i + 'track'.length));
    i = text.indexOf('track(', i + 1);
  }
  return out;
}

describe('every download and wall event carries its subject', () => {
  const files = sources(SRC);
  const found = [];
  for (const path of files) {
    const rel = relative(SRC, path);
    if (rel === 'lib/track.js') continue;
    const text = readFileSync(path, 'utf8');
    for (const call of trackCalls(text)) {
      const named = SUBJECT_EVENTS.some((e) => new RegExp(`events\\.${e}\\b`).test(call));
      const variable = VARIABLE_EVENT_FILES.includes(rel) && /^\(\s*(evt|blockedEvent)\b/.test(call);
      if (named || variable) found.push({ rel, call });
    }
  }

  it('finds the known places (guard against a silent scan)', () => {
    expect(new Set(found.map((f) => f.rel)).size).toBeGreaterThanOrEqual(15);
  });

  it.each(found.map((f) => [f.rel, f.call.slice(0, 90).replace(/\s+/g, ' '), f.call]))(
    '%s — %s', (rel, _short, call) => {
      if (EXEMPT.has(rel)) return;
      // Содержание: помощник subjectParams или общий вызов, который его добавляет (gridExport, excel.js).
      const ok = /subjectParams\(/.test(call) || /\babout\)/.test(call);
      expect(ok, `${rel}: событие без кода показателя — добавьте subjectParams({ code, country, region })`).toBe(true);
    },
  );

  it('grid downloads pass the subject (DataTable, compare)', () => {
    const table = readFileSync(join(SRC, 'components/DataTable.jsx'), 'utf8');
    expect(table).toMatch(/source: 'table-range',\s*subject: \{/);
    const compare = readFileSync(join(SRC, 'pages/ComparePage.jsx'), 'utf8');
    expect(compare).toMatch(/source: 'compare', subject: \{ codes \}/);
  });
});
