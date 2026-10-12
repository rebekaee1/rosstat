#!/usr/bin/env node
/**
 * Автоматический прогон вёрстки по набору страниц и ширин окна (Playwright, только чтение).
 *
 * Находит то, что человек видит как «некрасиво», без участия человека:
 *   - overflow-x: страница шире окна, элементы уходят за правый край;
 *   - number-split: число (и «число + единица/валюта») разорвано по двум строкам, например «-5,626.» / «5»;
 *   - truncated: название обрезано многоточием или line-clamp (читатель не видит, что за показатель);
 *   - overlap: два текстовых блока одного родителя налезают друг на друга;
 *   - tap-target: кнопка или ссылка меньше 36 px на телефоне и планшете;
 *   - tiny-text: текст мельче 11 px;
 *   - console/network: ошибки консоли и ответы 4xx/5xx (кроме ожидаемого 401 у гостя).
 *
 * Не заменяет глаза на настоящем устройстве (safe-area, жесты, шрифты iOS), но за минуты проходит десятки
 * сочетаний «страница × ширина» и называет конкретные элементы.
 *
 * Пример:
 *   node scripts/dev/layout-sweep.mjs --base https://ru.forecasteconomy.com --widths 360,390,430,768,1024,1440,1920 \
 *     --out .artifacts/sweep-ru --shots
 *   node scripts/dev/layout-sweep.mjs --base http://127.0.0.1:5191 --paths /,/russia,/compare --widths 360,390
 *
 * Параметры:
 *   --base URL        откуда брать страницы (по умолчанию https://forecasteconomy.com)
 *   --paths a,b,c     пути (по умолчанию набор ключевых страниц России, мира, сравнения, валют, калькулятора)
 *   --paths-file F    файл с путями по одному в строке
 *   --widths ...      ширины окна (по умолчанию 360,390,430,768,1024,1440,1920)
 *   --height N        высота окна (по умолчанию 900; для ширин ≤ 820 берётся 844)
 *   --out DIR         куда писать report.md, report.json и кадры (по умолчанию ./layout-sweep-out)
 *   --shots           сохранять кадр для каждого случая с находками
 *   --concurrency N   параллельных страниц (по умолчанию 3; прод держит 4 vCPU, не ставь больше 4)
 *   --browser PATH    свой исполняемый файл Chromium (по умолчанию тот, что поставил playwright)
 *   --insecure        принимать самоподписанный сертификат (локальный стенд perf-serve.mjs)
 */
import fs from 'node:fs';
import path from 'node:path';
import { createRequire } from 'node:module';
import { fileURLToPath, pathToFileURL } from 'node:url';

// Playwright лежит в frontend/node_modules (devDependency), а скрипт — в scripts/dev: ищем его там.
async function loadPlaywright() {
  try { return await import('playwright'); } catch { /* ниже */ }
  const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
  const req = createRequire(path.join(root, 'frontend', 'package.json'));
  return import(pathToFileURL(req.resolve('playwright')).href);
}
const playwright = await loadPlaywright();
const chromium = playwright.chromium || playwright.default.chromium;

const args = Object.fromEntries(process.argv.slice(2).reduce((acc, a, i, all) => {
  if (a.startsWith('--')) acc.push([a.slice(2), all[i + 1] && !all[i + 1].startsWith('--') ? all[i + 1] : true]);
  return acc;
}, []));

const BASE = String(args.base || 'https://forecasteconomy.com').replace(/\/$/, '');
const WIDTHS = String(args.widths || '360,390,430,768,1024,1440,1920').split(',').map(Number);
const OUT = path.resolve(String(args.out || './layout-sweep-out'));
const CONCURRENCY = Math.min(4, Number(args.concurrency || 3));
const DEFAULT_PATHS = [
  '/', '/russia', '/russia/category/prices', '/russia/category/finance', '/russia/indicator/cpi',
  '/world', '/world/rating/unemployment-rate', '/compare', '/regions', '/currencies', '/calendar', '/calculator',
  '/search?q=inflation',
];
let PATHS = DEFAULT_PATHS;
if (args['paths-file']) PATHS = fs.readFileSync(String(args['paths-file']), 'utf8').split('\n').map((s) => s.trim()).filter(Boolean);
else if (args.paths) PATHS = String(args.paths).split(',').map((s) => s.trim()).filter(Boolean);

fs.mkdirSync(OUT, { recursive: true });
const SELF_TEST = Boolean(args['self-test']);

