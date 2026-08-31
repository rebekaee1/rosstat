/**
 * Регрессия шапки: логотип vs меню, обрезание краёв, горизонтальный overflow.
 *
 * Меню шапки выровнено по правому краю (justify-end). Когда набор пунктов
 * перестаёт помещаться, лишнее выезжает не вправо, а ВЛЕВО — поверх логотипа.
 * Дополнительно: navbar/тикер не должны вылезать за viewport, края тикера
 * достижимы горизонтальным скроллом (не «вечно скрыты» из-за justify-center).
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
const WIDTHS = [320, 360, 390, 430, 1024, 1280, 1440];
const PATHS = [
  '/',
  '/about',
  '/compare',
  '/russia',
  '/russia/category/prices',
  '/russia/indicator/cpi',
];

const browser = await chromium.launch();
const failures = [];

for (const route of PATHS) {
  for (const width of WIDTHS) {
    const page = await browser.newPage({ viewport: { width, height: 900 } });
    await page.goto(BASE + route, { waitUntil: 'domcontentloaded' });
    await page.waitForSelector('nav.fixed', { timeout: 15000 });
    await page.waitForSelector('nav a[href="/login"], nav a[href="/account"], nav a[href="/register"]', { timeout: 10000 }).catch(() => {});
    await page.waitForTimeout(200);

    const box = await page.evaluate(() => {
      const nav = document.querySelector('nav.fixed');
      const logo = nav?.querySelector('a[aria-label*="Forecast"]');
      const menu = nav?.querySelector('div.hidden.lg\\:flex');
      const vis = (el) => el && getComputedStyle(el).display !== 'none';
      const r = (el) => el.getBoundingClientRect();
      const vw = document.documentElement.clientWidth;
      const docOverflow = document.documentElement.scrollWidth - document.documentElement.clientWidth;
      const navBox = nav ? r(nav) : null;

      let menuBox = null;
      if (logo && menu && vis(menu) && menu.firstElementChild) {
        const items = [...menu.children].filter(vis);
        if (items.length) {
          menuBox = {
            logoRight: Math.round(r(logo).right),
            firstItemLeft: Math.round(r(items[0]).left),
            lastItemRight: Math.round(r(items[items.length - 1]).right),
            menuRight: Math.round(r(menu).right),
          };
        }
      }

      const quotes = [...document.querySelectorAll('[aria-label]')]
        .find((el) => /котир|quote/i.test(el.getAttribute('aria-label') || ''));
      let ticker = null;
      if (quotes) {
        const track = quotes.querySelector(':scope > div') || quotes;
        const cells = [...track.children];
        ticker = {
          scrollWidth: quotes.scrollWidth,
          clientWidth: quotes.clientWidth,
          firstLeft: cells[0] ? Math.round(r(cells[0]).left) : null,
          lastRight: cells.length ? Math.round(r(cells[cells.length - 1]).right) : null,
          scrollerLeft: Math.round(r(quotes).left),
          scrollerRight: Math.round(r(quotes).right),
        };
        quotes.scrollLeft = quotes.scrollWidth;
        const lastAfter = cells.length ? Math.round(r(cells[cells.length - 1]).right) : null;
        quotes.scrollLeft = 0;
        const firstAfterReset = cells[0] ? Math.round(r(cells[0]).left) : null;
        ticker.lastReachable = lastAfter != null && lastAfter <= ticker.scrollerRight + 2;
        ticker.firstReachable = firstAfterReset != null && firstAfterReset >= ticker.scrollerLeft - 2;
      }

      return {
        vw,
        docOverflow,
        nav: navBox ? {
          left: Math.round(navBox.left),
          right: Math.round(navBox.right),
        } : null,
        menuBox,
        ticker,
      };
    });
    await page.close();

    const label = `${route} @ ${width}`;
    if (!box?.nav) {
      failures.push(`${label}: navbar не найден`);
      continue;
    }
    if (box.nav.left < -1) {
      failures.push(`${label}: navbar обрезан слева (${box.nav.left}px)`);
    }
    if (box.nav.right > box.vw + 1) {
      failures.push(`${label}: navbar обрезан справа (${box.nav.right} > ${box.vw})`);
    }
    if (box.docOverflow > 2) {
      failures.push(`${label}: горизонтальный overflow документа ${box.docOverflow}px`);
    }
    if (box.menuBox) {
      const overlap = box.menuBox.logoRight - box.menuBox.firstItemLeft;
      const spillRight = box.menuBox.lastItemRight - box.menuBox.menuRight;
      if (overlap > 0) failures.push(`${label}: меню наезжает на логотип на ${overlap}px`);
      else if (spillRight > 2) failures.push(`${label}: меню вылезает вправо на ${spillRight}px`);
      else console.log(`OK  ${label} — зазор ${-overlap}px`);
    } else {
      console.log(`OK  ${label} — navbar в viewport, overflow ${box.docOverflow}px`);
    }
    if (box.ticker && box.ticker.scrollWidth > box.ticker.clientWidth + 4) {
      if (!box.ticker.firstReachable) {
        failures.push(`${label}: левый край тикера недостижим скроллом`);
      }
      if (!box.ticker.lastReachable) {
        failures.push(`${label}: правый край тикера недостижим скроллом`);
      }
    }
  }
}

await browser.close();

if (failures.length) {
  console.error('\nПЕРЕПОЛНЕНИЕ ШАПКИ:');
  failures.forEach((f) => console.error('  ' + f));
  process.exit(1);
}
console.log('\nnavbar-overlap: OK');
