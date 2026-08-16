/**
 * Regression: mid-dot « · » (U+00B7) запрещён в публичном UI и SSR-шаблонах
 * (директива владельца, `.cursor/rules/no-middle-dot.mdc`).
 *
 * Сканирует шаблоны SSR backend/app/services/seo_*.py и все
 * frontend/src JSX-компоненты/страницы. Падает со списком файл:строка.
 */
import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join, relative, resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

const ROOT = resolve(import.meta.dirname, '../../..');
const MID_DOT = '\u00B7';

/**
 * Явные исключения (не широкая маска):
 * - forecaster.py — mid-dot в docstring-формулах = умножение, не публичный текст
 *   (файл вне скана seo_*.py, listed для документации инварианта);
 * - этот тест — символ в комментариях/константе проверки;
 * - HomeWorkbench.component.test.jsx — regex как раз ловит запрещённый паттерн.
 */
const ALLOWED_REL_PATHS = new Set([
  'backend/app/services/forecaster.py',
  'frontend/src/lib/noMiddleDot.test.js',
  'frontend/src/components/home/HomeWorkbench.component.test.jsx',
]);

function walkFiles(dir, predicate, out = []) {
  for (const name of readdirSync(dir)) {
    const full = join(dir, name);
    const st = statSync(full);
    if (st.isDirectory()) {
      walkFiles(full, predicate, out);
    } else if (predicate(full, name)) {
      out.push(full);
    }
  }
  return out;
}

function collectTargets() {
  const seoDir = resolve(ROOT, 'backend/app/services');
  const seoFiles = readdirSync(seoDir)
    .filter((name) => name.startsWith('seo_') && name.endsWith('.py'))
    .map((name) => join(seoDir, name));

  const jsxFiles = walkFiles(
    resolve(ROOT, 'frontend/src'),
    (_full, name) => name.endsWith('.jsx'),
  );

  return [...seoFiles, ...jsxFiles];
}

function findMidDotHits(absPath) {
  const rel = relative(ROOT, absPath).split('\\').join('/');
  if (ALLOWED_REL_PATHS.has(rel)) return [];
  const text = readFileSync(absPath, 'utf8');
  if (!text.includes(MID_DOT)) return [];
  const hits = [];
  for (const [idx, line] of text.split('\n').entries()) {
    if (line.includes(MID_DOT)) {
      hits.push(`${rel}:${idx + 1}`);
    }
  }
  return hits;
}

describe('no mid-dot (U+00B7) in public surfaces', () => {
  it('seo_*.py и frontend JSX без mid-dot (кроме явных исключений)', () => {
    const targets = collectTargets();
    expect(targets.length).toBeGreaterThan(20);

    const hits = targets.flatMap(findMidDotHits);
    expect(hits, hits.join('\n')).toEqual([]);
  });

  it('список исключений не пустой и покрывает известные безопасные случаи', () => {
    expect(ALLOWED_REL_PATHS.has('backend/app/services/forecaster.py')).toBe(true);
    expect(ALLOWED_REL_PATHS.has('frontend/src/lib/noMiddleDot.test.js')).toBe(true);
    expect(
      ALLOWED_REL_PATHS.has('frontend/src/components/home/HomeWorkbench.component.test.jsx'),
    ).toBe(true);
  });
});
