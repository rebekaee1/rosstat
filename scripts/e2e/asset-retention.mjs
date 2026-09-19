#!/usr/bin/env node
// Isolated real Vite builds + Chromium. No app/dev server, Docker or production.
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { createServer } from 'node:http';
import { mkdtemp, mkdir, readFile, realpath, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { build } from '../../frontend/node_modules/vite/dist/node/index.js';
import { chromium } from '../../frontend/node_modules/playwright/index.mjs';

const repo = resolve(dirname(fileURLToPath(import.meta.url)), '../..');
const tmp = await realpath(await mkdtemp(join(tmpdir(), 'fe-retention-')));
const archive = join(tmp, 'archive');
const builds = {};
let current = 'A';
let retention = false;
let server;
let browser;
const archiveCommand = (command, source) => execFileSync('python3', [
  join(repo, 'scripts/frontend-asset-archive.py'), command,
  '--archive', archive, ...(source ? ['--source', source] : []),
]);
try {
  for (const label of ['A', 'B']) {
    const root = join(tmp, label);
    await mkdir(root);
    await writeFile(join(root, 'index.html'), '<div id="result">ready</div><button id="lazy">navigate</button><script type="module" src="/main.js"></script>');
    await writeFile(join(root, 'lazy.js'), `export const value = 'release-${label}';`);
    await writeFile(join(root, 'main.js'), `
      import { createChunkRecovery } from ${JSON.stringify(join(repo, 'frontend/src/lib/chunkRecovery.js'))};
      const recovery = createChunkRecovery({release: import.meta.url, getStorage: () => window.sessionStorage, reload: () => window.location.reload()});
      window.addEventListener('vite:preloadError', recovery);
      window.testRecovery = recovery;
      window.loadedRelease = ${JSON.stringify(label)};
      document.querySelector('#lazy').onclick = async () => {
        try { document.querySelector('#result').textContent = (await import('./lazy.js')).value; }
        catch { document.querySelector('#result').textContent = 'missing chunk'; }
      };
    `);
    await build({ configFile: false, root, logLevel: 'error', build: { outDir: 'dist' } });
    builds[label] = join(root, 'dist');
    archiveCommand('publish', builds[label]);
  }
  server = createServer(async (req, res) => {
    const path = new URL(req.url, 'http://localhost').pathname;
    const file = path === '/' ? '/index.html' : path;
    let content;
    try { content = await readFile(join(builds[current], file)); }
    catch {
      if (retention && file.startsWith('/assets/')) {
        try { content = await readFile(join(archive, file)); } catch { /* 404 below */ }
      }
    }
    if (!content) { res.writeHead(404); res.end('not found'); return; }
    res.setHeader('Content-Type', file.endsWith('.js') ? 'text/javascript' : 'text/html');
    res.setHeader('Cache-Control', 'no-store');
    res.end(content);
  });
  await new Promise((done) => server.listen(0, '127.0.0.1', done));
  browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();
  const origin = `http://127.0.0.1:${server.address().port}`;
  // Baseline: old Vite build loses its lazy chunk; disable recovery to expose 404.
  await page.goto(origin);
  await page.waitForFunction(() => window.loadedRelease === 'A');
  await page.evaluate(() => window.removeEventListener('vite:preloadError', window.testRecovery));
  current = 'B';
  const missing = page.waitForResponse((r) => r.status() === 404 && r.url().includes('/assets/'));
  await page.click('#lazy');
  await missing;
  await page.waitForFunction(() => document.querySelector('#result').textContent === 'missing chunk');
  console.log('PASS baseline: old tab produces lazy chunk 404 without archive');

  current = 'A';
  await page.goto(origin);
  await page.waitForFunction(() => window.loadedRelease === 'A');
  let navigations = 0;
  const badResponses = [];
  page.on('framenavigated', () => navigations++);
  page.on('response', (response) => { if (response.status() >= 400) badResponses.push(response.url()); });
  retention = true;
  current = 'B';
  await page.click('#lazy');
  await page.waitForFunction(() => document.querySelector('#result').textContent === 'release-A');
  assert.equal(navigations, 0, 'retained lazy navigation must not reload');
  assert.deepEqual(badResponses, [], 'retained lazy navigation must not 404');
  console.log('PASS old A tab -> B build -> A lazy import: no 404 and no reload');

  await page.goto(origin);
  await page.waitForFunction(() => window.loadedRelease === 'B');
  await page.evaluate(() => window.dispatchEvent(new Event('vite:preloadError', { cancelable: true })));
  await page.waitForEvent('load');
  await page.waitForFunction(() => window.loadedRelease === 'B');
  const afterRecovery = navigations;
  await page.evaluate(() => {
    for (let i = 0; i < 20; i++) window.dispatchEvent(new Event('vite:preloadError', { cancelable: true }));
  });
  await page.waitForTimeout(250);
  assert.equal(navigations, afterRecovery, 'same build must not loop after reload');
  console.log('PASS reload guard persists across document reload and repeated errors');

  const privatePage = await browser.newPage();
  await privatePage.addInitScript(() => Object.defineProperty(window, 'sessionStorage', {
    get() { throw new DOMException('blocked', 'SecurityError'); },
  }));
  await privatePage.goto(origin);
  await privatePage.waitForFunction(() => window.loadedRelease === 'B');
  const cancelled = await privatePage.evaluate(() => !window.dispatchEvent(new Event('vite:preloadError', { cancelable: true })));
  assert.equal(cancelled, false, 'storage failure must preserve error UI, not reload');
  console.log('PASS blocked sessionStorage: no exception, no reload, error not swallowed');
  archiveCommand('prune');
} finally {
  await browser?.close();
  if (server) await new Promise((done) => server.close(done));
  await rm(tmp, { recursive: true, force: true });
}
