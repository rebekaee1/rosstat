/** Local, read-only acceptance of the complete compose entrypoint.
 * node scripts/e2e/liquid-glass-acceptance.mjs --mode=http --stage=baseline
 * node scripts/e2e/liquid-glass-acceptance.mjs --mode=browser --tier=matrix --stage=after-build
 * --engines=chromium,webkit,firefox --only=national-year,world-year --locales=ru,en
 * Matrix: Chromium every family at 390/1440 + representative boundary widths;
 * WebKit/Firefox representative families at 390/1440. Fresh context every page.
 * No deployment, rebuild, ingest, external-provider requests or cookie preseed.
 */
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import fs from 'node:fs';
import { execFileSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import { cases, widths, apiCases } from './liquid-glass-cases.mjs';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const require = createRequire(path.join(root, 'frontend/package.json'));
const engines = require('playwright');
const args = Object.fromEntries(process.argv.slice(2).map(s => s.replace(/^--/, '').split('=')));
const base = args.base || 'http://127.0.0.1:3000';
if (!['127.0.0.1', 'localhost', '[::1]'].includes(new URL(base).hostname)) throw Error('Local loopback entrypoint required');
const mode = args.mode || 'all', tier = args.tier || 'smoke', stage = (args.stage || 'local').replace(/[^\w-]/g, '_');
const out = path.join(root, 'output/design-acceptance/results', stage);
fs.mkdirSync(out, { recursive: true });
const shots = path.join(root, 'output/design-acceptance/2026-09-24', stage);
fs.mkdirSync(shots, { recursive: true });
const picked = cases.filter(c => !args.only || args.only.split(',').includes(c.id));
const locales = (args.locales || 'ru,en').split(',');
const report = { at: new Date().toISOString(), base, mode, tier, stage, head: execFileSync('git', ['rev-parse', 'HEAD'], { cwd: root, encoding: 'utf8' }).trim(), http: [], api: [], browser: [], inventory: null, issues: [], limitations: ['Family sampling, not a crawl of every public URL.', 'Desktop engines with emulated viewports, not physical devices.', 'API/image requests are intentionally paced: run durations and request latency are not performance evidence.', 'EN preview intentionally noindex; production host cutover is not changed.', 'Git HEAD identifies the working checkout, not the deployed compose image; response hashes and asset paths identify observed content.'] };
const issue = (kind, id, detail) => report.issues.push({ kind, id, detail });
const save = () => fs.writeFileSync(path.join(out, `${mode}.json`), JSON.stringify(report, null, 2) + '\n');
const localUrl = (p, locale) => { const u = new URL(p, base); if (locale === 'en') u.searchParams.set('preview_locale', 'en'); return u.href; };
const siteHost = h => /(^|\.)forecasteconomy\.com$/.test(h);
const localize = (raw, locale) => { const u = new URL(raw, base); if (siteHost(u.hostname)) { u.protocol = new URL(base).protocol; u.host = new URL(base).host; } return localUrl(u.href, locale); };

// Keep the read-only inventory separate from materialized sitemap artifact counts.
if (args.inventory !== 'false') {
  try {
    const sql = `BEGIN READ ONLY; SET LOCAL statement_timeout='10s';
SELECT json_build_object('subnational_regions',(SELECT count(*) FROM subnational_regions),'subnational_indicators',(SELECT count(*) FROM subnational_indicators),'subnational_points',(SELECT count(*) FROM subnational_data_points),'active_countries',(SELECT count(*) FROM world_countries WHERE is_active),'listed_world_series',(SELECT count(*) FROM world_indicators WHERE is_listed),'all_world_series',(SELECT count(*) FROM world_indicators)); ROLLBACK;`;
    const text = execFileSync('docker', ['compose', 'exec', '-T', 'postgres', 'psql', '-U', 'rustats', '-d', 'rustats', '-X', '-q', '-A', '-t'], { cwd: root, input: sql, encoding: 'utf8', timeout: 15000 });
    report.inventory = JSON.parse(text.trim());
    if (!report.inventory.subnational_points) issue('data-unavailable', 'us-subnational', 'Local subnational tables contain no observations; US content acceptance is blocked by fixture availability.');
  } catch (e) { report.inventory = { error: e.message.split('\n')[0] }; }
}
const request = await engines.request.newContext({ timeout: 15000, ignoreHTTPSErrors: false });
// Respect nginx's strict 2 requests/sec budget instead of treating a burst as a product defect.
let lastRequest = 0;
const mediaCache = new Map();
async function get(url, options = {}) {
  const wait = 900 - (Date.now() - lastRequest);
  if (wait > 0) await new Promise(r => setTimeout(r, wait));
  lastRequest = Date.now();
  let response = await request.get(url, options);
  for (let n = 0; response.status() === 429 && n < 2; n++) {
    await new Promise(r => setTimeout(r, 2500));
    lastRequest = Date.now(); response = await request.get(url, options);
  }
  return response;
}
try {
  const r = await get(base + '/sitemap-stats.json');
  const s = await r.json(), groups = {};
  for (const [k, v] of Object.entries(s.sections || {})) { const g = k.replace(/-\d+$/, ''); groups[g] = (groups[g] || 0) + v; }
  report.sitemap = { status: r.status(), builtAt: s.built_at, urlsTotal: s.urls_total, publishedUrlsTotal: s.published_urls_total, hosts: Object.keys(s.hosts || {}), groups };
} catch (e) { report.sitemap = { error: e.message.split('\n')[0] }; }

if (mode !== 'browser') {
  const browser = await engines.chromium.launch({ headless: true });
  const parser = await browser.newPage();
  const targets = new Map();
  for (const c of picked) for (const locale of locales) {
    const row = { id: c.id, family: c.family, locale, url: localUrl(c.path, locale), expected: c.status };
    try {
      const response = await get(row.url, { maxRedirects: 0 });
      row.status = response.status(); row.contentType = response.headers()['content-type']; row.location = response.headers().location;
      const raw = await response.text();
      row.bytes = Buffer.byteLength(raw);
      row.sha256 = createHash('sha256').update(raw).digest('hex');
      if (row.contentType?.includes('html')) row.document = await parser.evaluate(html => {
        const d = new DOMParser().parseFromString(html, 'text/html');
        const meta = n => d.querySelector(`meta[name="${n}"],meta[property="${n}"]`)?.content || null;
        const ld = [...d.querySelectorAll('script[type="application/ld+json"]')].flatMap(s => { try { const x = JSON.parse(s.textContent); return Array.isArray(x) ? x : x['@graph'] || [x]; } catch { return [{ invalidJSON: true }]; } });
        const imgs = [...d.querySelectorAll('img')].map(i => ({ src: i.getAttribute('src'), sources: [i.getAttribute('srcset'), ...[...(i.closest('picture')?.querySelectorAll('source[srcset]') || [])].map(s => s.getAttribute('srcset'))].filter(Boolean), alt: i.getAttribute('alt'), width: i.getAttribute('width'), height: i.getAttribute('height'), chart: !!i.closest('figure, .seo-chart, .seo-fast-chart, .seo-visual') }));
        const links = [...d.querySelectorAll('a[href]')].map(a => ({ href: a.getAttribute('href'), text: a.textContent.trim().slice(0, 80), inMain: !!a.closest('main,article,.seo-content') }));
        return { lang: d.documentElement.lang, title: d.title, h1: [...d.querySelectorAll('h1')].map(x => x.textContent.trim()), canonical: d.querySelector('link[rel="canonical"]')?.getAttribute('href'), hreflang: [...d.querySelectorAll('link[hreflang]')].map(x => ({ lang: x.hreflang, href: x.href })), robots: meta('robots'), ogImage: meta('og:image'), ogLocale: meta('og:locale'), ldTypes: ld.map(x => x['@type']), imageObjects: ld.filter(x => x['@type'] === 'ImageObject'), invalidLd: ld.some(x => x.invalidJSON), imgs, links, seoFast: !!d.querySelector('.seo-fast'), hasRoot: !!d.querySelector('#root'), hasModule: !!d.querySelector('script[type=module]') };
      }, raw);
      if (c.subnational && report.inventory?.subnational_points === 0) row.dataAcceptance = 'unavailable';
      else if (row.status !== c.status) issue('http-status', `${c.id}:${locale}`, `${row.status}; expected ${c.status}; location=${row.location || ''}`);
      const d = row.document;
      if (d && row.status === 200) {
        if (d.lang !== locale) issue('locale', `${c.id}:${locale}`, `html lang=${d.lang}`);
        if (!d.h1.length || !d.canonical) issue('seo-document', `${c.id}:${locale}`, 'Missing h1 or canonical');
        if (locale === 'en' && !d.robots?.includes('noindex')) issue('preview-indexable', c.id, d.robots);
        if (locale === 'ru' && d.robots?.includes('noindex')) issue('unexpected-noindex', c.id, d.robots);
        if (d.canonical?.includes('preview_locale')) issue('canonical-preview', c.id, d.canonical);
        if (d.invalidLd) issue('invalid-jsonld', c.id, 'JSON parse error');
        if (d.seoFast) {
          // Owner rule applies to every clickable fast-page anchor, including
          // source/footer links. External provenance in JSON-LD is unaffected.
          row.fastLinkAudit = { checked: d.links.length, external: [], wrongRussia: [] };
          for (const link of d.links) {
            let target;
            try { target = new URL(link.href, row.url); }
            catch { row.fastLinkAudit.external.push(link); continue; }
            if (!['http:', 'https:'].includes(target.protocol) || !(siteHost(target.hostname) || target.origin === new URL(base).origin)) row.fastLinkAudit.external.push(link);
            if (link.text.trim().toLocaleLowerCase('ru') === 'россия' && target.pathname.replace(/\/$/, '') !== '/russia/region') row.fastLinkAudit.wrongRussia.push(link);
          }
          if (row.fastLinkAudit.external.length) issue('fast-link-external', `${c.id}:${locale}`, row.fastLinkAudit.external);
          if (row.fastLinkAudit.wrongRussia.length) issue('fast-russia-target', `${c.id}:${locale}`, row.fastLinkAudit.wrongRussia);
          if (locale === 'en') {
            // Check the native visible markup before localize can supply any
            // test locale. Metadata/canonical/provenance URLs remain clean.
            const bodyUrls = [
              ...d.links.map(l => ({ kind: 'anchor', url: l.href })),
              ...d.imgs.flatMap(i => [{ kind: 'img', url: i.src }, ...i.sources.filter(s => !s.includes('data:')).flatMap(s => s.split(',').map(v => ({ kind: 'srcset', url: v.trim().split(/\s+/)[0] })))]),
            ].filter(v => v.url);
            row.previewBodyAudit = { checked: 0, missingLocale: [] };
            for (const item of bodyUrls) {
              const target = new URL(item.url, row.url);
              if (!['http:', 'https:'].includes(target.protocol) || !(siteHost(target.hostname) || target.origin === new URL(base).origin)) continue;
              row.previewBodyAudit.checked++;
              if (target.searchParams.get('preview_locale') !== 'en') row.previewBodyAudit.missingLocale.push(item);
            }
            if (row.previewBodyAudit.missingLocale.length) issue('preview-body-locale', `${c.id}:${locale}`, row.previewBodyAudit.missingLocale);
          }
        }
        if (c.image && (!d.ogImage || !d.imageObjects.length || !d.imgs.some(i => i.chart && i.alt))) issue('image-wiring', `${c.id}:${locale}`, { ogImage: d.ogImage, imageObjects: d.imageObjects.length, chartImgs: d.imgs.filter(i => i.chart) });
        const media = [d.ogImage, ...d.imgs.filter(i => i.chart).flatMap(i => [i.src, ...i.sources.flatMap(s => s.split(',').map(x => x.trim().split(/\s+/)[0]))])].filter(Boolean);
        row.media = [];
        const seen = new Set();
        for (const u of new Set(media)) {
          const local = localize(u, locale);
          if (new URL(local).origin !== new URL(base).origin || seen.has(local)) continue;
          seen.add(local);
          if (mediaCache.has(local)) { row.media.push(mediaCache.get(local)); continue; }
          const r = await get(local, { maxRedirects: 0 }); const b = await r.body();
          const item = { original: u, local, status: r.status(), type: r.headers()['content-type'], bytes: b.length, sha256: createHash('sha256').update(b).digest('hex') };
          if (b.length > 24 && b.subarray(1, 4).toString() === 'PNG') { item.width = b.readUInt32BE(16); item.height = b.readUInt32BE(20); }
          row.media.push(item);
          mediaCache.set(local, item);
          if (item.status !== 200 || !item.type?.startsWith('image/')) issue('broken-image', `${c.id}:${locale}`, item);
          if (new URL(local).searchParams.get('portrait') && (item.width !== 1080 || item.height !== 1350)) issue('portrait-dimensions', `${c.id}:${locale}`, item);
        }
        // Resolve bounded, useful continuation links locally. Never follow source/provider links.
        const mainLinks = d.links.filter(x => x.inMain);
        const priority = [
          ...mainLinks.filter(x => x.href.includes('#chart') || /откр|подроб|истори|интерактив|сравн|полный|open|explore|history|compare|full/i.test(x.text)),
          ...mainLinks.filter(x => x.href.split('?')[0] === c.path.replace(/\/(?!9999)[1-9][0-9]{3}(?:-\d{2})?$/, '')),
          ...mainLinks.filter(x => /\/(?!9999)[1-9][0-9]{3}(?:-\d{2})?$/.test(x.href)),
        ];
        for (const x of priority.slice(0, 3)) {
          if (x.href.startsWith('#')) continue;
          const u = new URL(x.href, base);
          if (!(u.origin === new URL(base).origin || siteHost(u.hostname))) continue;
          const local = localize(x.href, locale);
          if (!targets.has(local)) targets.set(local, { url: local, href: x.href, from: c.id, text: x.text });
        }
      }
    } catch (e) { row.error = e.message.split('\n')[0]; issue('request-error', `${c.id}:${locale}`, row.error); }
    report.http.push(row); save();
    console.log(`HTTP ${c.id} ${locale}: ${row.status || row.error}`);
    await new Promise(r => setTimeout(r, 110));
  }
  report.continuations = [];
  for (const t of args.continuations === 'false' ? [] : [...targets.values()].slice(0, 50)) {
    try {
      let current = t.url;
      const visited = new Set();
      t.chain = [];
      for (let hop = 0; hop < 5; hop++) {
        // Fragments never reach the server, so they cannot break a redirect cycle.
        const key = new URL(current); key.hash = '';
        if (visited.has(key.href)) { issue('continuation-redirect-loop', t.from, t.chain); break; }
        visited.add(key.href);
        const r = await get(current, { maxRedirects: 0 });
        t.status = r.status(); t.location = r.headers().location;
        t.chain.push({ url: current, status: t.status, location: t.location });
        if (t.status >= 400) { issue('broken-continuation', t.from, t); break; }
        if (t.status < 300 || t.status >= 400 || !t.location) break;
        current = localize(new URL(t.location, current).href, new URL(t.url).searchParams.get('preview_locale') || 'ru');
        if (hop === 4) issue('continuation-too-many-redirects', t.from, t.chain);
      }
    }
    catch (e) { t.error = e.message.split('\n')[0]; }
    report.continuations.push(t);
  }
  for (const c of args.api === 'false' ? [] : apiCases) for (const locale of locales) {
    if (c.subnational && report.inventory?.subnational_points === 0) continue;
    const row = { id: c.id, locale, url: localUrl(c.path, locale) };
    try {
      const r = await get(row.url); row.status = r.status();
      const data = await r.json(); const points = data[c.points];
      row.count = Array.isArray(points) ? points.length : 0;
      row.first = points?.[0]; row.last = points?.at(-1);
      row.unit = data.unit || data.indicator?.unit;
      if (row.status !== 200 || row.count < c.min) issue('api-data', `${c.id}:${locale}`, { status: row.status, count: row.count, minimum: c.min });
      if (Array.isArray(points) && points.some(p => p.value != null && !Number.isFinite(p.value))) issue('api-value', `${c.id}:${locale}`, 'Non-finite/non-numeric observed value');
    } catch (e) { row.error = e.message.split('\n')[0]; issue('api-error', `${c.id}:${locale}`, row.error); }
    report.api.push(row);
  }
  await browser.close(); save();
}

// Fresh contexts deliberately have no HTTP cache/cookies. Pace their API/image
// requests globally so a QA matrix does not exhaust the real 120/min/IP limit.
let apiQueue = Promise.resolve(), lastApiRequest = 0;
async function paceBrowserApi() {
  const turn = apiQueue.then(async () => {
    const wait = 850 - (Date.now() - lastApiRequest);
    if (wait > 0) await new Promise(r => setTimeout(r, wait));
    lastApiRequest = Date.now();
  });
  apiQueue = turn.catch(() => {});
  await turn;
}

if (mode !== 'http') for (const engine of (args.engines || 'chromium,webkit,firefox').split(',')) {
  let browser;
  try { browser = await engines[engine].launch({ headless: true }); }
  catch (e) { issue('engine-unavailable', engine, e.message.split('\n')[0]); continue; }
  for (const c of picked.filter(c => c.browser !== false)) {
    if (c.subnational && report.inventory?.subnational_points === 0) continue;
    if ((engine !== 'chromium' || tier === 'smoke') && !c.representative) continue;
    const viewportWidths = args.widths ? args.widths.split(',').map(Number) : tier === 'matrix' && engine === 'chromium' && c.representative ? widths : [390, 1440];
    for (const width of viewportWidths) for (const locale of locales) {
      const row = { id: c.id, family: c.family, engine, width, locale, url: localUrl(c.path, locale), errors: [], failedRequests: [], blockedExternal: [], badResponses: [] };
      const context = await browser.newContext({ viewport: { width, height: width < 768 ? 844 : 1000 }, locale: locale === 'ru' ? 'ru-RU' : 'en-US', serviceWorkers: 'block' });
      row.cookiesBefore = (await context.cookies()).length;
      await context.route('**/*', async route => {
        const u = new URL(route.request().url());
        if ((u.origin === new URL(base).origin || siteHost(u.hostname)) && /^\/(?:api|og|og-proxy)\//.test(u.pathname)) await paceBrowserApi();
        if (!['http:', 'https:'].includes(u.protocol) || u.origin === new URL(base).origin) return route.continue();
        if (siteHost(u.hostname)) {
          // Keep the navigation's original query: adding preview_locale here
          // would hide a real SSR -> SPA language-loss defect.
          let target = localize(u.href, locale);
          if (route.request().isNavigationRequest()) {
            u.protocol = new URL(base).protocol; u.host = new URL(base).host;
            target = u.href;
          }
          try { return await route.fulfill({ response: await route.fetch({ url: target, timeout: 12000 }) }); } catch { return route.abort(); }
        }
        row.blockedExternal.push(u.origin + u.pathname);
        return route.abort();
      });
      const page = await context.newPage();
      page.on('pageerror', e => row.errors.push(e.message));
      page.on('requestfailed', r => { if (new URL(r.url()).origin === new URL(base).origin) row.failedRequests.push({ url: r.url(), error: r.failure()?.errorText }); });
      page.on('response', r => { if (r.status() >= 400 && new URL(r.url()).origin === new URL(base).origin) row.badResponses.push({ url: r.url(), status: r.status() }); });
      try {
        const response = await page.goto(row.url, { waitUntil: 'domcontentloaded', timeout: 25000 }); row.status = response?.status();
        await page.locator('h1').first().waitFor({ timeout: 15000 });
        await page.waitForLoadState('networkidle', { timeout: 30000 }).catch(() => {});
        await page.evaluate(() => Promise.race([document.fonts.ready, new Promise(r => setTimeout(r, 3000))]));
        await page.waitForTimeout(650);
        row.document = await page.evaluate(() => {
          const visible = e => { const r = e.getBoundingClientRect(), s = getComputedStyle(e); return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none'; };
          const b = e => { const r = e.getBoundingClientRect(); return { x: r.x, y: r.y, width: r.width, height: r.height, right: r.right, bottom: r.bottom }; };
          const main = document.querySelector('main,article') || document.body;
          return { title: document.title, lang: document.documentElement.lang, h1: [...document.querySelectorAll('h1')].filter(visible).map(e => ({ text: e.textContent.trim(), ...b(e) })), overflow: Math.max(document.documentElement.scrollWidth, document.body.scrollWidth) - innerWidth, viewport: { width: innerWidth, height: innerHeight }, main: b(main), font: getComputedStyle(main).fontFamily, fontFaces: [...document.fonts].map(f => ({ family: f.family, status: f.status })), assets: [...document.querySelectorAll('script[src],link[rel=stylesheet]')].map(e => e.src || e.href), charts: [...main.querySelectorAll('svg,canvas')].filter(visible).filter(e => e.getBoundingClientRect().width > 200 && e.getBoundingClientRect().height > 100).map(e => ({ kind: e.tagName, aria: e.getAttribute('aria-label'), ...b(e) })), seoFast: !!document.querySelector('.seo-fast'), spaChildren: document.querySelector('#root')?.childElementCount || 0, images: [...document.images].filter(visible).map(i => ({ src: i.currentSrc, alt: i.alt, complete: i.complete, naturalWidth: i.naturalWidth, ...b(i) })), empty: !main.textContent.trim(), mainTextStart: main.innerText.slice(0, 550), offscreen: [...main.querySelectorAll('h1,h2,p,figure,table,nav,section')].filter(visible).filter(e => { const r = e.getBoundingClientRect(); return r.left < -3 || r.right > innerWidth + 3; }).slice(0, 15).map(e => ({ tag: e.tagName, cls: String(e.className).slice(0, 100), text: e.textContent.trim().slice(0, 90), ...b(e) })) };
        });
        if (row.status !== c.status) issue('browser-status', `${engine}:${c.id}:${width}:${locale}`, row.status);
        if (row.document.overflow > 3) issue('document-overflow', `${engine}:${c.id}:${width}:${locale}`, row.document.overflow);
        if (!row.document.h1.length || row.document.empty) issue('empty-content', `${engine}:${c.id}:${width}:${locale}`, row.document);
        row.softNotFound = row.document.h1.some(h => /^(404|страница не найдена|page not found)$/i.test(h.text.trim())) && c.status === 200;
        if (row.softNotFound) issue('soft-not-found', `${engine}:${c.id}:${width}:${locale}`, row.document.h1);
        if (row.errors.length) issue('pageerror', `${engine}:${c.id}:${width}:${locale}`, row.errors);
        row.expectedResponses = row.badResponses.filter(r => r.status === 404 && c.expected404?.includes(new URL(r.url).pathname));
        const badResponses = row.badResponses.filter(r => !(r.status === 401 && new URL(r.url).pathname === '/api/v1/auth/me') && !row.expectedResponses.includes(r));
        if (badResponses.length) issue('browser-response', `${engine}:${c.id}:${width}:${locale}`, badResponses);
        const missing = row.document.images.filter(i => i.complete && !i.naturalWidth); if (missing.length) issue('browser-image', `${engine}:${c.id}:${width}:${locale}`, missing);
        // Every checked viewport is reviewable, including boundary widths and
        // secondary engines. PNGs stay in ignored output, never tracked docs.
        row.screenshot = path.relative(root, path.join(shots, `${engine}-${c.id}-${width}-${locale}.png`));
        await page.screenshot({ path: path.join(root, row.screenshot), fullPage: false });
        if (c.id === 'home' && width === 390) {
          const dialog = page.getByRole('dialog', { name: locale === 'ru' ? 'Настройки cookie' : 'Cookie settings' });
          row.interactions = { cookieInitiallyVisible: await dialog.isVisible() };
          if (row.interactions.cookieInitiallyVisible) {
            await dialog.getByRole('button', { name: locale === 'ru' ? 'Настроить' : 'Customize', exact: true }).click();
            for (const checkbox of await dialog.getByRole('checkbox').all()) if (await checkbox.isEnabled()) await checkbox.uncheck();
            await dialog.getByRole('button', { name: locale === 'ru' ? 'Сохранить выбор' : 'Save choices', exact: true }).click();
            await dialog.waitFor({ state: 'hidden', timeout: 3000 });
            row.interactions.cookieChoicesSaved = true;
          }
          const menu = page.getByRole('button', { name: locale === 'ru' ? 'Открыть меню' : 'Open menu', exact: true });
          await menu.click();
          const closeMenu = page.getByRole('button', { name: locale === 'ru' ? 'Закрыть меню' : 'Close menu', exact: true });
          row.interactions.mobileMenuExpanded = await closeMenu.getAttribute('aria-expanded') === 'true';
          row.interactions.mobileMenuLinks = await page.locator('.fe-navbar-mobile-menu a').count();
          if (!row.interactions.mobileMenuExpanded || !row.interactions.mobileMenuLinks) issue('mobile-menu', `${engine}:${locale}`, row.interactions);
          await closeMenu.click();
        }
        if (c.representative && [390, 1440].includes(width)) {
          const dialog = page.getByRole('dialog', { name: locale === 'ru' ? 'Настройки cookie' : 'Cookie settings' });
          if (await dialog.isVisible()) await dialog.getByRole('button', { name: locale === 'ru' ? 'Закрыть' : 'Close', exact: true }).click();
          for (const chart of await page.locator('main svg,main canvas,main figure').all()) {
            const box = await chart.boundingBox();
            if (!box || box.width < 200 || box.height < 100) continue;
            await chart.scrollIntoViewIfNeeded();
            await page.waitForTimeout(250);
            row.chartScreenshot = path.relative(root, path.join(shots, `${engine}-${c.id}-${width}-${locale}-chart.png`));
            await page.screenshot({ path: path.join(root, row.chartScreenshot), fullPage: false });
            break;
          }
        }
        if (c.continuation && [390, 1440].includes(width)) {
          if (!row.document.seoFast && row.document.spaChildren) {
            // The base rating is already interactive after hydration; its
            // server-only image link no longer exists. Annual fast pages keep it.
            row.continuation = { mode: 'already-hydrated-spa' };
          } else {
            const link = page.locator(c.continuation.selector).first();
            row.continuation = { mode: 'native-click', href: await link.getAttribute('href') };
            await link.click();
            await page.waitForLoadState('networkidle', { timeout: 30000 }).catch(() => {});
            await page.waitForFunction(() => document.querySelector('#root')?.childElementCount > 0, null, { timeout: 15000 });
          }
          row.continuation.finalUrl = page.url();
          row.continuation.spaChildren = await page.locator('#root > *').count();
          row.continuation.selectedYears = await page.locator('select').evaluateAll(selects => selects.map(s => s.value));
          row.continuation.chartAnchor = await page.locator('#chart').count();
          row.continuation.lang = await page.evaluate(() => document.documentElement.lang);
          if (new URL(page.url()).pathname !== c.continuation.path || !row.continuation.spaChildren || !row.continuation.chartAnchor) issue('continuation-not-interactive', `${engine}:${c.id}:${width}:${locale}`, row.continuation);
          if (c.continuation.year && !row.continuation.selectedYears.includes(c.continuation.year)) issue('continuation-lost-year', `${engine}:${c.id}:${width}:${locale}`, row.continuation);
          if (row.continuation.lang !== locale) issue('continuation-lost-locale', `${engine}:${c.id}:${width}:${locale}`, row.continuation);
          row.continuation.screenshot = path.relative(root, path.join(shots, `${engine}-${c.id}-${width}-${locale}-continuation.png`));
          await page.screenshot({ path: path.join(root, row.continuation.screenshot), fullPage: false });
        }
      } catch (e) {
        row.error = e.message.split('\n')[0]; issue('browser-error', `${engine}:${c.id}:${width}:${locale}`, row.error);
        const failureShot = path.join(shots, `${engine}-${c.id}-${width}-${locale}-failure.png`);
        try {
          await page.screenshot({ path: failureShot, fullPage: false });
          row.failureScreenshot = path.relative(root, failureShot);
          row.screenshot ||= row.failureScreenshot;
        } catch (captureError) { row.screenshotError = captureError.message.split('\n')[0]; }
      }
      await context.close(); report.browser.push(row); save();
      console.log(`BROWSER ${engine} ${c.id} ${width} ${locale}: ${row.status || row.error} overflow=${row.document?.overflow ?? '?'}`);
    }
  }
  await browser.close();
}
await request.dispose();
report.completedAt = new Date().toISOString();
report.summary = { httpCases: report.http.length, apiCases: report.api.length, browserCases: report.browser.length, issues: report.issues.length, issueKinds: Object.fromEntries([...new Set(report.issues.map(x => x.kind))].map(k => [k, report.issues.filter(x => x.kind === k).length])) };
save(); console.log(JSON.stringify(report.summary));
process.exitCode = report.issues.some(i => i.kind !== 'data-unavailable') ? 1 : 0;
