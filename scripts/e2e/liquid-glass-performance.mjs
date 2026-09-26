/** Bounded local lab measurements. Run alone, outside the paced QA matrix.
 * Cold browser contexts, warm local server; no network throttling or field claim.
 */
import { createRequire } from 'node:module';
import fs from 'node:fs';
const require = createRequire(new URL('../../frontend/package.json', import.meta.url));
const { chromium } = require('playwright');
const base = 'http://127.0.0.1:3000';
const args = Object.fromEntries(process.argv.slice(2).map(arg => arg.replace(/^--/, '').split('=')));
const report = { at: new Date().toISOString(), environment: 'Local MacBook; cold browser context; server cache uncontrolled; no network throttle; optional third-party requests blocked', limitations: 'One run per case, not field Core Web Vitals, not production network latency, no INP claim', cases: [] };
const browser = await chromium.launch({ headless: true });
try {
  for (const [name, path, width] of [['home-mobile', '/', 390], ['fast-year-mobile', '/russia/indicator/cpi/2025', 390], ['indicator-mobile', '/russia/indicator/cpi', 390], ['world-desktop', '/germany', 1440]]) {
    if (args.case && args.case !== name) continue;
    const context = await browser.newContext({ viewport: { width, height: 900 }, serviceWorkers: 'block' });
    await context.route('**/*', route => new URL(route.request().url()).origin === base ? route.continue() : route.abort());
    const page = await context.newPage();
    await page.addInitScript(() => {
      window.__localVitals = { lcp: null, shifts: [], longTasks: [] };
      new PerformanceObserver(list => { for (const e of list.getEntries()) window.__localVitals.lcp = { ms: e.startTime, size: e.size, element: e.element?.tagName, text: e.element?.textContent?.slice(0,120), url: e.url }; }).observe({ type: 'largest-contentful-paint', buffered: true });
      new PerformanceObserver(list => { for (const e of list.getEntries()) if (!e.hadRecentInput) window.__localVitals.shifts.push({ time: e.startTime, value: e.value, sources: (e.sources || []).map(s => ({ tag: s.node?.tagName, id: s.node?.id, className: s.node?.className, text: s.node?.textContent?.slice(0,120), previousRect: s.previousRect.toJSON(), currentRect: s.currentRect.toJSON() })) }); }).observe({ type: 'layout-shift', buffered: true });
      new PerformanceObserver(list => { for (const e of list.getEntries()) window.__localVitals.longTasks.push({ ms: e.duration, at: e.startTime }); }).observe({ type: 'longtask', buffered: true });
    });
    const errors = [], badResponses = [], expectedResponses = [];
    page.on('pageerror', e => errors.push(e.message));
    page.on('response', r => { if (r.status() >= 400 && r.url().startsWith(base)) {
      const target = r.status() === 401 && new URL(r.url()).pathname === '/api/v1/auth/me' ? expectedResponses : badResponses;
      target.push({ status: r.status(), url: r.url() });
    } });
    await page.goto(base + path, { waitUntil: 'load', timeout: 30000 });
    await page.waitForTimeout(8000);
    const measurement = await page.evaluate(() => {
      const nav = performance.getEntriesByType('navigation')[0];
      const v = window.__localVitals;
      let max = 0, current = 0, start = 0, prev = null;
      for (const shift of v.shifts) {
        if (prev === null || shift.time - prev > 1000 || shift.time - start > 5000) { start = shift.time; current = 0; }
        current += shift.value; prev = shift.time; max = Math.max(max, current);
      }
      const resources = performance.getEntriesByType('resource');
      return { ttfbMs: nav.responseStart, domContentLoadedMs: nav.domContentLoadedEventEnd, lcp: v.lcp, clsSessionMax: max, longTaskCount: v.longTasks.length, longTaskTotalMs: v.longTasks.reduce((s,e)=>s+e.ms,0), resources: resources.length, transferBytes: resources.reduce((s,e)=>s+e.transferSize,nav.transferSize), encodedBytes: resources.reduce((s,e)=>s+e.encodedBodySize,nav.encodedBodySize), largestResources: resources.sort((a,b)=>b.encodedBodySize-a.encodedBodySize).slice(0,6).map(e=>({path:new URL(e.name).pathname,bytes:e.encodedBodySize})) };
    });
    const shifts = await page.evaluate(() => window.__localVitals.shifts);
    report.cases.push({ name, path, width, ...measurement, shifts, errors, badResponses, expectedResponses });
    console.log(name, JSON.stringify({ lcpMs: measurement.lcp?.ms, cls: measurement.clsSessionMax, transferBytes: measurement.transferBytes, errors }));
    await context.close();
  }
} finally { await browser.close(); }
fs.mkdirSync('docs/design/local-acceptance', { recursive: true });
fs.writeFileSync(`docs/design/local-acceptance/${args.output || 'performance-lab'}.json`, JSON.stringify(report, null, 2)+'\n');
