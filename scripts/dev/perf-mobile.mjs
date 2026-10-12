#!/usr/bin/env node
/**
 * Замер скорости страницы «как на телефоне» (Playwright + CDP). Один и тот же протокол до и после правок.
 *
 * Условия: окно 390×844 (dpr 2, касание), процессор ×4 медленнее (Emulation.setCPUThrottlingRate),
 * сеть «медленный 4G» (Network.emulateNetworkConditions: 1,6 Мбит/с вниз, 0,75 вверх, задержка 150 мс).
 * Каждый прогон — новый профиль браузера (холодный кэш, без сервис-воркера). Первый холодный прогон каждой
 * страницы продолжается «тёплым»: тот же профиль, повторная загрузка (кэш и сервис-воркер уже есть).
 *
 * Метрики (мс от начала навигации): TTFB, FCP, LCP, Speed Index (по кадрам экрана, гистограммы как у Lighthouse),
 * долгие задачи ≥ 50 мс и TBT (сумма превышений над 50 мс между FCP и TTI), TTI (окно 5 с без долгих задач и
 * не больше двух запросов в полёте), «SPA готово» (приложение смонтировано и открыто: html.fe-js, до этого человек видит
 * серверный текст или заставку), отклик главного потока (responsive в JSON),
 * CLS, число и вес запросов (в сжатом виде по сети), вес JS до FCP/до загрузки/всего, порядок водопада.
 *
 * Пример (локальная сборка через perf-serve.mjs; https://en.localhost:5290 и https://ru.localhost:5290):
 *   node scripts/dev/perf-mobile.mjs --base https://en.localhost:5290,https://ru.localhost:5290 \
 *     --paths /,/russia,/russia/indicator/cpi,/compare,/world/rating,/germany --runs 3 --label до --out out.json
 *   node scripts/dev/perf-mobile.mjs --base https://forecasteconomy.com --paths / --runs 1   # боевой: не чаще раза в минуту на страницу
 *
 * Параметры:
 *   --base A,B        адреса (через запятую); для каждого свой набор прогонов
 *   --paths a,b,c     пути (по умолчанию / /russia /russia/indicator/cpi /compare /world/rating /germany)
 *   --runs N          холодных прогонов на страницу (3); первый дополняется тёплым
 *   --throttle P      slow4g (по умолчанию) | fast4g | none
 *   --cpu N           замедление процессора (4); 1 — без замедления
 *   --latency MS      задержка сети, мс (150); --down МБИТ (1.6); --up МБИТ (0.75)
 *   --width/--height  окно (390/844)
 *   --human           как у человека: navigator.webdriver=false, поэтому показывается фирменная заставка.
 *                     По умолчанию как у Lighthouse/ботов: заставки нет, виден серверный текст.
 *   --waterfall N     сколько строк водопада печатать для первого прогона (0)
 *   --label TEXT      подпись в отчёте; --out FILE.json — все прогоны; --md FILE — добавить таблицу медиан
 *   --browser PATH    свой Chromium/Chrome вместо кэша playwright; --headed
 *   --settle MS       сколько ждать тишины после загрузки (3000); --max MS  потолок прогона (60000)
 */
import fs from 'node:fs';
import path from 'node:path';
import { createRequire } from 'node:module';
import { fileURLToPath, pathToFileURL } from 'node:url';

async function loadPlaywright() {
  try { return await import('playwright'); } catch { /* ниже */ }
  const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
  const req = createRequire(path.join(root, 'frontend', 'package.json'));
  return import(pathToFileURL(req.resolve('playwright')).href);
}

const args = Object.fromEntries(process.argv.slice(2).reduce((acc, a, i, all) => {
  if (a.startsWith('--')) acc.push([a.slice(2), all[i + 1] && !all[i + 1].startsWith('--') ? all[i + 1] : true]);
  return acc;
}, []));

