// Страж «никакого пикселя» (принцип владельца №9, круг 6, зона I): растр ставится только с запасом пикселей на показ.
// Читает public/brand/manifest.json (px, max_display_px, dpr) и сверяет его с диском и с исходниками:
//   1. каждый файл public/brand, public/art, public/icons есть в манифесте (новый растр без записи роняет тест);
//   2. заявленный px равен настоящей ширине файла (читается из заголовка webp/png);
//   3. px >= max_display_px x dpr; dpr < 2 разрешён только у мягких фонов (`soft` с причиной, не ниже 0.75), у значков ОС
//      (`external`, номинальный размер задаёт платформа) и у кадра для DPR 1 в srcset (`fallback_of` — кадр DPR 2-3 с dpr >= 2);
//   4. файл с used=false или defect не подключён в src, а ссылки из src на /brand/ и /art/ ведут на файл из манифеста.
// Записи с `pending` (замена или удаление в другой зоне) тест не роняют, но выводит списком: это долг, а не норма.
// Таблица для людей: python3 scripts/dev/check-raster-dpr.py (считает показ по CSS и сверяет его с манифестом).
import { readdirSync, readFileSync, statSync } from 'node:fs';
import { dirname, extname, join, relative } from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';

const here = dirname(fileURLToPath(import.meta.url));
const src = join(here, '..');
const publicDir = join(src, '..', 'public');
const manifest = JSON.parse(readFileSync(join(publicDir, 'brand', 'manifest.json'), 'utf8'));
const entries = manifest.files;
const GUARDED_DIRS = ['brand', 'art', 'icons'];
const IMAGE_EXT = new Set(['.webp', '.png', '.jpg', '.jpeg', '.svg', '.gif', '.avif']);

function walk(dir, out = []) {
  for (const name of readdirSync(dir)) {
    const full = join(dir, name);
    if (statSync(full).isDirectory()) {
      if (name === 'node_modules' || name === 'embed') continue;
      walk(full, out);
    } else out.push(full);
  }
  return out;
}

/** Ширина растра из заголовка файла (без зависимостей). */
export function imageWidth(file) {
  const buf = readFileSync(file);
  const ext = extname(file).toLowerCase();
  if (ext === '.png') return buf.readUInt32BE(16);
  if (ext === '.webp') {
    const kind = buf.toString('ascii', 12, 16);
    if (kind === 'VP8X') return 1 + buf.readUIntLE(24, 3);
    if (kind === 'VP8L') return (buf.readUInt32LE(21) & 0x3fff) + 1;
    if (kind === 'VP8 ') return buf.readUInt16LE(26) & 0x3fff;
    throw new Error(`webp: неизвестный блок ${kind} в ${file}`);
  }
  if (ext === '.jpg' || ext === '.jpeg') {
    let i = 2;
    while (i < buf.length) {
      if (buf[i] !== 0xff) { i += 1; continue; }
      const marker = buf[i + 1];
      if (marker >= 0xc0 && marker <= 0xcf && ![0xc4, 0xc8, 0xcc].includes(marker)) return buf.readUInt16BE(i + 7);
      i += 2 + buf.readUInt16BE(i + 2);
    }
  }
  throw new Error(`не удалось прочитать ширину ${file}`);
}

const guardedFiles = GUARDED_DIRS.flatMap((d) => walk(join(publicDir, d)))
  .filter((f) => IMAGE_EXT.has(extname(f).toLowerCase()))
  .map((f) => relative(publicDir, f).split('\\').join('/'));

const srcFiles = walk(src).filter((f) => /\.(css|jsx?)$/.test(f) && !/\.test\.jsx?$/.test(f));
const srcText = srcFiles.map((f) => [relative(src, f), readFileSync(f, 'utf8')]);