/** Выполняется внутри страницы. Возвращает массив находок {kind, sel, text, detail}. */
function inPage(isTouch) {
  const out = [];
  const vw = window.innerWidth;
  const short = (s, n = 70) => String(s || '').replace(/\s+/g, ' ').trim().slice(0, n);
  const sel = (el) => {
    const parts = [];
    for (let e = el, i = 0; e && e.nodeType === 1 && i < 3; e = e.parentElement, i += 1) {
      const cls = (e.className && typeof e.className === 'string' ? e.className.split(/\s+/).filter(Boolean).slice(0, 2) : []).join('.');
      parts.unshift(e.tagName.toLowerCase() + (cls ? `.${cls}` : ''));
    }
    return parts.join(' > ');
  };
  const visible = (el) => {
    const r = el.getBoundingClientRect();
    if (r.width < 1 || r.height < 1) return false;
    const st = getComputedStyle(el);
    return st.visibility !== 'hidden' && st.display !== 'none' && Number(st.opacity) > 0.05;
  };
  const inScroller = (el) => {
    for (let e = el.parentElement; e && e !== document.body; e = e.parentElement) {
      const st = getComputedStyle(e);
      if (/(auto|scroll)/.test(st.overflowX) && e.scrollWidth > e.clientWidth) return true;
      if (st.overflowX === 'hidden' && e.getBoundingClientRect().right <= vw + 1) return true;
    }
    return false;
  };

  // 1. overflow-x
  const docW = document.documentElement.scrollWidth;
  if (docW > vw + 1) {
    const bad = [];
    for (const el of document.body.querySelectorAll('*')) {
      if (bad.length >= 6) break;
      const r = el.getBoundingClientRect();
      if (r.right > vw + 2 && r.width > 4 && visible(el) && !inScroller(el) && getComputedStyle(el).position !== 'fixed') {
        bad.push({ kind: 'overflow-x', sel: sel(el), text: short(el.textContent, 40), detail: `правый край ${Math.round(r.right)} при окне ${vw}` });
      }
    }
    out.push({ kind: 'overflow-x', sel: 'document', text: '', detail: `ширина страницы ${docW} при окне ${vw}` }, ...bad);
  }

  // 2. число разорвано по строкам
  const tokenRe = /[−+-]?\d[\d   ]*(?:[.,]\d+)?(?:\s?(?:%|п\.\s?п\.|млрд|млн|трлн|тыс\.|bn|mn|trn|k|₽|\$|€|¥|руб\.?|RUB|USD|EUR))?/g;
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  let seenNum = 0;
  for (let n = walker.nextNode(); n && seenNum < 4000; n = walker.nextNode()) {
    const txt = n.textContent;
    if (!/\d/.test(txt) || !n.parentElement || !visible(n.parentElement)) continue;
    const tag = n.parentElement.tagName;
    if (tag === 'SCRIPT' || tag === 'STYLE' || tag === 'NOSCRIPT') continue;
    let m;
    tokenRe.lastIndex = 0;
    while ((m = tokenRe.exec(txt))) {
      seenNum += 1;
      const token = m[0];
      if (token.trim().length < 3) continue;
      const range = document.createRange();
      range.setStart(n, m.index);
      range.setEnd(n, m.index + token.length);
      const rects = [...range.getClientRects()].filter((r) => r.width > 0);
      if (rects.length < 2) continue;
      const tops = new Set(rects.map((r) => Math.round(r.top / 4)));
      if (tops.size > 1 && !/\s{2,}/.test(token)) {
        out.push({ kind: 'number-split', sel: sel(n.parentElement), text: short(token, 40), detail: 'число или единица разорваны по двум строкам' });
        break;
      }
    }
  }

  // 3. обрезано многоточием / line-clamp
  let trunc = 0;
  for (const el of document.body.querySelectorAll('*')) {
    if (trunc >= 12) break;
    const st = getComputedStyle(el);
    const clamp = st.webkitLineClamp && st.webkitLineClamp !== 'none';
    const ell = st.textOverflow === 'ellipsis' && st.overflow !== 'visible';
    if (!(clamp || ell) || !visible(el) || !short(el.textContent)) continue;
    const cut = clamp ? el.scrollHeight > el.clientHeight + 2 : el.scrollWidth > el.clientWidth + 3;
    if (cut) {
      trunc += 1;
      out.push({ kind: 'truncated', sel: sel(el), text: short(el.textContent, 60), detail: clamp ? `line-clamp ${st.webkitLineClamp}` : 'text-overflow: ellipsis' });
    }
  }

  // 4. наложение соседних текстовых блоков
  let ov = 0;
  const parents = new Set();
  for (const el of document.body.querySelectorAll('*')) if (el.children.length > 1 && el.children.length < 14) parents.add(el);
  for (const p of parents) {
    if (ov >= 8) break;
    const kids = [...p.children].filter((k) => visible(k) && short(k.textContent) && getComputedStyle(k).position !== 'absolute' && getComputedStyle(k).position !== 'fixed');
    const rectsOf = (el) => {
      const display = getComputedStyle(el).display;
      const list = display.startsWith('inline') && display !== 'inline-block' && display !== 'inline-flex' ? [...el.getClientRects()] : [el.getBoundingClientRect()];
      return list.filter((r) => r.width > 2 && r.height > 2);
    };
    for (let i = 0; i < kids.length && ov < 8; i += 1) {
      for (let j = i + 1; j < kids.length; j += 1) {
        let hit = null;
        for (const a of rectsOf(kids[i])) {
          for (const b of rectsOf(kids[j])) {
            const w = Math.min(a.right, b.right) - Math.max(a.left, b.left);
            const h = Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top);
            if (w > 6 && h > 6 && (w * h) / Math.min(a.width * a.height, b.width * b.height) > 0.25) hit = { w, h };
          }
        }
        if (hit) {
          ov += 1;
          out.push({ kind: 'overlap', sel: sel(p), text: `${short(kids[i].textContent, 30)} ⟷ ${short(kids[j].textContent, 30)}`, detail: `пересечение ${Math.round(hit.w)}×${Math.round(hit.h)} px` });
          break;
        }
      }
    }
  }

  // 5. мелкие цели нажатия и мелкий текст
  if (isTouch) {
    let tt = 0;
    for (const el of document.body.querySelectorAll('a[href],button,[role=button],input:not([type=hidden]),select')) {
      if (tt >= 10) break;
      if (!visible(el) || el.closest('svg')) continue;
      const r = el.getBoundingClientRect();
      if ((r.height < 32 || r.width < 32) && r.width * r.height > 0 && !(el.tagName === 'A' && getComputedStyle(el).display === 'inline')) {
        tt += 1;
        out.push({ kind: 'tap-target', sel: sel(el), text: short(el.textContent || el.getAttribute('aria-label'), 30), detail: `${Math.round(r.width)}×${Math.round(r.height)} px` });
      }
    }
  }
  let tiny = 0;
  const w2 = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  for (let n = w2.nextNode(); n && tiny < 6; n = w2.nextNode()) {
    if (!n.textContent.trim() || !n.parentElement || !visible(n.parentElement)) continue;
    const fs = parseFloat(getComputedStyle(n.parentElement).fontSize);
    if (fs < 11) { tiny += 1; out.push({ kind: 'tiny-text', sel: sel(n.parentElement), text: short(n.textContent, 40), detail: `${fs}px` }); }
  }
  return out;
}