const BASES = String(args.base || 'https://forecasteconomy.com').split(',').map((s) => s.trim().replace(/\/$/, ''));
const PATHS = String(args.paths || '/,/russia,/russia/indicator/cpi,/compare,/world/rating,/germany').split(',');
const RUNS = Number(args.runs || 3);
const CPU = Number(args.cpu || 4);
const THROTTLE_NAME = String(args.throttle || 'slow4g');
const PRESETS = { slow4g: { down: 1.6, up: 0.75, latency: 150 }, fast4g: { down: 9, up: 9, latency: 60 }, none: null };
const preset = PRESETS[THROTTLE_NAME];
const NET = preset ? {
  latency: Number(args.latency ?? preset.latency),
  down: Number(args.down ?? preset.down),
  up: Number(args.up ?? preset.up),
} : null;
const WIDTH = Number(args.width || 390);
const HEIGHT = Number(args.height || 844);
const HUMAN = Boolean(args.human);
const SETTLE = Number(args.settle || 3000);
const MAX_MS = Number(args.max || 60000);
const LABEL = String(args.label || '');
const EXT_ADDR = `127.0.0.1:${args['ext-port'] || 5290}`;
const UA = 'Mozilla/5.0 (Linux; Android 11; Moto G Power (2022)) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Mobile Safari/537.36';

const median = (a) => {
  const v = a.filter((x) => Number.isFinite(x)).sort((x, y) => x - y);
  if (!v.length) return null;
  const m = v.length >> 1;
  return v.length % 2 ? v[m] : (v[m - 1] + v[m]) / 2;
};

/** Скрипт, который ставится до любого кода страницы: собирает paint/LCP/CLS/долгие задачи. */
const INIT_SCRIPT = `(() => {
  const w = window; w.__perf = { paints: {}, lcp: 0, cls: 0, long: [], shifts: 0 };
  try {
    // момент монтирования приложения и момент, когда SPA стало видимым (html.fe-js)
    let mounted; Object.defineProperty(w, '__feAppMounted', { configurable: true, get() { return mounted; }, set(v) { mounted = v; w.__perf.mountedAt = performance.now(); } });
    new MutationObserver(() => { const root = document.documentElement; if (root && root.classList.contains('fe-js') && !w.__perf.revealAt) w.__perf.revealAt = performance.now(); })
      .observe(document, { attributes: true, subtree: true, attributeFilter: ['class'] });
  } catch (e) {}
  try {
    new PerformanceObserver((l) => { for (const e of l.getEntries()) w.__perf.paints[e.name] = e.startTime; })
      .observe({ type: 'paint', buffered: true });
    new PerformanceObserver((l) => { for (const e of l.getEntries()) { w.__perf.lcp = e.startTime; const el = e.element; w.__perf.lcpInfo = { tag: el && el.tagName, cls: el ? String(el.className && el.className.baseVal !== undefined ? el.className.baseVal : el.className || '').slice(0, 70) : '', url: (e.url || '').slice(-60), size: e.size, text: el && el.textContent ? el.textContent.trim().slice(0, 40) : '' }; } })
      .observe({ type: 'largest-contentful-paint', buffered: true });
    new PerformanceObserver((l) => { for (const e of l.getEntries()) if (!e.hadRecentInput) { w.__perf.cls += e.value; w.__perf.shifts++; } })
      .observe({ type: 'layout-shift', buffered: true });
    new PerformanceObserver((l) => { for (const e of l.getEntries()) w.__perf.long.push([e.startTime, e.duration]); })
      .observe({ type: 'longtask', buffered: true });
  } catch (e) {}
})();`;

const HUMAN_SCRIPT = 'Object.defineProperty(Navigator.prototype, "webdriver", { get: () => false });';

/** Гистограмма кадра (в браузере-помощнике): RGB по 64 корзины на канал. */
async function frameHistograms(helper, jpegs) {
  return helper.evaluate(async (list) => {
    const out = [];
    for (const b64 of list) {
      const blob = await (await fetch(`data:image/jpeg;base64,${b64}`)).blob();
      const bmp = await createImageBitmap(blob);
      const c = new OffscreenCanvas(bmp.width, bmp.height);
      const ctx = c.getContext('2d');
      ctx.drawImage(bmp, 0, 0);
      const d = ctx.getImageData(0, 0, bmp.width, bmp.height).data;
      const h = new Float64Array(192);
      const n = d.length / 4;
      for (let i = 0; i < d.length; i += 4) {
        h[d[i] >> 2] += 1; h[64 + (d[i + 1] >> 2)] += 1; h[128 + (d[i + 2] >> 2)] += 1;
      }
      for (let i = 0; i < 192; i++) h[i] /= n;
      out.push(Array.from(h));
    }
    return out;
  }, jpegs);
}

