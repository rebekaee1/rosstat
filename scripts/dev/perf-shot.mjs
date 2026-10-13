#!/usr/bin/env node
/**
 * Кадр страницы после загрузки и простоя (без замедления) для сравнения «до/после» на пиксели:
 *   node scripts/dev/perf-shot.mjs --url https://ru.localhost:5290/compare --out /tmp/a.png [--width 390] [--wait 6000] [--dark]
 * Режим как у человека (navigator.webdriver=false: заставка и сцена с F). Сравнение: scripts/dev/perf-shot-diff.py A.png B.png.
 */
import path from 'node:path';
import { createRequire } from 'node:module';
import { fileURLToPath, pathToFileURL } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const req = createRequire(path.join(root, 'frontend', 'package.json'));
const { chromium } = await import(pathToFileURL(req.resolve('playwright')).href).then((m) => (m.chromium ? m : m.default));
const args = Object.fromEntries(process.argv.slice(2).reduce((acc, a, i, all) => {
  if (a.startsWith('--')) acc.push([a.slice(2), all[i + 1] && !all[i + 1].startsWith('--') ? all[i + 1] : true]);
  return acc;
}, []));
const W = Number(args.width || 390);
const browser = await chromium.launch({ args: ['--ignore-certificate-errors', '--host-resolver-rules=MAP *.localhost 127.0.0.1, MAP *.yandex.ru 127.0.0.1:5290, MAP *.yandex.com 127.0.0.1:5290, MAP yastatic.net 127.0.0.1:5290'] });
const ctx = await browser.newContext({
  viewport: { width: W, height: W < 800 ? 844 : 900 }, deviceScaleFactor: 2, isMobile: W < 800, hasTouch: W < 800, ignoreHTTPSErrors: true,
  colorScheme: args.dark ? 'dark' : 'light',
});
await ctx.addInitScript('Object.defineProperty(Navigator.prototype, "webdriver", { get: () => false });');
const page = await ctx.newPage();
await page.route((u) => /ads\/system|partner-code|safeframe|metrika|\/watch\//.test(u.toString()), (r) => r.abort());
await page.goto(String(args.url), { waitUntil: 'load' });
await page.waitForTimeout(Number(args.wait || 6000));
await page.screenshot({ path: String(args.out) });
await browser.close();
