#!/usr/bin/env node
/** Portable local review package. No production imports, network or rendering. */
import { copyFile, mkdir, readFile, readdir, rename, stat, unlink, writeFile } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { dirname, extname, isAbsolute, join, relative, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const repo = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const output = join(repo, 'output/design-review');
const acceptance = join(repo, 'docs/design/local-acceptance');
const artwork = join(repo, 'frontend/public/art/quicklinks');
const promptSource = join(repo, 'docs/design/art-prompts');
const args = process.argv.slice(2);
let explicitStage;
let watch = false;
for (let index = 0; index < args.length; index += 1) {
  if (args[index] === '--stage' && args[index + 1]) explicitStage = args[++index];
  else if (args[index] === '--watch') watch = true;
  else if (args[index] === '--help') {
    console.log('node scripts/build-design-review.mjs [--stage NAME] [--watch]');
    process.exit(0);
  } else throw new Error(`Unknown or incomplete option: ${args[index]}`);
}

const themeNames = {
  housing: 'Жильё', population: 'Население', agriculture: 'Сельское хозяйство',
  education: 'Образование', health: 'Здоровье', energy: 'Энергетика',
  transport: 'Транспорт', science: 'Наука', finance: 'Финансы',
  environment: 'Экология', tourism: 'Туризм', commodity: 'Товарные рынки',
  industry: 'Промышленность', ict: 'Цифровая экономика', trade: 'Торговля',
  justice: 'Институты', 'forecast-glass': 'Бренд', neutral: 'Общий обзор',
  inflation: 'Инфляция', gdp: 'ВВП', labor: 'Рынок труда', wages: 'Зарплаты',
  demographics: 'Демография', ranking: 'Рейтинги', comparison: 'Сравнения',
  regional: 'Регионы', world: 'Страны мира', calculators: 'Калькуляторы', calendar: 'Календарь',
};
const label = (value) => Object.hasOwn(themeNames, value) ? themeNames[value] : String(value || 'Общий обзор');
const slug = (value) => String(value || 'image').replace(/[^a-zA-Z0-9_-]+/g, '-').slice(0, 100);
const hash = (value) => createHash('sha1').update(value).digest('hex').slice(0, 8);
const stableId = (kind, parts) => `${kind}-${slug(parts[0])}-${createHash('sha256').update(JSON.stringify(parts)).digest('hex').slice(0, 16)}`;
const json = async (path) => JSON.parse(await readFile(path, 'utf8'));
const exists = async (path) => { try { return (await stat(path)).isFile(); } catch { return false; } };
const list = async (path) => { try { return await readdir(path); } catch { return []; } };
const portablePath = (path) => relative(output, path).split('\\').join('/');

async function stages() {
  const found = [];
  for (const name of await list(acceptance)) {
    for (const report of ['browser.json', 'all.json']) {
      const path = join(acceptance, name, report);
      if (await exists(path)) {
        const data = await json(path);
        if (Array.isArray(data.browser) && data.browser.length) {
          found.push({ name, path, data, time: Date.parse(data.at) || (await stat(path)).mtimeMs });
        }
      }
    }
  }
  return found.sort((a, b) => b.time - a.time);
}

async function selectStage() {
  const available = await stages();
  if (explicitStage) {
    const selected = available.find((stage) => stage.name === explicitStage);
    if (!selected) throw new Error(`Stage not found: ${explicitStage}. Available: ${available.map((s) => s.name).join(', ')}`);
    return selected;
  }
  return available.find((stage) => /(?:^|[-_])(final|after[-_]build)(?:$|[-_])/i.test(stage.name))
    || available.find((stage) => !stage.name.startsWith('baseline')) || available[0] || null;
}

async function sourceFile(file, base) {
  if (!file || typeof file !== 'string' || !/\.(png|jpe?g|webp|svg)$/i.test(file)) return null;
  const choices = isAbsolute(file) ? [file] : [resolve(base, file), resolve(repo, file), resolve(output, file)];
  for (const candidate of choices) if (await exists(candidate)) return candidate;
  return null;
}

async function copyImage(source, kind, id) {
  // The OG renderer already writes its originals into this portable package.
  if (kind === 'cards' && portablePath(source).startsWith('cards/')) return portablePath(source);
  const dest = join(output, 'images', kind, `${slug(id)}-${hash(source)}${extname(source).toLowerCase()}`);
  await mkdir(dirname(dest), { recursive: true });
  await copyFile(source, dest);
  return portablePath(dest);
}

function screenshotTheme(shot) {
  if (shot.theme) return shot.theme;
  const identity = `${shot.id} ${shot.url}`;
  if (/demograph|population/.test(identity)) return 'population';
  if (/housing/.test(identity)) return 'housing';
  if (/cpi|inflation|hicp/.test(identity)) return 'inflation';
  if (/ppi|industry/.test(identity)) return 'industry';
  if (/key-rate|interest/.test(identity)) return 'finance';
  if (/unemployment|wages|labor/.test(identity)) return 'labor';
  if (/rating/.test(identity)) return 'ranking';
  if (/compare|vs-/.test(identity)) return 'comparison';
  if (/calculator/.test(identity)) return 'calculators';
  if (/calendar/.test(identity)) return 'calendar';
  if (/region/.test(identity)) return 'regional';
  if (/world|germany|us-national/.test(identity)) return 'world';
  return 'neutral';
}

function pageLink(value, locale) {
  if (!value || typeof value !== 'string' || value.startsWith('/Users/') || value.startsWith('file:')) return null;
  try {
    const url = new URL(value, 'http://localhost:3000');
    if (!['http:', 'https:'].includes(url.protocol)) return null;
    if (locale === 'en') url.searchParams.set('preview_locale', 'en');
    return `http://localhost:3000${url.pathname}${url.search}${url.hash}`;
  } catch { return null; }
}

async function build() {
  await mkdir(output, { recursive: true });
  const warnings = [];
  const items = [];
  const manifestPath = join(output, 'cards/manifest.json');
  if (await exists(manifestPath)) {
    const manifest = await json(manifestPath);
    const cards = Array.isArray(manifest) ? manifest : manifest.entries || manifest.cards || [];
    for (const [index, card] of cards.entries()) {
      const source = await sourceFile(card.file, dirname(manifestPath));
      if (!source) { warnings.push(`Не найден файл карточки: ${card.id || index}`); continue; }
      const id = stableId('card', [card.id || card.path || card.file, pageLink(card.path, card.locale), card.locale || 'ru', card.format || 'wide']);
      items.push({ id, kind: 'cards', title: card.title || card.id || 'Карточка',
        theme: card.theme || 'neutral', themeLabel: label(card.theme), locale: card.locale || 'ru',
        format: card.format || 'wide', device: ['portrait', 'vertical'].includes(card.format) ? 'mobile' : 'desktop',
        image: await copyImage(source, 'cards', id), page: pageLink(card.path, card.locale) });
    }
  }

  const selected = await selectStage();
  for (const [index, shot] of (selected?.data.browser || []).entries()) {
    const rawWidth = Number(shot.width || shot.document?.viewport?.width);
    const width = Number.isFinite(rawWidth) && rawWidth > 0 ? rawWidth : null;
    // Raw H1 text may include both hidden desktop and mobile copies.
    const title = String(shot.document?.title || shot.document?.h1?.[0]?.text || shot.id || 'Страница')
      .replace(/\s*(?:\||—|-)\s*Forecast\s?Economy.*$/i, '');
    const theme = screenshotTheme(shot);
    for (const [view, file] of [['page', shot.screenshot], ['chart', shot.chartScreenshot]]) {
      if (!file) continue;
      const source = await sourceFile(file, dirname(selected.path));
      if (!source) { warnings.push(`Не найден снимок ${view === 'chart' ? 'графика' : 'страницы'}: ${shot.id || index}`); continue; }
      const id = stableId('site', [shot.id || shot.url || shot.path || 'site', pageLink(shot.url || shot.path, shot.locale), shot.locale || 'ru', width, shot.engine || 'browser', view]);
      items.push({ id, kind: 'site', view, title, theme,
        themeLabel: label(theme), locale: shot.locale || 'ru', width,
        device: width == null ? 'neutral' : width < 768 ? 'mobile' : 'desktop', format: 'screenshot',
        image: await copyImage(source, 'site', id), page: pageLink(shot.url || shot.path, shot.locale),
        stage: selected.name, engine: shot.engine || 'browser',
        check: shot.status >= 400 || shot.softNotFound || shot.document?.empty || shot.errors?.length ? 'Нужна проверка' : null });
    }
  }

  const prompts = new Map();
  await mkdir(join(output, 'prompts'), { recursive: true });
  for (const name of (await list(promptSource)).filter((name) => name.endsWith('.json')).sort()) {
    const raw = await json(join(promptSource, name));
    const rows = (Array.isArray(raw) ? raw : raw.images || []).map((entry) => ({
      theme: entry.theme || entry.id, prompt: entry.prompt || '',
      ...(entry.mode ? { mode: entry.mode } : {}), ...(entry.role ? { role: entry.role } : {}),
    }));
    for (const entry of rows) prompts.set(entry.theme, entry.prompt);
    await writeFile(join(output, 'prompts', name), `${JSON.stringify(rows, null, 2)}\n`);
  }
  const reconstructionName = 'forecast-glass-reconstruction.md';
  const reconstructionSource = join(promptSource, reconstructionName);
  const reconstruction = await exists(reconstructionSource) ? `prompts/${reconstructionName}` : null;
  if (reconstruction) await copyFile(reconstructionSource, join(output, reconstruction));
  else warnings.push('Не найдена реконструкция промпта forecast-glass');
  for (const name of (await list(artwork)).filter((name) => name.endsWith('.webp') && !name.endsWith('-320.webp')).sort()) {
    const theme = name.slice(0, -5);
    const image = await copyImage(join(artwork, name), 'art', theme);
    const small = join(artwork, `${theme}-320.webp`);
    items.push({ id: `art-${theme}`, kind: 'art', title: label(theme), theme, themeLabel: label(theme),
      locale: 'neutral', format: 'illustration', device: 'neutral', image,
      thumbnail: await exists(small) ? await copyImage(small, 'art', `${theme}-320`) : image,
      prompt: prompts.get(theme) || null,
      ...(theme === 'forecast-glass' && reconstruction ? {
        promptDocument: reconstruction, promptLabel: 'Реконструкция промпта — не исходный текст ↗',
      } : {}) });
  }
  await mkdir(join(output, 'fonts'), { recursive: true });
  for (const name of ['manrope-latin-cyrillic.woff2', 'Manrope-OFL.txt']) {
    await copyFile(join(repo, 'frontend/public/fonts', name), join(output, 'fonts', name));
  }
  await copyFile(join(repo, 'frontend/public/favicon.svg'), join(output, 'favicon.svg'));
  // Decisions identify the logical item and the actual full-size image bytes.
  // Reordering metadata keeps the ID; a changed image gets a new review key.
  const checksums = new Map();
  for (const item of items) {
    if (!checksums.has(item.image)) checksums.set(item.image, createHash('sha256').update(await readFile(join(output, item.image))).digest('hex'));
    item.assetHash = checksums.get(item.image);
  }
  const data = { builtAt: new Date().toISOString(), stage: selected?.name || null,
    report: selected ? relative(acceptance, selected.path).split('\\').join('/') : null,
    finalStage: /(?:^|[-_])(final|after[-_]build)(?:$|[-_])/i.test(selected?.name || ''),
    items, warnings };
  await writeFile(join(output, 'gallery-data.json'), `${JSON.stringify(data, null, 2)}\n`);
  await writeFile(join(output, 'index.html.tmp'), html(data));
  await rename(join(output, 'index.html.tmp'), join(output, 'index.html'));
  const usedImages = new Set(items.flatMap((item) => [item.image, item.thumbnail]).filter(Boolean));
  for (const kind of ['cards', 'site', 'art']) {
    const dir = join(output, 'images', kind);
    for (const name of await list(dir)) {
      const path = join(dir, name);
      if (!usedImages.has(portablePath(path))) await unlink(path);
    }
  }
  console.log(JSON.stringify({ output: portablePath(join(output, 'index.html')),
    stage: data.stage, cards: items.filter((i) => i.kind === 'cards').length,
    screenshots: items.filter((i) => i.kind === 'site').length,
    illustrations: items.filter((i) => i.kind === 'art').length, warnings }));
}

function html(data) {
  const embedded = JSON.stringify(data).replaceAll('<', '\\u003c').replaceAll('\u2028', '\\u2028').replaceAll('\u2029', '\\u2029');
  return `<!doctype html>
<html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex,nofollow"><meta name="theme-color" content="#EEF0F4"><link rel="icon" href="favicon.svg" type="image/svg+xml"><title>ForecastEconomy — дизайн на приёмку</title>
<style>
@font-face{font-family:Manrope;src:url('fonts/manrope-latin-cyrillic.woff2') format('woff2');font-weight:200 800;font-display:swap}
:root{font-family:Manrope,system-ui,sans-serif;color:#202A3C;background:#EEF0F4;font-synthesis:none;--muted:#5F6E84;--gold:#80642F}
*{box-sizing:border-box}body{margin:0;background:radial-gradient(ellipse at 80% 0,#CAD8E57D,transparent 44%),#EEF0F4}button,input,select,textarea{font:inherit}button,a,select,input{-webkit-tap-highlight-color:transparent}button,a{touch-action:manipulation}button{cursor:pointer}a{color:inherit}button:focus-visible,a:focus-visible,input:focus-visible,select:focus-visible,textarea:focus-visible{outline:2px solid #80642F;outline-offset:3px}
.shell{max-width:1520px;margin:auto;padding:28px clamp(16px,4vw,64px) 72px}.top{display:flex;align-items:center;justify-content:space-between;gap:20px;margin-bottom:38px}.brand{font-size:21px;font-weight:700;letter-spacing:-1.2px;display:flex;align-items:center;gap:9px}.brand svg{width:22px;height:28px;fill:currentColor}.quiet{color:var(--muted);font-size:12px}.top a{text-decoration:none;border:1px solid #202A3C20;border-radius:20px;padding:10px 15px;white-space:nowrap}.hero{display:grid;grid-template-columns:1.3fr 1fr;gap:30px;align-items:center;margin-bottom:35px;min-height:280px}.eyebrow{color:var(--gold);font-size:10px;letter-spacing:.17em;font-weight:700;text-transform:uppercase}h1{font-size:clamp(32px,4.1vw,59px);line-height:1.1;letter-spacing:-.055em;font-weight:570;margin:16px 0}h1 span{color:#77899D}.intro{color:var(--muted);font-size:15px;max-width:490px;line-height:1.7}.hero-art{height:280px;width:100%;object-fit:cover;border-radius:30px;mix-blend-mode:multiply}.counts{display:flex;flex-wrap:wrap;gap:10px;margin-top:22px}.count{padding:9px 13px;background:#FFFFFF85;border:1px solid #fff;border-radius:14px;font-size:12px}.count strong{margin-right:5px}.controls{position:sticky;top:10px;z-index:2;padding:14px;border-radius:24px;background:#F6F7F9F5;border:1px solid #fff;box-shadow:0 12px 35px -25px #202A3C50;backdrop-filter:blur(16px);margin-bottom:22px}.tabs{display:flex;gap:5px;flex-wrap:wrap}.tabs button{border:0;border-radius:12px;padding:11px 16px;background:transparent;color:var(--muted);font-size:13px;min-height:42px}.tabs button[aria-pressed=true]{background:#202A3C;color:white;box-shadow:0 3px 8px #202A3C15}.filters{display:flex;gap:8px;flex-wrap:wrap;margin-top:12px}.filters select,.filters input{border:1px solid #202A3C19;background:#FFFFFFBA;border-radius:10px;padding:10px 12px;min-height:42px;color:#202A3C;font-size:12px;min-width:0}.filters input{flex:1;min-width:150px}.filters select:disabled{opacity:.45;cursor:not-allowed}.status{display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:10px;font-size:12px;color:var(--muted);margin:18px 3px}.status button{border:0;background:none;color:var(--gold);padding:8px;min-height:44px}.status-actions{display:flex;flex-wrap:wrap;gap:8px}.grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:23px}.item{min-width:0;overflow:hidden;border-radius:24px;background:linear-gradient(130deg,#FFFFFFE6,#FFFFFF85);border:1px solid #fff;box-shadow:0 18px 36px -30px #202A3C80;display:flex;flex-direction:column}.preview{display:block;border:0;padding:0;width:100%;background:#E8ECF1;overflow:hidden;aspect-ratio:1.62;position:relative}.preview img{width:100%;height:100%;object-fit:cover;object-position:top;display:block;transition:transform .3s}.item[data-kind=cards] .preview img,.item[data-kind=art] .preview img{object-fit:contain}.item[data-device=mobile][data-kind=site] .preview{background:linear-gradient(135deg,#E0E7EF,#F2F3F6)}.item[data-device=mobile][data-kind=site][data-view=page] .preview img{width:60%;height:auto;min-height:100%;margin:auto;box-shadow:0 0 35px #202A3C17}.item[data-view=chart] .preview img{object-fit:contain;object-position:center}.item[data-format=portrait] .preview img{object-fit:contain}.preview:hover img{transform:scale(1.015)}.info{padding:17px 18px 19px;display:flex;flex-direction:column;flex:1}.meta{display:flex;gap:6px;flex-wrap:wrap;font-size:10px;color:var(--muted);margin-bottom:9px}.badge{background:#CAD8E53B;border-radius:6px;padding:4px 6px}.info h2{font-size:15px;line-height:1.45;letter-spacing:-.025em;font-weight:650;margin:0 0 14px;overflow-wrap:anywhere}.links{display:flex;align-items:center;justify-content:space-between;gap:10px;margin-top:auto}.links button,.links a{font-size:11px;color:var(--gold);text-decoration:none;border:0;background:none;padding:7px 0;min-height:32px}.empty{grid-column:1/-1;padding:55px 20px;text-align:center;color:var(--muted);background:#ffffff70;border-radius:24px}.foot{margin-top:40px;font-size:11px;line-height:1.7;color:var(--muted)}.notice{color:#80642F}.hidden{display:none!important}
dialog{width:min(1380px,calc(100vw - 24px));max-height:calc(100dvh - 24px);padding:0;border:1px solid white;border-radius:22px;background:#F2F4F7;color:#202A3C;box-shadow:0 30px 100px #202A3C55}dialog::backdrop{background:#202A3CA6;backdrop-filter:blur(8px)}.dialog-head{display:flex;align-items:center;justify-content:space-between;gap:16px;padding:15px 20px}.dialog-head h2{font-size:15px;margin:0;line-height:1.4}.dialog-head button,.dialog-actions button,.dialog-actions a{border:1px solid #202A3C20;border-radius:10px;background:#FFFFFFAA;padding:10px 13px;min-height:42px;font-size:12px;text-decoration:none}.dialog-image{overflow:auto;text-align:center;background:#E5EAF0;max-height:70dvh;min-height:180px}.dialog-image img{display:block;max-width:100%;max-height:70dvh;object-fit:contain;margin:auto}.dialog-image.zoom img{max-width:none;max-height:none}.dialog-actions{display:flex;gap:8px;flex-wrap:wrap;padding:13px 20px}.dialog-details{padding:0 20px 18px;font-size:12px;color:var(--muted)}pre{white-space:pre-wrap;font:12px/1.65 Manrope,sans-serif;overflow-wrap:anywhere;max-height:180px;overflow:auto}summary{cursor:pointer;padding:8px 0}
@media(min-width:1800px){.grid{grid-template-columns:repeat(4,minmax(0,1fr))}}@media(max-width:1000px){.grid{grid-template-columns:repeat(2,minmax(0,1fr))}.hero{gap:12px}.hero-art{height:240px}}@media(max-width:640px){.top-link-long{display:none}.shell{padding-top:20px}.top{margin-bottom:28px}.top a{font-size:10px;padding:9px}.brand{font-size:17px}.hero{grid-template-columns:1fr;position:relative;overflow:hidden;min-height:0}.hero>div{position:relative;z-index:1}.hero-art{position:absolute;right:-55%;top:20px;width:100%;height:250px;opacity:.35}.hero h1{max-width:90%}.intro{max-width:88%;font-size:13px}.counts{gap:6px}.count{font-size:10px;padding:8px}.controls{position:relative;top:0;border-radius:18px;padding:10px}.tabs{gap:2px}.tabs button{padding:9px 10px;font-size:11px}.filters{gap:6px}.filters select{flex:1 1 42%;max-width:100%;font-size:11px;padding:9px}.filters input{flex-basis:100%}.grid{grid-template-columns:1fr;gap:18px}.status{font-size:10px}.dialog-head{padding:12px}.dialog-actions{padding:12px;gap:5px}.dialog-actions a,.dialog-actions button{font-size:10px;padding:8px}.dialog-head h2{font-size:12px}.dialog-image{max-height:66dvh}.dialog-image img{max-height:66dvh}}@media(prefers-reduced-motion:reduce){*{scroll-behavior:auto!important;transition:none!important}}

.review-panel{padding:0 20px 16px}.review-actions{display:flex;flex-wrap:wrap;gap:8px}.review-actions button{min-height:44px;border:1px solid #202A3C30;border-radius:10px;background:#FFFFFFB3;color:#202A3C;padding:10px 14px;font-size:12px}.review-actions button[aria-pressed=true]{background:#202A3C;color:#fff}.review-panel p{font-size:12px;color:var(--muted);margin:8px 0}.review-panel summary{font-size:12px}.review-panel textarea{display:block;width:100%;min-width:0;max-width:100%;margin-top:7px;padding:10px;border:1px solid #202A3C30;border-radius:10px;background:#fff;color:#202A3C;font-size:13px;resize:vertical}.review-badge[data-decision=approved]{color:#245847;background:#DFEBE5}.review-badge[data-decision=rework]{color:#74551F;background:#F2E7D0}@media(max-width:640px){.review-panel{padding:0 12px 12px}.review-actions{gap:5px}.review-actions button{font-size:11px;padding:8px 10px}.status-actions{gap:4px}}
</style></head><body><main class="shell"><header class="top"><div class="brand"><svg viewBox="0 0 40 44" aria-hidden="true"><path d="M8 38V17Q8 5 21 5H34V13H22Q17 13 17 19V20H31V28H17V38Z"/><path d="M29 30H35V38H29Z" fill="#AD8A48"/></svg>forecasteconomy</div><a href="http://localhost:3000" target="_blank" rel="noopener"><span class="top-link-long">Открыть локальный </span>сайт ↗</a></header>
<section class="hero"><div><div class="eyebrow">Коллекция для приёмки</div><h1>Экономика.<br><span>В новом свете.</span></h1><p class="intro">Карточки с реальными данными, страницы сайта и коллекция стеклянных иллюстраций. Всё в одном месте, в полном размере.</p><div class="counts" id="counts"></div></div><img class="hero-art" id="hero-art" alt="Стеклянная скульптура ForecastEconomy"></section>
<section class="controls" aria-label="Фильтры галереи"><div class="tabs"><button data-kind="featured" aria-pressed="true">Подборка</button><button data-kind="cards" aria-pressed="false">Карточки</button><button data-kind="site" aria-pressed="false">Сайт</button><button data-kind="art" aria-pressed="false">Иллюстрации</button></div><div class="filters"><select id="theme" aria-label="Тема"><option value="">Все темы</option></select><select id="locale" aria-label="Язык"><option value="">RU + EN</option><option value="ru">Русский</option><option value="en">English</option></select><select id="device" aria-label="Экран"><option value="">Все экраны</option><option value="mobile">Mobile / portrait</option><option value="desktop">Desktop / wide</option></select><select id="format" aria-label="Формат"><option value="">Все форматы</option><option value="wide">Wide</option><option value="portrait">Portrait</option><option value="screenshot">Скриншоты</option><option value="illustration">Иллюстрации</option></select><select id="view" aria-label="Вид сайта"><option value="">Все виды сайта</option><option value="page">Страница</option><option value="chart">График</option></select><select id="width" aria-label="Ширина экрана сайта в CSS-пикселях"><option value="">Любая ширина сайта</option></select><select id="decision" aria-label="Статус решения"><option value="">Все решения</option><option value="pending">Без решения</option><option value="approved">Утверждено</option><option value="rework">Доработать</option></select><input id="search" type="search" placeholder="Найти страницу или тему…" aria-label="Поиск"></div></section>
<div class="status"><span id="status" aria-live="polite"></span><div class="status-actions"><button id="reset">Сбросить фильтры</button><button id="export-decisions">Скачать решения JSON ↓</button></div></div><p id="storage-notice" class="notice hidden" role="alert"></p><section class="grid" id="grid" aria-label="Галерея"></section><footer class="foot"><p id="stage"></p><p>Числа и графики — из данных сайта. Иллюстрации — декоративный слой. Ссылки на страницы работают, когда локальный сайт запущен на порту 3000.</p><p><a href="gallery-data.json">Состав пакета JSON</a> · <a href="fonts/Manrope-OFL.txt">Лицензия шрифта</a></p></footer></main>
<dialog id="detail" aria-labelledby="detail-title"><div class="dialog-head"><h2 id="detail-title"></h2><button id="close" aria-label="Закрыть просмотр">✕</button></div><section class="review-panel" aria-label="Решение по изображению"><div class="review-actions"><button id="approve" type="button" aria-pressed="false">Утвердить</button><button id="rework" type="button" aria-pressed="false">Доработать</button><button id="clear-decision" type="button">Снять решение</button></div><p id="review-status" aria-live="polite"></p><details id="comment-details"><summary>Комментарий (необязательно)</summary><label class="quiet" for="review-comment">Что сохранить или изменить</label><textarea id="review-comment" rows="3" maxlength="4000" placeholder="Например: увеличить подписи оси…"></textarea></details></section><div class="dialog-image" id="image-stage"><img id="detail-image" alt=""></div><div class="dialog-actions"><button id="prev" aria-label="Предыдущее изображение">←</button><button id="next" aria-label="Следующее изображение">→</button><button id="zoom">Масштаб 100%</button><a id="original" target="_blank" rel="noopener">Открыть оригинал ↗</a><a id="source" target="_blank" rel="noopener">Страница сайта ↗</a></div><div class="dialog-details"><p id="detail-meta"></p><p id="prompt-document-wrap" class="hidden"><a id="prompt-document" target="_blank" rel="noopener"></a></p><details id="prompt"><summary>Промпт иллюстрации</summary><pre id="prompt-text"></pre></details></div></dialog>
<script type="application/json" id="gallery-data">${embedded}</script>
<script>
const data=JSON.parse(document.getElementById('gallery-data').textContent);
const el=id=>document.getElementById(id), grid=el('grid'), modal=el('detail');
const names={cards:'Карточка',site:'Сайт',art:'Иллюстрация'};
const views={page:'Страница',chart:'График'};
const filterIds=['theme','locale','device','format','view','width','decision','search'];
const state={kind:'featured'};let visible=[],current=-1,trigger=null,triggerItemId=null,openedItem=null;
const decisionNames={pending:'Без решения',approved:'Утверждено',rework:'Доработать'};
const reviewPrefix='forecasteconomy-design-review:v1:';
const reviewCache=new Map();
let storageFailed=false;
function reviewKey(item){return reviewPrefix+item.id+':'+item.assetHash}
function storageWarning(){storageFailed=true;el('storage-notice').classList.remove('hidden');el('storage-notice').textContent='Браузер не разрешил сохранить решения. До закрытия вкладки они доступны здесь; скачайте JSON, чтобы сохранить результат.'}
function reviewFor(item){
  const key=reviewKey(item);if(reviewCache.has(key))return reviewCache.get(key);
  let saved=null;try{saved=JSON.parse(localStorage.getItem(key)||'null')}catch{storageWarning()}
  const result={decision:['approved','rework'].includes(saved?.decision)?saved.decision:'pending',comment:typeof saved?.comment==='string'?saved.comment:'',updatedAt:saved?.updatedAt||null};
  reviewCache.set(key,result);return result
}
function syncReview(){
  if(!openedItem)return;const review=reviewFor(openedItem);
  el('approve').setAttribute('aria-pressed',String(review.decision==='approved'));
  el('rework').setAttribute('aria-pressed',String(review.decision==='rework'));
  el('clear-decision').disabled=review.decision==='pending';
  el('review-comment').value=review.comment;
  el('review-status').textContent=decisionNames[review.decision]+(storageFailed?' · только в этой вкладке':review.updatedAt?' · сохранено в этом браузере':'');
}
function saveReview(decision){
  if(!openedItem)return;
  const item=openedItem,review={decision,comment:el('review-comment').value,updatedAt:new Date().toISOString()};
  const key=reviewKey(item);reviewCache.set(key,review);
  try{localStorage.setItem(key,JSON.stringify(review))}catch{storageWarning()}
  for(const card of grid.querySelectorAll('.item'))if(card.dataset.itemId===item.id){card.dataset.decision=decision;const badge=card.querySelector('.review-badge');badge.dataset.decision=decision;badge.textContent=decisionNames[decision]}
  syncReview()
}
function exportDecisions(){
  const entries=data.items.map(item=>({id:item.id,assetHash:item.assetHash,title:item.title,kind:item.kind,theme:item.theme,locale:item.locale,format:item.format,view:item.view||null,width:item.width||null,image:item.image,page:item.page,...reviewFor(item)}));
  const payload={schemaVersion:1,exportedAt:new Date().toISOString(),galleryBuiltAt:data.builtAt,stage:data.stage,hashAlgorithm:'SHA-256',entries};
  const url=URL.createObjectURL(new Blob([JSON.stringify(payload,null,2)],{type:'application/json;charset=utf-8'}));
  const link=node('a');link.href=url;link.download='forecasteconomy-design-decisions-'+new Date().toISOString().slice(0,10)+'.json';document.body.append(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(url),1000)
}
function node(tag,text,cls){const e=document.createElement(tag);if(text!=null)e.textContent=text;if(cls)e.className=cls;return e}
function groupCount(kind){return data.items.filter(i=>i.kind===kind).length}
function sizeLabel(item){return item.width?item.width+' CSS px':item.format}
for(const [kind,title]of[['cards','карточек'],['site','снимков сайта'],['art','иллюстраций']]){
  const c=node('span',null,'count');c.append(node('strong',groupCount(kind)),document.createTextNode(title));el('counts').append(c)
}
const hero=data.items.find(i=>i.id==='art-forecast-glass')||data.items.find(i=>i.kind==='art');
if(hero)el('hero-art').src=hero.image;else el('hero-art').hidden=true;
const themes=[...new Map(data.items.map(i=>[i.theme,i.themeLabel])).entries()].sort((a,b)=>a[1].localeCompare(b[1],'ru'));
for(const [value,title]of themes){const o=node('option',title);o.value=value;el('theme').append(o)}
const widths=[...new Set(data.items.filter(i=>i.kind==='site'&&i.width).map(i=>i.width))].sort((a,b)=>a-b);
for(const width of widths){const o=node('option',width+' CSS px');o.value=String(width);el('width').append(o)}
el('stage').textContent=(data.stage?'Снимки: '+data.stage+(data.finalStage?'':' · предварительный этап'):'Снимки сайта ещё не добавлены')+' · сборка '+new Date(data.builtAt).toLocaleString('ru-RU');
if(data.warnings.length)el('stage').append(node('span',' · Предупреждений: '+data.warnings.length,'notice'));
function selection(items){
  const cards=items.filter(i=>i.kind==='cards').sort((a,b)=>(a.locale==='ru'?0:1)-(b.locale==='ru'?0:1)||(a.format==='wide'?0:1)-(b.format==='wide'?0:1));
  const site=items.filter(i=>i.kind==='site').sort((a,b)=>(a.locale==='ru'?0:1)-(b.locale==='ru'?0:1));
  if(!cards.length&&!site.length)return items.slice(0,12);
  const used=new Set(),chosen=[];
  for(const item of cards){const key=item.theme+'-'+item.format;if(!used.has(key)){used.add(key);chosen.push(item)}if(chosen.length===8)break}
  const sites=[],seen=new Set();
  const route=item=>{try{return new URL(item.page).pathname}catch{return item.id}};
  const parts=item=>route(item).split('/').filter(Boolean);
  // One route per slot: viewport, locale and chart crops must not turn the
  // opening overview into six versions of the same home page.
  const slots=[
    {match:p=>p.length===0,width:1440,view:'page'},
    {match:p=>p[0]==='russia'&&p[1]==='indicator'&&p.length===4&&/^[0-9]{4}$/.test(p[3]),width:390,view:'page'},
    {match:(p,i)=>p.length===1&&p[0]!=='russia'&&i.theme==='world',width:1440,view:'page'},
    {match:p=>p[0]==='united-states'&&p[1]==='region'&&p[2]!=='map'&&p.length===4,width:390,view:'chart'},
    {match:p=>p[0]==='russia'&&p[1]==='region'&&p[2]!=='map'&&p.length===3,width:1440,view:'page'},
    {match:p=>p.join('/')==='russia/demographics'||p[0]==='compare',width:1440,view:'chart'},
  ];
  const ranked=(items,slot)=>items.slice().sort((a,b)=>{
    const score=i=>[Number(Boolean(i.check)),i.locale==='ru'?0:1,(i.width<768)===(slot.width<768)?0:1,i.view===slot.view?0:1,Math.abs((i.width||0)-slot.width)];
    const aa=score(a),bb=score(b);for(let n=0;n<aa.length;n++){if(aa[n]!==bb[n])return aa[n]-bb[n]}return 0
  });
  for(const slot of slots){
    const item=ranked(site.filter(i=>!seen.has(route(i))&&slot.match(parts(i),i)),slot)[0];
    if(item){seen.add(route(item));sites.push(item)}
  }
  // Smaller or future acceptance sets still get distinct available routes.
  for(const item of ranked(site,{width:1440,view:'page'})){
    if(sites.length===6)break;if(!seen.has(route(item))){seen.add(route(item));sites.push(item)}
  }
  const out=[];while(chosen.length||sites.length){out.push(...chosen.splice(0,2),...sites.splice(0,1))}return out
}
function render(){
  const siteFilters=state.kind==='site'||state.kind==='featured';
  for(const id of['view','width']){el(id).disabled=!siteFilters;el(id).title=siteFilters?'':'Доступно во вкладках «Сайт» и «Подборка»'}
  const q=el('search').value.trim().toLocaleLowerCase();
  const theme=el('theme').value,locale=el('locale').value,device=el('device').value,format=el('format').value;
  const view=siteFilters?el('view').value:'',width=siteFilters?el('width').value:'',decision=el('decision').value;
  let items=data.items.filter(i=>
    (state.kind==='featured'?i.kind!=='art':i.kind===state.kind)&&
    (!theme||i.theme===theme)&&(!locale||i.locale===locale||i.locale==='neutral')&&
    (!device||i.device===device||i.device==='neutral')&&(!format||i.format===format)&&
    (!view||i.kind==='site'&&i.view===view)&&(!width||i.kind==='site'&&String(i.width)===width)&&(!decision||reviewFor(i).decision===decision)&&
    (!q||(i.title+' '+i.themeLabel+' '+(i.page||'')).toLocaleLowerCase().includes(q)));
  if(state.kind==='featured'&&!theme&&!locale&&!device&&!format&&!view&&!width&&!decision&&!q)items=selection(data.items);
  visible=items;grid.replaceChildren();
  el('status').textContent=items.length+' материалов'+(!groupCount('cards')&&state.kind==='featured'?' · реальные OG-карточки появятся после следующей сборки':'');
  if(!items.length){grid.append(node('p','Материалов с такими фильтрами пока нет.','empty'));return}
  for(const [index,item]of items.entries()){
    const card=node('article',null,'item');card.dataset.itemId=item.id;card.dataset.decision=reviewFor(item).decision;
    for(const key of['kind','device','format','view','width'])if(item[key]!=null)card.dataset[key]=String(item[key]);
    const preview=node('button',null,'preview');preview.setAttribute('aria-label','Открыть: '+item.title+(item.view?' — '+views[item.view]:''));
    const img=node('img');img.src=(item.thumbnail||item.image)+'?v='+item.assetHash;img.alt=item.title;img.loading=index<3?'eager':'lazy';img.decoding='async';preview.append(img);preview.onclick=()=>openItem(index,preview);
    const info=node('div',null,'info'),meta=node('div',null,'meta');
    for(const text of[names[item.kind],views[item.view],item.locale==='neutral'?'Без текста':item.locale.toUpperCase(),sizeLabel(item),item.check].filter(Boolean))meta.append(node('span',text,'badge'));
    const reviewBadge=node('span',decisionNames[reviewFor(item).decision],'badge review-badge');reviewBadge.dataset.decision=reviewFor(item).decision;meta.append(reviewBadge);info.append(meta,node('h2',item.title));
    const links=node('div',null,'links'),open=node('button','Посмотреть →');open.onclick=()=>openItem(index,open);links.append(open);
    if(item.page){const link=node('a','На сайте ↗');link.href=item.page;link.target='_blank';link.rel='noopener';links.append(link)}
    info.append(links);card.append(preview,info);grid.append(card)
  }
}
function openItem(index,button){
  if(!visible.length)return;current=(index+visible.length)%visible.length;const item=visible[current];openedItem=item;if(button){trigger=button;triggerItemId=item.id}
  el('detail-title').textContent=item.title;el('detail-image').src=item.image+'?v='+item.assetHash;el('detail-image').alt=item.title;el('original').href=item.image+'?v='+item.assetHash;
  el('source').classList.toggle('hidden',!item.page);if(item.page)el('source').href=item.page;
  el('detail-meta').textContent=[names[item.kind],views[item.view],item.themeLabel,item.locale==='neutral'?'Без текста':item.locale.toUpperCase(),sizeLabel(item),item.stage].filter(Boolean).join(' · ');
  el('prompt').classList.toggle('hidden',!item.prompt);el('prompt-text').textContent=item.prompt||'';el('prompt').open=false;
  el('prompt-document-wrap').classList.toggle('hidden',!item.promptDocument);
  if(item.promptDocument){el('prompt-document').href=item.promptDocument;el('prompt-document').textContent=item.promptLabel||'Документ промпта ↗'}
  el('image-stage').classList.remove('zoom');el('zoom').textContent='Масштаб 100%';syncReview();el('comment-details').open=Boolean(reviewFor(item).comment);if(!modal.open)modal.showModal()
}
for(const button of document.querySelectorAll('.tabs [data-kind]'))button.onclick=()=>{state.kind=button.dataset.kind;for(const b of document.querySelectorAll('.tabs button'))b.setAttribute('aria-pressed',String(b===button));render()};
for(const id of filterIds)el(id).addEventListener(id==='search'?'input':'change',render);
el('approve').onclick=()=>saveReview('approved');el('rework').onclick=()=>saveReview('rework');el('clear-decision').onclick=()=>saveReview('pending');el('review-comment').addEventListener('input',()=>saveReview(reviewFor(openedItem).decision));el('export-decisions').onclick=exportDecisions;
el('reset').onclick=()=>{for(const id of filterIds)el(id).value='';render()};
el('close').onclick=()=>modal.close();modal.addEventListener('close',()=>{const itemId=triggerItemId||openedItem?.id;render();const target=[...grid.querySelectorAll('.item')].find(e=>e.dataset.itemId===itemId)?.querySelector(trigger?.classList.contains('preview')?'.preview':'.links button');(target||el('reset')).focus();openedItem=null});el('prev').onclick=()=>openItem(current-1);el('next').onclick=()=>openItem(current+1);
el('zoom').onclick=()=>{const zoom=el('image-stage').classList.toggle('zoom');el('zoom').textContent=zoom?'Вписать в окно':'Масштаб 100%'};
modal.addEventListener('keydown',event=>{if(['INPUT','TEXTAREA'].includes(event.target.tagName))return;if(event.key==='ArrowLeft'){event.preventDefault();openItem(current-1)}if(event.key==='ArrowRight'){event.preventDefault();openItem(current+1)}});render();
</script></body></html>`;
}

async function signature() {
  const paths = [join(output, 'cards/manifest.json'), artwork, promptSource];
  for (const stage of await stages()) paths.push(stage.path);
  for (const path of [artwork, promptSource, join(output, 'cards')]) {
    for (const name of await list(path)) paths.push(join(path, name));
  }
  return Promise.all(paths.map(async (path) => { try { const info = await stat(path); return `${path}:${info.mtimeMs}:${info.size}`; } catch { return path; } })).then((rows) => rows.join('|'));
}

await build();
if (watch) {
  let previous = await signature();
  console.log('Watching cards, screenshots stages, artwork and prompts. Ctrl+C to stop.');
  let busy = false;
  setInterval(async () => {
    if (busy) return;
    busy = true;
    try {
      const next = await signature();
      if (next !== previous) { await build(); previous = next; }
    } catch (error) { console.error(`Build postponed: ${error.message}`); }
    finally { busy = false; }
  }, 3000);
}
