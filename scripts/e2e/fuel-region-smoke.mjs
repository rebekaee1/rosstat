#!/usr/bin/env node
/**
 * Разовый смоук новых топливных рядов (раздел 16 «Транспорт»):
 * SPA-карточка месячного ряда (ceni-ai92, Москва) с графиком/таблицей,
 * годовой ряд (roznica-dt), SSR-версия и OG-картинка.
 *
 * Запуск: node scripts/e2e/fuel-region-smoke.mjs [BASE_URL]
 */

import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const require = createRequire(path.join(__dirname, '..', '..', 'frontend', 'package.json'));
const { chromium } = require('playwright');

const BASE = process.argv[2] || process.env.E2E_BASE_URL || 'http://localhost:3000';
const failures = [];

function ok(name) { console.log(`  ok ${name}`); }
function fail(name, detail) {
  failures.push(`${name}: ${detail}`);
  console.error(`  FAIL ${name}: ${detail}`);
}

const browser = await chromium.launch();
try {
  // 1. SPA: месячная карточка (Москва, АИ-92) — заголовок, значение, график, таблица.
  const page = await browser.newPage();
  await page.goto(`${BASE}/russia/region/moskva/ceni-ai92`, { waitUntil: 'domcontentloaded' });
  try {
    await page.waitForFunction(
      () => /АИ-92/i.test(document.body.innerText) && /июл|июль/i.test(document.body.innerText),
      { timeout: 20000 },
    );
    ok('SPA: заголовок и последний месяц отрисовались');
  } catch {
    fail('SPA: месячная карточка', 'не дождались заголовка/месяца');
  }
  const chartPoints = await page.locator('#chart svg').count();
  if (chartPoints > 0) ok('SPA: график (recharts) нарисован');
  else fail('SPA: график', 'svg не найден');

  const h1 = await page.locator('h1').first().innerText().catch(() => '');
  const headArea = await page.locator('main, body').first().innerText().catch(() => '');
  if (/АИ-92/.test(h1) && /[Мм]осква/.test(headArea)) ok(`SPA: h1 «${h1.slice(0, 60)}…»`);
  else fail('SPA: h1', h1 || 'пусто');

  const bodyText = await page.evaluate(() => document.body.innerText);
  if (/среднероссийск|России/i.test(bodyText)) ok('SPA: сравнение с РФ доступно');

  // Таблица: раскрываем и проверяем месячную строку
  await page.getByRole('button', { name: /таблиц/i }).first().click().catch(() => {});
  await page.waitForTimeout(600);
  const tableText = await page.locator('table').first().innerText().catch(() => '');
  if (/июль 2026/i.test(tableText)) ok('SPA: таблица содержит июль 2026');
  else fail('SPA: таблица', 'нет строки «июль 2026»');

  await page.screenshot({ path: 'tmp-design/e2e-fuel-monthly.png', fullPage: false });

  // 2. Годовой ряд (розница дизеля, Белгородская область)
  const page2 = await browser.newPage();
  await page2.goto(`${BASE}/russia/region/belgorodskaya-oblast/roznica-dt`, { waitUntil: 'domcontentloaded' });
  try {
    await page2.waitForFunction(() => /дизельного топлива/i.test(document.body.innerText), { timeout: 15000 });
    ok('SPA: годовой ряд roznica-dt открылся');
  } catch {
    fail('SPA: годовой ряд roznica-dt', 'заголовок не дождался');
  }
  await page2.screenshot({ path: 'tmp-design/e2e-fuel-annual.png', fullPage: false });

  // 3. SSR-версия (обычный UA) — заголовок/таблица/OG-картинка в теле.
  const page3 = await browser.newPage();
  const ssrUrl = `${BASE}/russia/region/moskva/ceni-ai92`;
  const resp = await page3.goto(ssrUrl, { waitUntil: 'domcontentloaded' });
  const status = resp?.status();
  if (status === 200) ok('SSR: страница отвечает 200');
  else fail('SSR: статус', String(status));
  const ssrHtml = await page3.content();
  if (/og:image/.test(ssrHtml)) ok('SSR: og:image присутствует');
  if (/application\/ld\+json/.test(ssrHtml)) ok('SSR: JSON-LD присутствует');
} finally {
  await browser.close();
}

if (failures.length) {
  console.error(`\nПровалов: ${failures.length}`);
  failures.forEach((f) => console.error(' - ' + f));
  process.exit(1);
}
console.log('\nВсе проверки прошли.');
