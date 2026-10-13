import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';
import { localizeSource, localizeViewModeLabel } from './viewModeLabels.js';

describe('localizeViewModeLabel', () => {
  it('keeps Russian on ru', () => {
    expect(localizeViewModeLabel('Год к году', 'ru')).toBe('Год к году');
  });

  it('translates picker labels on en', () => {
    expect(localizeViewModeLabel('Год к году', 'en')).toBe('Year over year');
    expect(localizeViewModeLabel('К прошлому периоду', 'en')).toBe('Over previous period');
    expect(localizeViewModeLabel('нет официального ряда', 'en')).toBe('no official series');
    expect(localizeViewModeLabel('расчётный ряд', 'en')).toBe('derived series');
  });
});

describe('localizeSource', () => {
  it('maps Rosstat on en', () => {
    expect(localizeSource('Росстат', 'en')).toBe('Rosstat');
    expect(localizeSource('Банк России', 'en')).toBe('Bank of Russia');
    expect(localizeSource('Минфин', 'en')).toBe('Ministry of Finance');
    expect(localizeSource('Евростат', 'en')).toBe('Eurostat');
    expect(localizeSource('Банк Японии', 'en')).toBe('Bank of Japan');
  });

  it('keeps Russian on ru', () => {
    expect(localizeSource('Росстат', 'ru')).toBe('Росстат');
    expect(localizeSource('Евростат', 'ru')).toBe('Евростат');
  });

  it('turns English names the server sent into Russian on ru', () => {
    expect(localizeSource('Rosstat, Bank of Russia', 'ru')).toBe('Росстат, Банк России');
    expect(localizeSource('International Monetary Fund', 'ru')).toBe('Международный валютный фонд');
    expect(localizeSource('Ministry of Finance', 'ru')).toBe('Минфин России');
    expect(localizeSource('', 'ru')).toBe('');
  });
});

// Круг 13: источники каталога в английской версии не остаются русскими; фронтенд и backend говорят одно и то же.
describe('источники каталога по-английски (паритет с backend/app/data/i18n/glossary_en.py)', () => {
  const root = join(dirname(fileURLToPath(import.meta.url)), '..', '..', '..', 'backend');
  const seed = readFileSync(join(root, 'seed_data.py'), 'utf8');
  const glossary = readFileSync(join(root, 'app', 'data', 'i18n', 'glossary_en.py'), 'utf8');
  const pairs = new Map([...glossary.matchAll(/"([^"]+)":\s*\(?\s*"([^"]+)"/g)].map((m) => [m[1], m[2]]));
  const sources = [...new Set([...seed.matchAll(/"source":\s*"([^"]+)"/g)].map((m) => m[1]))];

  it('все источники seed_data имеют английскую форму без кириллицы', () => {
    expect(sources.length).toBeGreaterThanOrEqual(12);
    for (const source of sources) {
      expect(/[А-Яа-яЁё]/.test(localizeSource(source, 'en')), source).toBe(false);
    }
  });

  it('форма совпадает с глоссарием backend', () => {
    for (const source of sources) {
      if (pairs.has(source)) expect(localizeSource(source, 'en'), source).toBe(pairs.get(source));
    }
    expect(localizeSource('Управление энергетической информации США (EIA)', 'en')).toBe('U.S. Energy Information Administration (EIA)');
  });
});