async function scrollThrough(page) {
  await page.evaluate(async () => {
    const h = () => document.documentElement.scrollHeight;
    for (let y = 0; y < Math.min(h(), 14000); y += Math.round(window.innerHeight * 0.8)) {
      window.scrollTo(0, y);
      await new Promise((r) => setTimeout(r, 140));
    }
    window.scrollTo(0, 0);
  });
}

// --insecure: самоподписанный сертификат локального стенда (scripts/dev/perf-serve.mjs); хосты *.localhost Chrome ведёт на петлю сам.
const browser = await chromium.launch({
  ...(args.browser ? { executablePath: String(args.browser) } : {}),
  ...(args.insecure ? { args: ['--ignore-certificate-errors'] } : {}),
});
if (SELF_TEST) {
  // Проверка самого инструмента: страница с заведомыми дефектами должна дать находки каждого вида.
  const ctx = await browser.newContext({ viewport: { width: 300, height: 600 }, hasTouch: true });
  const page = await ctx.newPage();
  await page.setContent(`<body style="margin:0;font:16px sans-serif">
    <p style="width:120px">Итого -5,626.5 млрд ₽ за год</p>
    <div style="display:grid;grid-template-columns:1fr auto"><span style="white-space:nowrap">309 014,39 млн $</span><span style="margin-left:-60px;white-space:nowrap">к прошлому кварталу</span></div>
    <span style="display:block;width:90px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">Индекс потребительских цен на услуги</span>
    <div style="width:500px;height:10px;background:red"></div><button style="width:20px;height:20px">x</button><small style="font-size:9px">мелко</small></body>`);
  const found = await page.evaluate(inPage, true);
  const kinds = [...new Set(found.map((f) => f.kind))].sort();
  console.log('self-test находки:', kinds.join(', '));
  const need = ['number-split', 'overflow-x', 'overlap', 'tap-target', 'tiny-text', 'truncated'];
  const miss = need.filter((k) => !kinds.includes(k));
  await browser.close();
  if (miss.length) { console.error('НЕ нашёл:', miss.join(', ')); process.exit(1); }
  console.log('self-test OK');
  process.exit(0);
}
const jobs = [];
for (const p of PATHS) for (const w of WIDTHS) jobs.push({ p, w });
const results = [];
let next = 0;

