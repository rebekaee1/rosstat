/**
 * Регрессия «задвоенный логотип».
 *
 * Меню шапки выровнено по правому краю (justify-end). Когда набор пунктов
 * перестаёт помещаться, лишнее выезжает не вправо, а ВЛЕВО — поверх логотипа,
 * и текст пунктов накладывается на «Forecast Economy». Ни scrollWidth, ни
 * визуальный обзор на широком мониторе этого не ловят: переполнение в
 * start-направлении во flex не попадает в scrollWidth.
 *
 * Здесь сравниваются боксы: правый край логотипа против левого края первого
 * пункта меню. Любое пересечение — дефект.
 *
 * Запуск: node scripts/e2e/navbar-overlap.mjs [baseUrl]
 */
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const require = createRequire(path.join(__dirname, '..', '..', 'frontend', 'package.json'));
const { chromium } = require('playwright');

const BASE = process.argv[2] ?? process.env.E2E_BASE_URL ?? 'http://127.0.0.1:3000';
const WIDTHS = [1024, 1152, 1280, 1440, 1600, 1920];
const PATHS = ['/', '/world/germany', '/indicator/cpi'];

const browser = await chromium.launch();
const failures = [];

for (const path of PATHS) {
  for (const width of WIDTHS) {
    const page = await browser.newPage({ viewport: { width, height: 900 } });
    await page.goto(BASE + path, { waitUntil: 'domcontentloaded' });
    await page.waitForSelector('nav.fixed', { timeout: 15000 });
    await page.waitForTimeout(400);

    const box = await page.evaluate(() => {
      const nav = document.querySelector('nav.fixed');
      const logo = nav.querySelector('a[aria-label*="Forecast"]');
      const menu = nav.querySelector('div.hidden.lg\\:flex');
      if (!logo || !menu || !menu.firstElementChild) return null;
      const vis = (el) => getComputedStyle(el).display !== 'none';
      const items = [...menu.children].filter(vis);
      if (!items.length) return null;
      const r = (el) => el.getBoundingClientRect();
      return {
        logoRight: Math.round(r(logo).right),
        firstItemLeft: Math.round(r(items[0]).left),
        lastItemRight: Math.round(r(items[items.length - 1]).right),
        menuRight: Math.round(r(menu).right),
      };
    });
    await page.close();

    if (!box) continue;
    const overlap = box.logoRight - box.firstItemLeft;
    const spillRight = box.lastItemRight - box.menuRight;
    const label = `${path} @ ${width}`;
    if (overlap > 0) failures.push(`${label}: меню наезжает на логотип на ${overlap}px`);
    // 2px допуска: у пунктов -mx-0.5 под кольцо фокуса, бокс шире контента.
    else if (spillRight > 2) failures.push(`${label}: меню вылезает вправо на ${spillRight}px`);
    else console.log(`OK  ${label} — зазор ${-overlap}px`);
  }
}

await browser.close();

if (failures.length) {
  console.error('\nПЕРЕПОЛНЕНИЕ ШАПКИ:');
  failures.forEach((f) => console.error('  ' + f));
  process.exit(1);
}
console.log('\nnavbar-overlap: OK');
