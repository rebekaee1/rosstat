#!/usr/bin/env node
/**
 * Профиль главного потока при загрузке страницы в условиях perf-mobile.mjs (CPU ×4, медленный 4G).
 * Печатает: время по файлам (self time), самые «тяжёлые» функции, долгие задачи с моментом старта.
 * Нужен, чтобы понять, ЧЕМ занят процессор между FCP и TTI (а не гадать по размеру бандла).
 *
 *   node scripts/dev/perf-profile.mjs --url https://ru.localhost:5290/russia [--cpu 4] [--top 25] [--seconds 9] [--human] [--trace]
 *   --dist DIR  сборка с sourcemap (vite build --sourcemap): тяжёлые функции печатаются с исходным файлом и строкой
 */
import fs from 'node:fs';
import path from 'node:path';
import { createRequire } from 'node:module';
import { fileURLToPath, pathToFileURL } from 'node:url';

async function loadPlaywright() {
  const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
  const req = createRequire(path.join(root, 'frontend', 'package.json'));
  return import(pathToFileURL(req.resolve('playwright')).href);
}
const args = Object.fromEntries(process.argv.slice(2).reduce((acc, a, i, all) => {
  if (a.startsWith('--')) acc.push([a.slice(2), all[i + 1] && !all[i + 1].startsWith('--') ? all[i + 1] : true]);
  return acc;
}, []));
const URL_ = String(args.url);
const CPU = Number(args.cpu || 4);
const TOP = Number(args.top || 25);
const SECONDS = Number(args.seconds || 9);
const { chromium } = await loadPlaywright().then((m) => (m.chromium ? m : m.default));
const browser = await chromium.launch({
  args: ['--ignore-certificate-errors', '--host-resolver-rules=MAP *.localhost 127.0.0.1, MAP *.yandex.ru 127.0.0.1:5290, MAP *.yandex.com 127.0.0.1:5290, MAP yastatic.net 127.0.0.1:5290'],
});
const ctx = await browser.newContext({
  viewport: { width: 390, height: 844 }, deviceScaleFactor: 2, isMobile: true, hasTouch: true, ignoreHTTPSErrors: true,
  userAgent: 'Mozilla/5.0 (Linux; Android 11; Moto G Power (2022)) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Mobile Safari/537.36',
});
if (args.human) await ctx.addInitScript('Object.defineProperty(Navigator.prototype, "webdriver", { get: () => false });');
const page = await ctx.newPage();
const cdp = await ctx.newCDPSession(page);
await cdp.send('Network.enable');
await cdp.send('Network.emulateNetworkConditions', { offline: false, latency: 150, downloadThroughput: (1.6e6) / 8, uploadThroughput: (0.75e6) / 8 });
await cdp.send('Emulation.setCPUThrottlingRate', { rate: CPU });
const events = [];
if (args.trace) {
  const tr = await browser.startTracing(page, { categories: ['devtools.timeline', 'v8', 'disabled-by-default-devtools.timeline', 'blink.user_timing'] });
  void tr;
}
await cdp.send('Profiler.enable');
await cdp.send('Profiler.setSamplingInterval', { interval: 500 });
await cdp.send('Profiler.start');
const t0 = Date.now();
await page.goto(URL_, { waitUntil: 'commit' });
await new Promise((r) => setTimeout(r, SECONDS * 1000));
const { profile } = await cdp.send('Profiler.stop');
let traceBuf = null;
if (args.trace) traceBuf = await browser.stopTracing();
await browser.close();
if (traceBuf) {
  const ev = JSON.parse(traceBuf.toString()).traceEvents;
  const nav = ev.find((e) => e.name === 'navigationStart' || e.name === 'NavigationStart') || ev.find((e) => e.name === 'ResourceSendRequest');
  const t0m = nav ? nav.ts : Math.min(...ev.filter((e) => e.ts).map((e) => e.ts));
  const mainTid = (() => { const m = ev.find((e) => e.name === 'thread_name' && e.args && e.args.name === 'CrRendererMain'); return m ? m.tid : null; })();
  const names = ['UpdateLayoutTree', 'Layout', 'PrePaint', 'Paint', 'Layerize', 'Commit', 'EvaluateScript', 'v8.compile', 'v8.run', 'FunctionCall', 'ParseHTML', 'ParseAuthorStyleSheet', 'MinorGC', 'MajorGC', 'V8.GC_MC_BACKGROUND_MARKING', 'XHRReadyStateChange', 'TimerFire', 'FireAnimationFrame', 'RunMicrotasks', 'EventDispatch', 'Decode Image', 'ImageDecodeTask', 'ResourceFinish'];
  const sum = new Map();
  const tasks = [];
  for (const e of ev) {
    if (e.ph !== 'X' || e.tid !== mainTid) continue;
    if (names.includes(e.name)) sum.set(e.name, (sum.get(e.name) || 0) + e.dur / 1000);
    if (e.name === 'RunTask' && e.dur > 50000) tasks.push([Math.round((e.ts - t0m) / 1000), Math.round(e.dur / 1000)]);
  }
  console.log('\nглавный поток (суммарная длительность по типам событий, мс; вложенные события считаются и в родителе):');
  [...sum].sort((a, b) => b[1] - a[1]).forEach(([n, ms]) => console.log(String(Math.round(ms)).padStart(7), n));
  console.log('\nдолгие задачи (старт мс от навигации, длительность мс):', JSON.stringify(tasks));
  // Что внутри самых тяжёлых layout/style: счётчики элементов
  const lay = ev.filter((e) => e.ph === 'X' && e.tid === mainTid && (e.name === 'UpdateLayoutTree' || e.name === 'Layout') && e.dur > 20000).map((e) => [e.name, Math.round((e.ts - t0m) / 1000), Math.round(e.dur / 1000), e.args && e.args.beginData ? e.args.beginData.dirtyObjects : (e.args && e.args.elementCount)]);
  console.log('тяжёлые layout/style (>20 мс): имя, старт, мс, объектов:', JSON.stringify(lay));
}

