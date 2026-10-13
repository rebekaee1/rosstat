#!/usr/bin/env node
/**
 * Раскадровка загрузки в условиях perf-mobile.mjs (телефон, CPU ×4, медленный 4G): кадры экрана через Page.startScreencast,
 * сохраняются файлами `<out>/<t_мс>.jpg` (время от начала навигации). Нужна, чтобы увидеть, что видит человек и когда.
 *   node scripts/dev/perf-film.mjs --url https://ru.localhost:5290/ --out /tmp/film [--human] [--seconds 9]
 */
import fs from 'node:fs';
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
const OUT = path.resolve(String(args.out || '/tmp/film'));
fs.mkdirSync(OUT, { recursive: true });
const browser = await chromium.launch({
  args: ['--ignore-certificate-errors', '--host-resolver-rules=MAP *.localhost 127.0.0.1, MAP *.yandex.ru 127.0.0.1:5290, MAP *.yandex.com 127.0.0.1:5290, MAP yastatic.net 127.0.0.1:5290'],
});
const ctx = await browser.newContext({
  viewport: { width: 390, height: 844 }, deviceScaleFactor: 1, isMobile: true, hasTouch: true, ignoreHTTPSErrors: true,
  userAgent: 'Mozilla/5.0 (Linux; Android 11; Moto G Power (2022)) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Mobile Safari/537.36',
});
if (args.human) await ctx.addInitScript('Object.defineProperty(Navigator.prototype, "webdriver", { get: () => false });');
const page = await ctx.newPage();
const cdp = await ctx.newCDPSession(page);
await cdp.send('Network.enable');
await cdp.send('Network.emulateNetworkConditions', { offline: false, latency: 150, downloadThroughput: 1.6e6 / 8, uploadThroughput: 0.75e6 / 8 });
await cdp.send('Emulation.setCPUThrottlingRate', { rate: Number(args.cpu || 4) });
const frames = [];
cdp.on('Page.screencastFrame', (e) => { frames.push({ wall: e.metadata.timestamp * 1000, data: e.data }); cdp.send('Page.screencastFrameAck', { sessionId: e.sessionId }).catch(() => {}); });
await cdp.send('Page.startScreencast', { format: 'jpeg', quality: 50, maxWidth: 390, maxHeight: 844, everyNthFrame: 1 });
const t0 = Date.now();
await page.goto(String(args.url), { waitUntil: 'commit' });
await new Promise((r) => setTimeout(r, Number(args.seconds || 9) * 1000));
const origin = await page.evaluate(() => performance.timeOrigin);
await browser.close();
let last = -1e9;
for (const f of frames) {
  const t = Math.round(f.wall - origin);
  if (t - last < 250) continue;
  last = t;
  fs.writeFileSync(path.join(OUT, `${String(Math.max(0, t)).padStart(5, '0')}.jpg`), Buffer.from(f.data, 'base64'));
}
console.log(`кадров ${frames.length}, сохранено в ${OUT}, ${Date.now() - t0} мс`);
