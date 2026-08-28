#!/usr/bin/env node
/** Отладка: состояние графика/таблицы на месячной карточке. */
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const require = createRequire(path.join(__dirname, '..', '..', 'frontend', 'package.json'));
const { chromium } = require('playwright');

const BASE = process.argv[2] || 'http://localhost:3000';
const browser = await chromium.launch();
const page = await browser.newPage();
await page.goto(`${BASE}/russia/region/moskva/ceni-ai92`, { waitUntil: 'domcontentloaded' });
await page.waitForTimeout(8000);

const chartHtml = await page.locator('#chart').innerHTML().catch(() => 'NO #chart');
console.log('chart svg count:', await page.locator('#chart svg').count());
console.log('chart svg len:', chartHtml.length);
console.log('has recharts:', chartHtml.includes('recharts'));
const tblBtn = page.getByRole('button', { name: /таблиц/i });
console.log('tbl btn count:', await tblBtn.count());
if (await tblBtn.count()) {
  await tblBtn.first().click();
  await page.waitForTimeout(600);
  console.log('table count:', await page.locator('table').count());
  const t = await page.locator('table').first().innerText().catch(() => 'NO TABLE');
  console.log('table head:', t.slice(0, 120).replace(/\n/g, ' | '));
}
await page.screenshot({ path: 'tmp-design/e2e-fuel-debug.png' });
await browser.close();
