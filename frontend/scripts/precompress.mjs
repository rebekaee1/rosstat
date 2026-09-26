#!/usr/bin/env node
/**
 * Предсжатие хэшированных ассетов после `vite build`.
 *
 * Рядом с каждым dist/assets/*.{js,css,svg,json} кладём `.gz` (gzip -9).
 * nginx отдаёт их через `gzip_static on` (location /assets/) — это на ~5–8 %
 * меньше, чем on-the-fly gzip_comp_level 4, и без CPU nginx на каждом запросе.
 * Файлы без выигрыша (< 1 КБ или сжатие хуже 95 %) не пишем.
 *
 * Brotli (`--brotli`, ещё −15…20 % к gzip) выключен по умолчанию: nginx:alpine
 * не содержит ngx_brotli, и `.br` просто лежали бы мёртвым грузом.
 * Использование: node scripts/precompress.mjs [distDir] [--brotli]
 */
import { readdirSync, readFileSync, statSync, writeFileSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { brotliCompressSync, constants, gzipSync } from 'node:zlib';

const args = process.argv.slice(2);
const withBrotli = args.includes('--brotli');
const distDir = resolve(args.find((arg) => !arg.startsWith('--')) || 'dist');
const assetsDir = join(distDir, 'assets');
const COMPRESSIBLE = /\.(?:js|mjs|css|svg|json|txt|map)$/;
const MIN_BYTES = 1024;

let files = 0;
let rawTotal = 0;
let gzTotal = 0;
for (const name of readdirSync(assetsDir)) {
  if (!COMPRESSIBLE.test(name)) continue;
  const file = join(assetsDir, name);
  if (!statSync(file).isFile()) continue;
  const raw = readFileSync(file);
  if (raw.length < MIN_BYTES) continue;
  const gz = gzipSync(raw, { level: 9 });
  if (gz.length >= raw.length * 0.95) continue;
  writeFileSync(`${file}.gz`, gz);
  if (withBrotli) {
    const br = brotliCompressSync(raw, {
      params: {
        [constants.BROTLI_PARAM_QUALITY]: 11,
        [constants.BROTLI_PARAM_SIZE_HINT]: raw.length,
      },
    });
    writeFileSync(`${file}.br`, br);
  }
  files += 1;
  rawTotal += raw.length;
  gzTotal += gz.length;
}
const kb = (bytes) => `${(bytes / 1024).toFixed(1)} KB`;
console.log(`precompress: ${files} files, ${kb(rawTotal)} → ${kb(gzTotal)} gzip${withBrotli ? ' (+br)' : ''}`);
