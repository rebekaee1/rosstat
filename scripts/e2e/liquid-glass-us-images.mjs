/** Preserve before/after PNG evidence for the bounded US source-label correction.
 * Run only after the main suite, never in parallel with its network requests.
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { createHash } from 'node:crypto';
import { setTimeout as delay } from 'node:timers/promises';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const phase = process.argv.find(a => a.startsWith('--phase='))?.split('=')[1] || 'before';
if (!['before', 'after'].includes(phase)) throw Error('Expected before or after');
const initial = JSON.parse(fs.readFileSync(path.join(root, 'docs/design/local-acceptance/final/all.json')));
const chosen = new Set(['us-region-indicator', 'us-region-annual', 'us-region-quarterly']);
const report = { at: new Date().toISOString(), phase, initialSuiteAt: initial.at, images: [], issues: [], limitations: ['Paced local requests, not performance measurements.'] };
const out = path.join(root, 'output/design-acceptance/2026-09-24', `final-us-images-${phase}`);
fs.mkdirSync(out, { recursive: true });
const seen = new Set();
for (const row of initial.http.filter(r => chosen.has(r.id))) for (const item of row.media || []) {
  const url = new URL(item.local);
  if (!['127.0.0.1', 'localhost'].includes(url.hostname)) throw Error('Loopback only');
  if (seen.has(url.href)) continue;
  seen.add(url.href);
  await delay(950);
  const response = await fetch(url, { redirect: 'error' });
  const png = Buffer.from(await response.arrayBuffer());
  const file = `${row.id}-${row.locale}-${url.searchParams.has('portrait') ? 'portrait' : 'landscape'}.png`;
  const image = { id: row.id, locale: row.locale, url: url.href, status: response.status, type: response.headers.get('content-type'), bytes: png.length, sha256: createHash('sha256').update(png).digest('hex') };
  if (png.length > 24 && png.subarray(1, 4).toString() === 'PNG') {
    image.width = png.readUInt32BE(16); image.height = png.readUInt32BE(20);
    fs.writeFileSync(path.join(out, file), png); image.path = path.relative(root, path.join(out, file));
  }
  if (response.status !== 200 || !image.path) report.issues.push({ id: image.id, url: image.url, status: response.status });
  report.images.push(image);
}
if (report.images.length !== 12) report.issues.push({ expectedImages: 12, actualImages: report.images.length });
if (phase === 'after') {
  const before = JSON.parse(fs.readFileSync(path.join(root, 'docs/design/local-acceptance/final-us-images-before.json')));
  report.comparison = report.images.map(i => ({ url: i.url, changed: before.images.find(b => b.url === i.url)?.sha256 !== i.sha256 }));
}
fs.writeFileSync(path.join(root, `docs/design/local-acceptance/final-us-images-${phase}.json`), JSON.stringify(report, null, 2) + '\n');
console.log(JSON.stringify({ phase, images: report.images.length, issues: report.issues, changed: report.comparison?.filter(i => i.changed).length }));
process.exitCode = report.issues.length ? 1 : 0;