async function worker() {
  while (next < jobs.length) {
    const { p, w } = jobs[next++];
    const touch = w <= 1024;
    const ctx = await browser.newContext({
      viewport: { width: w, height: w <= 820 ? 844 : 900 },
      deviceScaleFactor: touch ? 2 : 1,
      isMobile: w <= 820,
      hasTouch: touch,
      ignoreHTTPSErrors: Boolean(args.insecure),
      locale: BASE.includes('ru.') || BASE.includes('ru.localhost') ? 'ru-RU' : 'en-US',
    });
    const page = await ctx.newPage();
    const errs = [];
    page.on('console', (m) => { if (m.type() === 'error' && !/401/.test(m.text())) errs.push(short(m.text())); });
    page.on('response', (r) => { if (r.status() >= 400 && !(r.status() === 401 && /auth\/me/.test(r.url()))) errs.push(`${r.status()} ${new URL(r.url()).pathname}`); });
    function short(s) { return String(s).slice(0, 120); }
    const rec = { path: p, width: w, findings: [], errors: [], shot: null };
    try {
      await page.goto(BASE + p, { waitUntil: 'domcontentloaded', timeout: 45000 });
      await page.waitForLoadState('networkidle', { timeout: 20000 }).catch(() => {});
      await scrollThrough(page);
      await page.waitForTimeout(600);
      rec.findings = await page.evaluate(inPage, touch);
      rec.errors = [...new Set(errs)].slice(0, 6);
      if (args.shots && (rec.findings.length || rec.errors.length)) {
        const name = `${p.replace(/[^a-z0-9]+/gi, '_') || 'home'}_${w}.png`;
        await page.screenshot({ path: path.join(OUT, name), fullPage: false });
        rec.shot = name;
      }
    } catch (e) {
      rec.errors.push(`не открылась: ${String(e.message).slice(0, 100)}`);
    }
    results.push(rec);
    await ctx.close();
    process.stderr.write(`\r${results.length}/${jobs.length}`);
  }
}
await Promise.all(Array.from({ length: CONCURRENCY }, worker));
await browser.close();
process.stderr.write('\n');

results.sort((a, b) => a.path.localeCompare(b.path) || a.width - b.width);
fs.writeFileSync(path.join(OUT, 'report.json'), JSON.stringify(results, null, 1));

const sev = { 'overflow-x': 1, 'number-split': 1, overlap: 1, truncated: 2, 'tap-target': 3, 'tiny-text': 3 };
const byKind = {};
for (const r of results) for (const f of r.findings) byKind[f.kind] = (byKind[f.kind] || 0) + 1;
let md = `# Прогон вёрстки: ${BASE}\n\nСтраниц: ${PATHS.length}, ширин: ${WIDTHS.join(', ')}. Находок по видам: ${Object.entries(byKind).map(([k, v]) => `${k} ${v}`).join(', ') || 'нет'}.\n\n`;
md += '| Страница | Ширина | Вид | Элемент | Текст | Подробности |\n|---|---|---|---|---|---|\n';
const rows = [];
for (const r of results) {
  const groups = new Map();
  for (const f of r.findings) {
    const key = `${f.kind}|${f.sel}`;
    const g = groups.get(key);
    if (g) { g.n += 1; if (g.f.text.length < 60 && !g.f.text.includes(f.text)) g.f = { ...g.f, text: `${g.f.text}; ${f.text}`.slice(0, 120) }; } else groups.set(key, { n: 1, f });
  }
  for (const { n, f } of groups.values()) rows.push({ s: sev[f.kind] || 4, r, f: n > 1 ? { ...f, detail: `${f.detail} (×${n})` } : f });
  for (const e of r.errors) rows.push({ s: 5, r, f: { kind: 'error', sel: '', text: e, detail: '' } });
}
rows.sort((a, b) => a.s - b.s || a.r.path.localeCompare(b.r.path) || a.r.width - b.r.width);
for (const { r, f } of rows.slice(0, 400)) {
  md += `| ${r.path} | ${r.width} | ${f.kind} | \`${String(f.sel).replace(/\|/g, '/')}\` | ${String(f.text).replace(/\|/g, '/')} | ${f.detail}${r.shot ? ` (${r.shot})` : ''} |\n`;
}
if (rows.length > 400) md += `\n… и ещё ${rows.length - 400} строк в report.json\n`;
fs.writeFileSync(path.join(OUT, 'report.md'), md);
console.log(`${rows.length} находок; отчёт: ${path.join(OUT, 'report.md')}`);