function speedIndex(frames, hists, endMs) {
  // frames: [{t}], hists: гистограммы; белый лист как кадр 0 (t = 0)
  if (!frames.length) return null;
  const white = new Array(192).fill(0);
  for (let c = 0; c < 3; c++) white[c * 64 + 63] = 1;
  const final = hists[hists.length - 1];
  const dist = (a, b) => a.reduce((s, v, i) => s + Math.abs(v - b[i]), 0);
  const base = dist(white, final) || 1;
  const prog = hists.map((h) => Math.max(0, Math.min(1, 1 - dist(h, final) / base)));
  let si = 0;
  let prevT = 0;
  let prevP = 0;
  frames.forEach((f, i) => {
    si += (f.t - prevT) * (1 - prevP);
    prevT = f.t; prevP = prog[i];
  });
  si += Math.max(0, endMs - prevT) * (1 - prevP) * 0; // после последнего изменения вклад нулевой
  const complete = (q) => { const k = prog.findIndex((p) => p >= q); return k < 0 ? null : frames[k].t; };
  return { si, firstPaint: frames[0].t, vc85: complete(0.85), vc95: complete(0.95), lastChange: frames[frames.length - 1].t, frames: frames.length };
}

function computeTti(fcp, longTasks, reqs, endObserved) {
  // Окно 5 с без долгих задач и с ≤ 2 запросами в полёте; кандидат — FCP или конец очередной долгой задачи после FCP.
  const cands = [fcp, ...longTasks.filter(([s, d]) => s + d > fcp).map(([s, d]) => s + d)];
  const inflightMax = (a, b) => {
    const ev = [];
    reqs.forEach((r) => { if (r.end != null && r.end > a && r.start < b) { ev.push([Math.max(r.start, a), 1], [Math.min(r.end, b), -1]); } });
    ev.sort((x, y) => x[0] - y[0] || x[1] - y[1]);
    let cur = 0; let mx = 0;
    ev.forEach(([, k]) => { cur += k; mx = Math.max(mx, cur); });
    return mx;
  };
  for (const t of cands) {
    if (t + 5000 > endObserved) return null; // не хватило наблюдения
    const clash = longTasks.some(([s, d]) => s < t + 5000 && s + d > t);
    if (clash) continue;
    if (inflightMax(t, t + 5000) > 2) continue;
    return t;
  }
  return null;
}

