#!/usr/bin/env node
/**
 * Rebuild the shared brand preview with approved local assets (no data/requests).
 * Run from any directory: node scripts/render-generic-og.mjs
 * Requires frontend npm dependencies and Playwright Chromium.
 */
import { createRequire } from 'node:module';
import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const require = createRequire(resolve(root, 'frontend/package.json'));
const { chromium } = require('playwright');
const asset = (path, type) => `data:${type};base64,${readFileSync(resolve(root, path)).toString('base64')}`;
const font = asset('frontend/public/fonts/manrope-latin-cyrillic.woff2', 'font/woff2');
const art = asset('frontend/public/art/quicklinks/forecast-glass.webp', 'image/webp');
const output = resolve(root, 'frontend/public/og-image-v3.png');

const browser = await chromium.launch();
try {
  const page = await browser.newPage({ viewport: { width: 1200, height: 630 }, deviceScaleFactor: 1 });
  await page.setContent(`<!doctype html><html lang="en"><meta charset="utf-8"><style>
    @font-face { font-family:Manrope; src:url('${font}') format('woff2'); font-weight:200 800; }
    * { box-sizing:border-box; margin:0; }
    body { width:1200px; height:630px; overflow:hidden; background:#EEF0F4; color:#202A3C; font-family:Manrope,sans-serif; }
    main { position:relative; isolation:isolate; width:100%; height:100%; padding:42px 48px; background:radial-gradient(ellipse at 95% 0%,#E9DFCD75,transparent 60%); }
    .art { position:absolute; z-index:-2; width:1020px; height:680px; right:-166px; top:-29px; object-fit:cover; }
    .veil { position:absolute; z-index:-1; inset:0; background:linear-gradient(90deg,#EEF0F4 0%,#EEF0F4F5 31%,#EEF0F426 61%,transparent); }
    .brand { display:flex; align-items:center; gap:10px; font-size:31px; font-weight:730; letter-spacing:-.06em; }
    .brand svg { width:34px; height:40px; }
    .brand span span { font-weight:460; }
    .eyebrow { margin-top:64px; display:flex; align-items:center; gap:12px; font-size:12px; font-weight:650; letter-spacing:.15em; color:#59697F; }
    .eyebrow:before { content:''; width:28px; height:2px; background:#AD8A48; }
    h1 { margin-top:22px; font-size:61px; font-weight:530; line-height:1.1; letter-spacing:-.055em; }
    .caption { margin-top:23px; color:#59697F; font-size:16px; line-height:1.8; }
    footer { position:absolute; left:48px; right:48px; bottom:37px; display:flex; justify-content:space-between; align-items:center; gap:30px; padding:21px 25px; border:1px solid #FFFFFFE6; border-radius:21px; background:linear-gradient(130deg,#FFFFFFDC,#FFFFFFA8); box-shadow:0 16px 45px -33px #26344E50; }
    footer strong { font-weight:600; letter-spacing:-.035em; font-size:23px; }
    footer span { color:#59697F; font-size:12px; letter-spacing:.08em; }
  </style><main>
    <img class="art" src="${art}" alt=""><div class="veil"></div>
    <div class="brand"><svg viewBox="0 0 40 44" aria-hidden="true"><path d="M8 38V17Q8 5 21 5H34V13H22Q17 13 17 19V20H31V28H17V38Z" fill="currentColor"/><path d="M29 30H35V38H29Z" fill="#AD8A48"/></svg><span>forecast<span>economy</span></span></div>
    <p class="eyebrow">OFFICIAL DATA · ОФИЦИАЛЬНЫЕ ДАННЫЕ</p>
    <h1>Economic<br>intelligence.</h1>
    <p class="caption">Data. Charts. Context.<br>Данные. Графики. Контекст.</p>
    <footer><strong>forecasteconomy.com</strong><span>ЭКОНОМИКА, КОТОРУЮ ВИДНО</span></footer>
  </main></html>`);
  await page.evaluate(async () => {
    await document.fonts.ready;
    await Promise.all([...document.images].map((img) => img.decode()));
  });
  await page.screenshot({ path: output, type: 'png', animations: 'disabled' });
  console.log(`Generated ${output} (1200×630)`);
} finally {
  await browser.close();
}
