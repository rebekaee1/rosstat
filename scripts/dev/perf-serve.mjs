#!/usr/bin/env node
/**
 * Локальный стенд для замера скорости (только чтение боевого, одинаковые условия «до» и «после»).
 *
 * Что делает:
 *   - отдаёт собранный `frontend/dist` как nginx фронтенда: HTTP/2 по TLS, `.gz` рядом с хэшированными файлами
 *     (gzip_static), `Cache-Control: public, immutable` у /assets/, no-store у HTML, тот же состав заголовков кэша;
 *   - страницы отдаёт из СНИМКОВ боевой SSR-страницы (`--snap DIR/{en,ru}/{home,russia,cpi,compare,world,germany}.html`),
 *     в которые подставлена шапка текущей сборки теми же функциями, что у backend (`perf_ssr_shell.py`):
 *     так видны и изменения в сборке, и в том, как backend подключает ассеты;
 *   - /api/* и остальное, что у nginx идёт на backend, проксирует на `--api` (боевой, только GET) и записывает в
 *     `--cache DIR`; повторы идут с диска с задержкой `--api-delay` мс (серверное время фиксировано, боевой не нагружается);
 *   - язык задаёт хост: `en.localhost` (английская версия), `ru.localhost` (русская). Chrome ведёт *.localhost на петлю.
 *
 * Пример:
 *   node scripts/dev/perf-serve.mjs --dist frontend/dist --snap ../.artifacts/circle-12/data/snap --port 5290
 *   → https://en.localhost:5290/ , https://ru.localhost:5290/russia  (сертификат самоподписанный: --ignore-certificate-errors)
 *
 * Параметры: --no-br (не отдавать .br, как до brotli), --dist, --snap, --port (5290), --api (https://forecasteconomy.com), --cache (./.perf-cache),
 *            --api-delay (120), --html-delay (250: время ответа backend на SSR-страницу), --record (разрешить сходить
 *            на боевой за тем, чего нет в кэше; по умолчанию 404 для незаписанного).
 */
import fs from 'node:fs';
import path from 'node:path';
import http2 from 'node:http2';
import zlib from 'node:zlib';
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const args = Object.fromEntries(process.argv.slice(2).reduce((acc, a, i, all) => {
  if (a.startsWith('--')) acc.push([a.slice(2), all[i + 1] && !all[i + 1].startsWith('--') ? all[i + 1] : true]);
  return acc;
}, []));
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const DIST = path.resolve(String(args.dist || path.join(ROOT, 'frontend/dist')));
const SNAP = args.snap ? path.resolve(String(args.snap)) : null;
const PORT = Number(args.port || 5290);
const API = String(args.api || 'https://forecasteconomy.com').replace(/\/$/, '');
const CACHE = path.resolve(String(args.cache || '.perf-cache'));
const API_DELAY = Number(args['api-delay'] ?? 120);
const HTML_DELAY = Number(args['html-delay'] ?? 250);
const RECORD = Boolean(args.record);
const UA = 'Mozilla/5.0 (Linux; Android 11; Moto G Power (2022)) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Mobile Safari/537.36';

fs.mkdirSync(path.join(CACHE, 'api'), { recursive: true });

// --- TLS (самоподписанный, один раз) ---------------------------------------------------------
const keyFile = path.join(CACHE, 'key.pem');
const certFile = path.join(CACHE, 'cert.pem');
if (!fs.existsSync(certFile)) {
  execFileSync('openssl', ['req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-keyout', keyFile, '-out', certFile,
    '-days', '30', '-subj', '/CN=localhost', '-addext', 'subjectAltName=DNS:localhost,DNS:*.localhost,DNS:en.localhost,DNS:ru.localhost'],
  { stdio: 'ignore' });
}

// --- Шапка текущей сборки для SSR-снимков -----------------------------------------------------
const shellPy = path.join(ROOT, 'backend/.venv/bin/python');
function loadShell() {
  const out = execFileSync(shellPy, [path.join(ROOT, 'scripts/dev/perf_ssr_shell.py'), path.join(DIST, 'index.html')],
    { encoding: 'utf8', cwd: ROOT });
  return JSON.parse(out);
}
const SHELL = loadShell();