let tm = null;
const mapCache = new Map();
if (args.dist) {
  const tmod = await import(pathToFileURL(createRequire(path.join(path.resolve(String(args.dist)), 'x')).resolve('@jridgewell/trace-mapping', { paths: [path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../frontend/node_modules')] })).href);
  const { TraceMap, originalPositionFor } = tmod.TraceMap ? tmod : tmod.default;
  tm = (url, line, col) => {
    const m = /\/assets\/([^?]+)$/.exec(url || '');
    if (!m) return null;
    const f = path.join(path.resolve(String(args.dist)), 'assets', `${m[1]}.map`);
    if (!mapCache.has(f)) mapCache.set(f, fs.existsSync(f) ? new TraceMap(JSON.parse(fs.readFileSync(f, 'utf8'))) : null);
    const t = mapCache.get(f);
    if (!t) return null;
    const o = originalPositionFor(t, { line: line + 1, column: col });
    return o && o.source ? `${o.source.replace(/^.*\/(src|node_modules)\//, '$1/')}:${o.line}${o.name ? ` ${o.name}` : ''}` : null;
  };
}
const nodes = new Map(profile.nodes.map((n) => [n.id, n]));
const self = new Map();
const byFile = new Map();
const dt = profile.timeDeltas;
profile.samples.forEach((id, i) => {
  const ms = (dt[i] || 0) / 1000;
  self.set(id, (self.get(id) || 0) + ms);
});
let total = 0;
for (const [id, ms] of self) {
  const n = nodes.get(id);
  const url = (n.callFrame.url || '(native)').replace(/^https?:\/\/[^/]+/, '') || '(native)';
  byFile.set(url, (byFile.get(url) || 0) + ms);
  total += ms;
}
const idle = [...self].filter(([id]) => ['(idle)', '(program)', '(garbage collector)'].includes(nodes.get(id).callFrame.functionName)).reduce((s, [, ms]) => s + ms, 0);
console.log(`профиль ${URL_} · CPU ×${CPU}: всего ${Math.round(total)} мс выборки (idle ${Math.round(idle)}), реальное время ${Date.now() - t0} мс`);
console.log('\nпо файлам (self, мс; на замедленном процессоре):');
[...byFile].sort((a, b) => b[1] - a[1]).slice(0, 18).forEach(([u, ms]) => console.log(String(Math.round(ms)).padStart(7), u.slice(0, 100)));
console.log('\nтяжёлые функции:');
[...self].sort((a, b) => b[1] - a[1]).slice(0, TOP).forEach(([id, ms]) => {
  const c = nodes.get(id).callFrame;
  console.log(String(Math.round(ms)).padStart(7), `${c.functionName || '(anon)'}`.padEnd(30), (c.url || '').replace(/^https?:\/\/[^/]+/, '').slice(0, 44), `${c.lineNumber}:${c.columnNumber}`, tm ? (tm(c.url, c.lineNumber, c.columnNumber) || '') : '');
});