describe('no-lowres: растры не ниже 2x от размера показа', () => {
  it('манифест читается и не пуст', () => {
    expect(Object.keys(entries).length).toBeGreaterThan(10);
  });

  it('каждый растр и вектор из public/brand, public/art, public/icons внесён в манифест', () => {
    const missing = guardedFiles.filter((f) => !(f in entries));
    expect(missing, `нет в manifest.json: ${missing.join(', ')}`).toEqual([]);
  });

  it('каждая запись манифеста ведёт на существующий файл', () => {
    const gone = Object.keys(entries).filter((k) => !guardedFiles.includes(k) && !entries[k].pending);
    expect(gone, `в манифесте есть, файла нет: ${gone.join(', ')}`).toEqual([]);
  });

  it('px в манифесте равен настоящей ширине файла', () => {
    const wrong = [];
    for (const [name, e] of Object.entries(entries)) {
      if (e.vector || !guardedFiles.includes(name)) continue;
      const real = imageWidth(join(publicDir, name));
      if (real !== e.px) wrong.push(`${name}: в манифесте ${e.px}, в файле ${real}`);
    }
    expect(wrong).toEqual([]);
  });

  it('px >= max_display_px x dpr у каждого показываемого растра (кроме ждущих замены)', () => {
    const low = [];
    for (const [name, e] of Object.entries(entries)) {
      if (e.vector || e.used === false || e.pending) continue;
      if (typeof e.max_display_px !== 'number' || typeof e.dpr !== 'number') {
        low.push(`${name}: нет max_display_px или dpr`);
        continue;
      }
      const need = e.max_display_px * e.dpr;
      if (e.px < need) low.push(`${name}: ${e.px} px < ${e.max_display_px} CSS px x ${e.dpr} = ${need}`);
    }
    expect(low, low.join('\n')).toEqual([]);
  });

  it('dpr ниже 2 допустим только у мягких фонов с причиной (не ниже 0.75) и у значков ОС', () => {
    const bad = [];
    for (const [name, e] of Object.entries(entries)) {
      if (e.vector || e.used === false || typeof e.dpr !== 'number') continue;
      if (e.dpr >= 2) continue;
      if (e.external) continue;
      if (e.fallback_of && entries[e.fallback_of] && entries[e.fallback_of].dpr >= 2) continue;
      if (e.soft && String(e.soft).length >= 20 && e.dpr >= 0.75) continue;
      bad.push(`${name}: dpr ${e.dpr} без soft/external (причина не короче 20 знаков, dpr >= 0.75)`);
    }
    expect(bad).toEqual([]);
  });

  it('файлы с used=false или defect не подключены в src; ссылки из src ведут в манифест', () => {
    const dead = new Set(Object.entries(entries).filter(([, e]) => e.used === false || e.defect).map(([k]) => k));
    const wrongRefs = [];
    const unknownRefs = [];
    const re = /\/(?:brand|art|icons)\/[^\s'"`)?#]+\.(?:webp|png|jpe?g|svg|avif|gif)/g;
    for (const [file, text] of srcText) {
      for (const m of text.matchAll(re)) {
        const rel = m[0].slice(1);
        if (rel.includes('${')) continue;
        if (!(rel in entries)) unknownRefs.push(`${file}: ${rel}`);
        else if (dead.has(rel)) wrongRefs.push(`${file}: ${rel}`);
      }
    }
    expect(wrongRefs, `used=false/defect, но подключены: ${wrongRefs.join('; ')}`).toEqual([]);
    expect(unknownRefs, `ссылка на файл вне манифеста: ${unknownRefs.join('; ')}`).toEqual([]);
  });

  it('картинки категорий: у каждой показываемой есть кадр 640 px для DPR 2-3', () => {
    const missing = [];
    for (const name of Object.keys(entries)) {
      const m = /^art\/quicklinks\/(.+)-320\.webp$/.exec(name);
      if (m && entries[name].used !== false && !(`art/quicklinks/${m[1]}-640.webp` in entries)) missing.push(name);
    }
    expect(missing).toEqual([]);
  });

  it('ждущие замены записи перечислены (долг круга 6)', () => {
    const pending = Object.entries(entries).filter(([, e]) => e.pending).map(([k, e]) => `${k}: ${e.pending}`);
    if (pending.length) console.warn(`no-lowres: ${pending.length} растр(ов) ждут замены другой зоной:\n  ${pending.join('\n  ')}`);
    expect(Array.isArray(pending)).toBe(true);
  });
});
