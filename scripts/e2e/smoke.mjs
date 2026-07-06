#!/usr/bin/env node
/**
 * Т-14: E2E smoke (Playwright) — 5 браузерных сценариев + YandexBot SSR-suite.
 *
 * Проверяет живой стек (docker compose up): SPA реально загружается, ключевые
 * страницы рендерят контент (не белый экран после смены asset-hash), SSR для
 * поисковых ботов отдаёт canonical/JSON-LD.
 *
 * Запуск:  node scripts/e2e/smoke.mjs [BASE_URL]
 *          BASE_URL по умолчанию http://localhost:3000
 * Зависимости: playwright из frontend/node_modules (npm i уже ставит).
 */

import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const require = createRequire(path.join(__dirname, '..', '..', 'frontend', 'package.json'));
const { chromium } = require('playwright');

const BASE = process.argv[2] || process.env.E2E_BASE_URL || 'http://localhost:3000';
const failures = [];

function ok(name) {
  console.log(`  ✓ ${name}`);
}

function fail(name, detail) {
  failures.push(`${name}: ${detail}`);
  console.error(`  ✗ ${name}: ${detail}`);
}

async function expectVisibleText(page, name, pattern, timeout = 15000) {
  try {
    await page.waitForFunction(
      (p) => new RegExp(p, 'i').test(document.body.innerText),
      pattern,
      { timeout },
    );
    ok(name);
  } catch {
    fail(name, `текст /${pattern}/ не появился за ${timeout}ms`);
  }
}

// ── Браузерные сценарии ──────────────────────────────────────────────

async function browserSuite() {
  console.log(`\nБраузерные сценарии (${BASE}):`);
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
  const pageErrors = [];
  page.on('pageerror', (e) => pageErrors.push(String(e)));

  // 1. Карточка индикатора: имя + график (svg от recharts).
  await page.goto(`${BASE}/indicator/cpi`, { waitUntil: 'domcontentloaded' });
  await expectVisibleText(page, 'indicator/cpi: контент карточки', 'потребительск|инфляц');
  try {
    await page.waitForSelector('svg', { timeout: 15000 });
    ok('indicator/cpi: график отрисован');
  } catch {
    fail('indicator/cpi: график', 'svg не появился');
  }

  // 2. Сравнение.
  await page.goto(`${BASE}/compare`, { waitUntil: 'domcontentloaded' });
  await expectVisibleText(page, 'compare: страница сравнения', 'сравнени');

  // 3. Регионы.
  await page.goto(`${BASE}/regions`, { waitUntil: 'domcontentloaded' });
  await expectVisibleText(page, 'regions: хаб регионов', 'регион');

  // 4. Embed-виджет (iframe-страница графика).
  await page.goto(`${BASE}/embed/chart/cpi`, { waitUntil: 'domcontentloaded' });
  try {
    await page.waitForSelector('svg, canvas', { timeout: 15000 });
    ok('embed/chart/cpi: виджет отрисован');
  } catch {
    fail('embed/chart/cpi', 'ни svg, ни canvas не появились');
  }

  // 5. Admin BI: гость обязан увидеть форму входа, не дашборд и не белый экран.
  await page.goto(`${BASE}/admin/bi`, { waitUntil: 'domcontentloaded' });
  await expectVisibleText(page, 'admin/bi: гейт входа', 'вход|войти|404');

  if (pageErrors.length) {
    fail('JS-ошибки на страницах', pageErrors.slice(0, 3).join(' | '));
  } else {
    ok('без необработанных JS-ошибок');
  }
  await browser.close();
}

// ── SSR-suite под YandexBot ──────────────────────────────────────────

const BOT_UA = 'Mozilla/5.0 (compatible; YandexBot/3.0; +http://yandex.com/bots)';
const SSR_PAGES = ['/', '/indicator/cpi', '/category/prices', '/regions', '/today'];

async function ssrSuite() {
  console.log('\nSSR под YandexBot:');
  for (const p of SSR_PAGES) {
    const name = `SSR ${p}`;
    try {
      const r = await fetch(`${BASE}${p}`, { headers: { 'User-Agent': BOT_UA } });
      const html = await r.text();
      if (r.status !== 200) {
        fail(name, `status ${r.status}`);
        continue;
      }
      const problems = [];
      if (!/<link rel="canonical"/.test(html)) problems.push('нет canonical');
      if (!/application\/ld\+json/.test(html)) problems.push('нет JSON-LD');
      if (!/<title>[^<]{10,}/.test(html)) problems.push('пустой title');
      if (problems.length) fail(name, problems.join(', '));
      else ok(name);
    } catch (e) {
      fail(name, String(e));
    }
  }
}

const started = Date.now();
await browserSuite();
await ssrSuite();

console.log(`\n${failures.length === 0 ? 'SMOKE OK' : `SMOKE FAILED (${failures.length})`} за ${((Date.now() - started) / 1000).toFixed(1)}s`);
process.exit(failures.length === 0 ? 0 : 1);