async function measure(ctx, helper, url) {
  const page = await ctx.newPage();
  const cdp = await ctx.newCDPSession(page);
  await cdp.send('Network.enable');
  await cdp.send('Page.enable');
  await cdp.send('Network.setCacheDisabled', { cacheDisabled: false });
  if (NET) {
    await cdp.send('Network.emulateNetworkConditions', {
      offline: false, latency: NET.latency,
      downloadThroughput: (NET.down * 1e6) / 8, uploadThroughput: (NET.up * 1e6) / 8,
    });
  }
  if (CPU > 1) await cdp.send('Emulation.setCPUThrottlingRate', { rate: CPU });

  const reqs = new Map();
  let wall0 = null; let ts0 = null;
  cdp.on('Network.requestWillBeSent', (e) => {
    if (wall0 == null) { wall0 = e.wallTime; ts0 = e.timestamp; }
    if (e.request.url.startsWith('data:')) return;
    const r = { id: e.requestId, url: e.request.url, type: e.type, start: (e.timestamp - ts0) * 1000, end: null, bytes: 0, status: 0, prio: e.request.initialPriority, fromCache: false };
    // редирект переиспользует requestId
    if (reqs.has(e.requestId) && e.redirectResponse) { const old = reqs.get(e.requestId); old.end = r.start; reqs.set(`${e.requestId}#r${reqs.size}`, old); }
    reqs.set(e.requestId, r);
  });
  cdp.on('Network.responseReceived', (e) => { const r = reqs.get(e.requestId); if (r) { r.status = e.response.status; r.fromCache = Boolean(e.response.fromDiskCache || e.response.fromServiceWorker); r.resType = e.response.mimeType; } });
  cdp.on('Network.loadingFinished', (e) => { const r = reqs.get(e.requestId); if (r) { r.end = (e.timestamp - ts0) * 1000; r.bytes = e.encodedDataLength; } });
  cdp.on('Network.loadingFailed', (e) => { const r = reqs.get(e.requestId); if (r) { r.end = (e.timestamp - ts0) * 1000; r.failed = e.errorText; } });

  // кадры экрана
  const rawFrames = [];
  cdp.on('Page.screencastFrame', (e) => {
    rawFrames.push({ wall: e.metadata.timestamp * 1000, data: e.data });
    cdp.send('Page.screencastFrameAck', { sessionId: e.sessionId }).catch(() => {});
  });
  await cdp.send('Page.startScreencast', { format: 'jpeg', quality: 35, maxWidth: 195, maxHeight: 422, everyNthFrame: 1 });

  // зонд отзывчивости главного потока
  const probes = [];
  let probing = true;
  const probeLoop = (async () => {
    while (probing) {
      const t0 = Date.now();
      try { await cdp.send('Runtime.evaluate', { expression: '1' }); probes.push([t0, Date.now() - t0]); } catch { /* страница меняется */ }
      await new Promise((r) => setTimeout(r, 120));
    }
  })();

  const navStartWall = Date.now();
  let loadAt = null;
  page.once('load', () => { loadAt = Date.now() - navStartWall; });
  let navError = null;
  try { await page.goto(url, { waitUntil: 'commit', timeout: 45000 }); } catch (e) { navError = String(e.message || e).split('\n')[0]; }

  // ждём загрузки и тишины
  const startWait = Date.now();
  let lastActivity = Date.now();
  let lastCount = 0;
  while (Date.now() - startWait < MAX_MS) {
    await new Promise((r) => setTimeout(r, 250));
    const open = [...reqs.values()].filter((r) => r.end == null).length;
    const n = reqs.size;
    if (open > 0 || n !== lastCount) lastActivity = Date.now();
    lastCount = n;
    const cleared = loadAt != null && Date.now() - lastActivity > SETTLE;
    // TTI требует ещё 5 с спокойствия после FCP — наблюдаем минимум 6 с после загрузки
    if (cleared && Date.now() - navStartWall > (loadAt || 0) + 6000) break;
  }
  const endObserved = Date.now() - navStartWall;
  probing = false;
  await probeLoop;
  await cdp.send('Page.stopScreencast').catch(() => {});

  let perf = null; let nav = null; let timeOrigin = null;
  try {
    perf = await page.evaluate(() => window.__perf);
    nav = await page.evaluate(() => {
      const n = performance.getEntriesByType('navigation')[0];
      return n ? { responseStart: n.responseStart, domContentLoaded: n.domContentLoadedEventEnd, load: n.loadEventEnd, responseEnd: n.responseEnd, transferSize: n.transferSize } : null;
    });
    timeOrigin = await page.evaluate(() => performance.timeOrigin);
    perf.mounted = await page.evaluate(() => Boolean(window.__feAppMounted));
    perf.bodyText = await page.evaluate(() => document.body.innerText.length);
  } catch (e) { navError = navError || String(e.message || e).split('\n')[0]; }
  await page.close().catch(() => {});

  // Приведение времён к началу навигации. Сетевые времена отсчитаны от первого запроса ≈ началу навигации.
  const offset = (wall0 != null && timeOrigin != null) ? wall0 * 1000 - timeOrigin : 0; // сетевое время + offset = время страницы
  const reqList = [...reqs.values()].map((r) => ({ ...r, start: r.start + offset, end: r.end == null ? null : r.end + offset }));
  const fcp = perf?.paints?.['first-contentful-paint'] ?? null;
  const long = (perf?.long || []).sort((a, b) => a[0] - b[0]);
  const tti = fcp != null ? computeTti(fcp, long, reqList, endObserved) : null;
  const tbtEnd = tti ?? endObserved;
  const tbt = fcp != null ? long.reduce((s, [st, d]) => (st + d > fcp && st < tbtEnd ? s + Math.max(0, d - 50) : s), 0) : null;

  let responsive = null;
  if (fcp != null && timeOrigin != null) {
    const pr = probes.map(([t, l]) => [t - timeOrigin, l]);
    for (let i = 0; i < pr.length; i++) {
      if (pr[i][0] < fcp) continue;
      const win = pr.filter(([t]) => t >= pr[i][0] && t <= pr[i][0] + 1000);
      if (win.length >= 3 && win.every(([, l]) => l < 100) && pr[i][0] + 1000 <= pr[pr.length - 1][0]) { responsive = pr[i][0]; break; }
    }
  }

  let si = null;
  if (rawFrames.length && timeOrigin != null) {
    const frames = rawFrames.map((f) => ({ t: f.wall - timeOrigin }));
    const hists = await frameHistograms(helper, rawFrames.map((f) => f.data));
    si = speedIndex(frames, hists, endObserved);
  }

  const jsBytes = (cut) => reqList.filter((r) => /script|javascript/i.test(r.resType || '') || r.type === 'Script').filter((r) => r.end != null && (cut == null || r.end <= cut)).reduce((s, r) => s + r.bytes, 0);
  const loadMs = nav?.load > 0 ? nav.load : loadAt;
  return {
    url,
    error: navError,
    ttfb: nav?.responseStart ?? null,
    fcp,
    lcp: perf?.lcp || null,
    lcpInfo: perf?.lcpInfo || null,
    speedIndex: si?.si ?? null,
    vc95: si?.vc95 ?? null,
    firstFrame: si?.firstPaint ?? null,
    lastVisualChange: si?.lastChange ?? null,
    tbt,
    tti,
    responsive,
    cls: perf?.cls ?? null,
    mountedAt: perf?.mountedAt ?? null,
    revealAt: perf?.revealAt ?? null,
    longTasks: long.length,
    longTaskMs: Math.round(long.reduce((s, [, d]) => s + d, 0)),
    loadMs,
    requests: reqList.length,
    transferKB: Math.round(reqList.reduce((s, r) => s + r.bytes, 0) / 1024),
    jsKBatFcp: fcp != null ? Math.round(jsBytes(fcp) / 1024) : null,
    jsKBatLoad: loadMs != null ? Math.round(jsBytes(loadMs) / 1024) : null,
    jsKB: Math.round(jsBytes(null) / 1024),
    apiRequests: reqList.filter((r) => /\/api\//.test(r.url)).length,
    mounted: perf?.mounted ?? null,
    bodyText: perf?.bodyText ?? null,
    waterfall: reqList.sort((a, b) => a.start - b.start).map((r) => ({
      url: r.url.replace(/^https?:\/\/[^/]+/, ''), type: r.type, start: Math.round(r.start), end: r.end == null ? null : Math.round(r.end),
      kb: +(r.bytes / 1024).toFixed(1), status: r.status, prio: r.prio, cache: r.fromCache || undefined,
    })),
  };
}

const { chromium } = await loadPlaywright().then((m) => (m.chromium ? m : m.default));
const browser = await chromium.launch({
  headless: !args.headed,
  executablePath: args.browser && args.browser !== true ? String(args.browser) : undefined,
  // Чужие хосты (Метрика и т.п.) ведём на стенд perf-serve.mjs: вес и исполнение настоящие, хитов в настоящий счётчик нет.
  args: ['--ignore-certificate-errors', `--host-resolver-rules=MAP *.localhost 127.0.0.1, MAP *.yandex.ru ${EXT_ADDR}, MAP *.yandex.com ${EXT_ADDR}, MAP yastatic.net ${EXT_ADDR}, MAP mc.webvisor.com ${EXT_ADDR}, MAP *.webvisor.com ${EXT_ADDR}`, '--disable-background-timer-throttling', '--disable-renderer-backgrounding'],
});
const helperCtx = await browser.newContext();
const helper = await helperCtx.newPage();

async function newCtx() {
  const ctx = await browser.newContext({
    viewport: { width: WIDTH, height: HEIGHT }, deviceScaleFactor: 2, isMobile: true, hasTouch: true, userAgent: UA,
    ignoreHTTPSErrors: true, locale: 'en-US',
  });
  await ctx.addInitScript(INIT_SCRIPT);
  if (HUMAN) await ctx.addInitScript(HUMAN_SCRIPT);
  return ctx;
}

const all = [];
for (const base of BASES) {
  for (const p of PATHS) {
    const url = base + p;
    const runs = [];
    for (let i = 0; i < RUNS; i++) {
      const ctx = await newCtx();
      const r = await measure(ctx, helper, url);
      r.kind = 'cold'; r.run = i + 1;
      runs.push(r);
      if (i === 0) {
        await new Promise((res) => setTimeout(res, 500));
        const w = await measure(ctx, helper, url);
        w.kind = 'warm'; w.run = 1;
        runs.push(w);
      }
      await ctx.close();
      process.stderr.write(`  ${url} ${r.kind}#${r.run}: fcp=${Math.round(r.fcp ?? -1)} lcp=${Math.round(r.lcp ?? -1)} si=${Math.round(r.speedIndex ?? -1)} tti=${Math.round(r.tti ?? -1)} tbt=${Math.round(r.tbt ?? -1)} req=${r.requests} kb=${r.transferKB}\n`);
    }
    all.push({ base, path: p, label: LABEL, runs });
  }
}
await browser.close();

if (args.out) fs.writeFileSync(path.resolve(String(args.out)), JSON.stringify({ label: LABEL, config: { cpu: CPU, throttle: THROTTLE_NAME, net: NET, width: WIDTH, height: HEIGHT, human: HUMAN, runs: RUNS }, results: all }, null, 1));

const fmt = (v, d = 0) => (v == null ? '—' : d ? v.toFixed(d) : String(Math.round(v)));
const lines = [];
lines.push(`### ${LABEL || 'замер'} · ${THROTTLE_NAME}${NET ? ` (${NET.down} Мбит/с, ${NET.latency} мс)` : ''} · CPU ×${CPU} · ${WIDTH}×${HEIGHT}${HUMAN ? ' · с заставкой' : ''}`);
lines.push('');
lines.push('| страница | кэш | TTFB | FCP | LCP | SI | TBT | TTI | SPA готово | CLS | запросов | КБ | JS до FCP | JS всего |');
lines.push('|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|');
for (const g of all) {
  for (const kind of ['cold', 'warm']) {
    const rs = g.runs.filter((r) => r.kind === kind);
    if (!rs.length) continue;
    const m = (k) => median(rs.map((r) => r[k]));
    lines.push(`| ${g.base.replace(/^https?:\/\//, '')}${g.path} | ${kind === 'cold' ? `холодный (${rs.length})` : 'тёплый'} | ${fmt(m('ttfb'))} | ${fmt(m('fcp'))} | ${fmt(m('lcp'))} | ${fmt(m('speedIndex'))} | ${fmt(m('tbt'))} | ${fmt(m('tti'))} | ${fmt(m('revealAt'))} | ${fmt(m('cls'), 3)} | ${fmt(m('requests'))} | ${fmt(m('transferKB'))} | ${fmt(m('jsKBatFcp'))} | ${fmt(m('jsKB'))} |`);
  }
}
const text = lines.join('\n');
console.log(text);
if (args.md) fs.appendFileSync(path.resolve(String(args.md)), `\n${text}\n`);
const WF = Number(args.waterfall || 0);
if (WF > 0) {
  for (const g of all) {
    const r = g.runs[0];
    console.log(`\nВодопад ${g.base}${g.path} (холодный #1), первые ${WF}:`);
    r.waterfall.slice(0, WF).forEach((w) => console.log(`${String(w.start).padStart(6)} → ${String(w.end ?? '…').padStart(6)}  ${String(w.kb).padStart(7)} КБ  ${String(w.type).padEnd(10)} ${w.prio || ''}  ${w.url.slice(0, 90)}`));
  }
}