const PAGE_FILES = new Map([
  ['/', 'home'], ['/russia', 'russia'], ['/russia/indicator/cpi', 'cpi'], ['/compare', 'compare'],
  ['/world/rating', 'world'], ['/world/rating/gdp-usd', 'world'], ['/germany', 'germany'],
]);

/** Заменить в снимке боевой страницы всё, что backend берёт из оболочки Vite (ссылки на /assets, /fonts, скрипт входа). */
export function patchSnapshot(html) {
  const useLcp = /<link[^>]+rel="preload"[^>]+as="image"/.test(html);
  const parts = useLcp ? SHELL.lcp : SHELL.plain;
  const lines = html.split('\n');
  const isShellLine = (l) => (/^\s*(<noscript>)?<link\b/.test(l) && /\/(assets|fonts)\/[^"']+/.test(l) && !/rel="alternate"/.test(l))
    || /^\s*<script\b[^>]*src="\/assets\//.test(l);
  const out = [];
  let headInserted = false;
  let bodyInserted = false;
  let lateIdx = -1;
  for (const l of lines) {
    if (isShellLine(l)) {
      if (/^\s*<script\b/.test(l)) {
        if (!bodyInserted) { out.push(parts.body_scripts); bodyInserted = true; }
      } else if (!headInserted) {
        out.push(parts.css_preload, parts.head_early);
        headInserted = true;
      }
      continue;
    }
    if (lateIdx < 0 && /<script type="application\/ld\+json">/.test(l)) {
      lateIdx = out.length;
    }
    // старые иконки (head_late в бою) убираем и ставим заново из оболочки
    if (/^\s*<link\b[^>]*(rel="icon"|rel="shortcut icon"|rel="manifest"|rel="apple-touch-icon")/.test(l)
      || /^\s*<link\b[^>]*href="\/(favicon|manifest|apple-touch-icon)/.test(l)) continue;
    out.push(l);
  }
  if (lateIdx >= 0) out.splice(lateIdx, 0, parts.head_late);
  return out.join('\n');
}

// --- Вспомогательное ---------------------------------------------------------------------------
const MIME = {
  '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.mjs': 'text/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8', '.json': 'application/json', '.svg': 'image/svg+xml', '.png': 'image/png',
  '.jpg': 'image/jpeg', '.webp': 'image/webp', '.ico': 'image/x-icon', '.woff2': 'font/woff2', '.woff': 'font/woff',
  '.txt': 'text/plain; charset=utf-8', '.webmanifest': 'application/manifest+json', '.xml': 'application/xml',
};
const COMPRESSIBLE = /^(text\/|application\/(json|javascript|xml|manifest)|image\/svg)/;
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

function cacheControlFor(urlPath) {
  if (urlPath === '/assets/behavior-standalone.js') return 'no-cache, must-revalidate';
  if (urlPath.startsWith('/assets/')) return 'public, max-age=31536000, immutable';
  if (urlPath === '/fonts/fonts.css') return 'public, max-age=86400';
  if (urlPath === '/consent.js' || urlPath === '/seo-ticker.js') return 'no-cache, must-revalidate';
  if (urlPath === '/sw.js') return 'no-cache, no-store, must-revalidate';
  if (/\.(svg|png|jpg|ico|webp|woff2?)$/.test(urlPath)) return 'public, max-age=2592000';
  return 'no-cache';
}

function accepts(req, enc) {
  return String(req.headers['accept-encoding'] || '').includes(enc);
}

function send(stream, req, status, headers, body, { compress = true } = {}) {
  let payload = Buffer.isBuffer(body) ? body : Buffer.from(body);
  const h = { ...headers, ':status': status };
  const type = String(h['content-type'] || '');
  if (compress && payload.length >= 512 && COMPRESSIBLE.test(type) && !h['content-encoding'] && accepts(req, 'gzip')) {
    payload = zlib.gzipSync(payload, { level: 4 });
    h['content-encoding'] = 'gzip';
    h.vary = 'Accept-Encoding';
  }
  h['content-length'] = String(payload.length);
  stream.respond(h);
  stream.end(payload);
}

function serveFile(stream, req, file, urlPath) {
  const ext = path.extname(file);
  const headers = { 'content-type': MIME[ext] || 'application/octet-stream', 'cache-control': cacheControlFor(urlPath) };
  const br = `${file}.br`;
  // как nginx.conf: br для js/css в /assets/ (map по Accept-Encoding + try_files), иначе .gz (gzip_static)
  if (/^\/assets\/.+\.(js|mjs|css)$/.test(urlPath) && !args['no-br'] && fs.existsSync(br) && accepts(req, 'br')) {
    const body = fs.readFileSync(br);
    headers['content-encoding'] = 'br';
    headers.vary = 'Accept-Encoding';
    headers['content-length'] = String(body.length);
    stream.respond({ ...headers, ':status': 200 });
    stream.end(body);
    return;
  }
  const gz = `${file}.gz`;
  if (urlPath.startsWith('/assets/') && fs.existsSync(gz) && accepts(req, 'gzip')) {
    const body = fs.readFileSync(gz);
    headers['content-encoding'] = 'gzip';
    headers.vary = 'Accept-Encoding';
    headers['content-length'] = String(body.length);
    stream.respond({ ...headers, ':status': 200 });
    stream.end(body);
    return;
  }
  send(stream, req, 200, headers, fs.readFileSync(file));
}

function hostLocale(host) {
  const h = String(host || '').split(':')[0].toLowerCase();
  return h.startsWith('ru.') ? 'ru' : 'en';
}

// --- API: запись/повтор ---------------------------------------------------------------------------
async function apiResponse(req, urlPath, search, locale) {
  const key = Buffer.from(`${locale}|${req.headers[':method']}|${urlPath}${search}`).toString('base64url').slice(0, 180);
  const file = path.join(CACHE, 'api', `${key}.json`);
  if (fs.existsSync(file)) return JSON.parse(fs.readFileSync(file, 'utf8'));
  if (!RECORD) return null;
  if (req.headers[':method'] !== 'GET') return null;
  // --api http://127.0.0.1:18080 — стенд/локальный backend без поддоменов: язык задаёт заголовок X-FE-Locale.
  const plain = /^http:/.test(API);
  const origin = !plain && locale === 'ru' ? API.replace('://', '://ru.') : API;
  const res = await fetch(`${origin}${urlPath}${search}`, { headers: { 'user-agent': UA, accept: req.headers.accept || '*/*', ...(plain ? { 'x-fe-locale': locale } : {}) } });
  const body = Buffer.from(await res.arrayBuffer());
  const rec = {
    status: res.status,
    type: res.headers.get('content-type') || 'application/octet-stream',
    cacheControl: res.headers.get('cache-control') || '',
    body: body.toString('base64'),
  };
  if (res.status < 500) fs.writeFileSync(file, JSON.stringify(rec));
  return rec;
}

/**
 * Сторонние скрипты (Яндекс.Метрика и пр.): браузер запускается с --host-resolver-rules, который ведёт чужие хосты сюда.
 * Файлы .js/.css/.html один раз записываются с настоящего хоста (обычный публичный GET, это не хит в счётчик) и дальше
 * отдаются отсюда, поэтому вес и время исполнения настоящие, а хитов в Метрику не создаётся.
 * Всё остальное (watch, адверты, gif) получает пустой ответ.
 */
async function externalResponse(urlPath, search) {
  const m = /^\/__ext\/([^/]+)(\/.*)?$/.exec(urlPath);
  if (!m) return null;
  const host = m[1];
  const rest = m[2] || '/';
  const ext = path.extname(rest).toLowerCase();
  const file = path.join(CACHE, 'ext', host, rest.replace(/[^A-Za-z0-9._-]/g, '_') + (search ? `.${Buffer.from(search).toString('base64url').slice(0, 24)}` : ''));
  if (fs.existsSync(file)) return { type: MIME[ext] || 'application/octet-stream', body: fs.readFileSync(file) };
  const staticLike = ['.js', '.css', '.html'].includes(ext) && /(yandex|yastatic|webvisor)/.test(host) && !/\/watch\//.test(rest);
  if (RECORD && staticLike) {
    const res = await fetch(`https://${host}${rest}${search}`, { headers: { 'user-agent': UA } });
    if (res.ok) {
      const body = Buffer.from(await res.arrayBuffer());
      fs.mkdirSync(path.dirname(file), { recursive: true });
      fs.writeFileSync(file, body);
      return { type: res.headers.get('content-type') || MIME[ext], body };
    }
  }
  return { type: MIME[ext] || 'text/plain', body: Buffer.alloc(0) };
}

const BACKEND_PREFIXES = ['/api/', '/manifest.webmanifest', '/offline.html', '/feed.xml', '/robots.txt', '/llms.txt', '/og/'];

const server = http2.createSecureServer({
  key: fs.readFileSync(keyFile), cert: fs.readFileSync(certFile), allowHTTP1: true,
});
server.on('request', async (req, res) => {
  // Совместимость: на HTTP/2 stream в res.stream, на HTTP/1.1 нет — для локального замера нужен только h2.
  const stream = res.stream;
  if (!stream) { res.statusCode = 505; res.end('h2 only'); return; }
  const h2req = { headers: { ...req.headers, ':method': req.method } };
  try {
    const url = new URL(req.url, 'https://localhost');
    const p = decodeURIComponent(url.pathname);
    const locale = hostLocale(req.headers[':authority'] || req.headers.host);

    const authority = String(req.headers[':authority'] || req.headers.host || '').split(':')[0].toLowerCase();
    if (authority && !authority.endsWith('localhost')) {
      // чужой хост, направленный сюда правилом --host-resolver-rules (Метрика и т.п.)
      const ext = await externalResponse(`/__ext/${authority}${url.pathname}`, url.search);
      send(stream, h2req, 200, { 'content-type': ext.type, 'cache-control': 'public, max-age=3600', 'access-control-allow-origin': '*' }, ext.body);
      return;
    }

    if (BACKEND_PREFIXES.some((x) => p.startsWith(x))) {
      const rec = await apiResponse(h2req, url.pathname, url.search, locale);
      await sleep(API_DELAY);
      if (!rec) { send(stream, h2req, 404, { 'content-type': 'application/json' }, '{"detail":"not recorded"}'); return; }
      send(stream, h2req, rec.status, {
        'content-type': rec.type,
        'cache-control': rec.cacheControl || 'no-cache',
      }, Buffer.from(rec.body, 'base64'));
      return;
    }

    // Статика
    const file = path.join(DIST, p);
    if (p !== '/' && file.startsWith(DIST) && fs.existsSync(file) && fs.statSync(file).isFile()) {
      serveFile(stream, h2req, file, p);
      return;
    }
    if (p.startsWith('/assets/')) { send(stream, h2req, 404, { 'content-type': 'text/plain' }, 'not found'); return; }

    // HTML
    await sleep(HTML_DELAY);
    let name = PAGE_FILES.get(p);
    if (!name && /^\/[a-z-]+$/.test(p) && !['/about', '/login', '/register', '/account'].includes(p)) name = 'germany';
    const snapFile = SNAP && name ? path.join(SNAP, locale, `${name}.html`) : null;
    let html;
    if (snapFile && fs.existsSync(snapFile)) html = patchSnapshot(fs.readFileSync(snapFile, 'utf8'));
    else html = fs.readFileSync(path.join(DIST, 'index.html'), 'utf8');
    send(stream, h2req, 200, {
      'content-type': 'text/html; charset=utf-8',
      'cache-control': 'no-cache, no-store, must-revalidate',
    }, html);
  } catch (err) {
    console.error('perf-serve error', req.url, err);
    try { send(stream, h2req, 500, { 'content-type': 'text/plain' }, String(err)); } catch { /* ответ уже начат */ }
  }
});
server.listen(PORT, '127.0.0.1', () => {
  console.log(`perf-serve: https://en.localhost:${PORT}  https://ru.localhost:${PORT}  dist=${DIST} snap=${SNAP || '—'} api=${RECORD ? 'record' : 'replay'}`);
});
