/**
 * Regression: публичные поверхности (About/Privacy/Terms/Footer/RegisterNudge/
 * index.html/llms.txt) честно разделяют просмотр и скачивание, не тянут
 * устаревшие 80+/9/«девяти» и не обещают «весь мир».
 */
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

const ROOT = resolve(import.meta.dirname, '../../..');

const SURFACES = [
  'backend/app/services/seo_content.py',
  'backend/app/services/seo_renderer.py',
  // После i18n публичные тексты SPA живут в словарях, а не в компонентах.
  'frontend/src/i18n/messages.ru.js',
  'frontend/src/i18n/messages.en.js',
  'frontend/src/pages/Dashboard.jsx',
  'frontend/src/components/home/HomeHero.jsx',
  'frontend/src/components/home/HomeCountryList.jsx',
  'frontend/src/components/home/HomeWorkbench.jsx',
  'frontend/src/pages/About.jsx',
  'frontend/src/pages/Privacy.jsx',
  'frontend/src/pages/Terms.jsx',
  'frontend/src/components/Footer.jsx',
  'frontend/src/components/RegisterNudge.jsx',
  'frontend/index.html',
  'frontend/public/llms.txt',
];

const BANNED = [
  /\b80\s*\+/i,
  /\bв\s+9\s+категори/i,
  /\b9\s+категори/i,
  /\bдевяти\b/i,
  /стран\s+мира/i,
  /всей?\s+мир[ае]?\b/i,
  /по\s+всем\s+странам/i,
  /снимает\s+лимит/i,
  /лимит\s+на\s+выгруз/i,
  /лимит\s+бесплатных\s+выгрузок/i,
  /выгрузк\w*\s+без\s+регистрац/i,
  /скачиван\w*\s+без\s+регистрац/i,
];

/**
 * Квантифицированное покрытие витрины главной: «48» + «стран мира» в
 * home.scope.stat.* — официальный факт (48 в публичном каталоге), а не
 * устаревшее обещание «весь мир». Число и подпись — соседние ключи i18n,
 * поэтому строка подписи исключена из скана явно, а не правкой формулировки.
 */
const QUANTIFIED_LINE = /'home\.scope\.stat\./;

function stripQuantifiedLines(text) {
  return text
    .split('\n')
    .filter((line) => !QUANTIFIED_LINE.test(line))
    .join('\n');
}

function read(rel) {
  return readFileSync(resolve(ROOT, rel), 'utf8');
}

describe('public product claims', () => {
  it.each(SURFACES)('%s без устаревших product-claims', (rel) => {
    const text = stripQuantifiedLines(read(rel));
    for (const re of BANNED) {
      expect(text, `${rel} matches ${re}`).not.toMatch(re);
    }
  });

  it('About честно разделяет просмотр и скачивание', () => {
    const text = read('frontend/src/i18n/messages.ru.js');
    expect(text).toMatch(/без регистрации/i);
    expect(text).toMatch(/после бесплатной регистрации/i);
    expect(text).toMatch(/доступная статистика/i);
    expect(text).toMatch(/России/);
  });

  it('Privacy и Terms требуют регистрацию для скачивания, не для просмотра', () => {
    for (const rel of ['frontend/src/pages/Privacy.jsx', 'frontend/src/pages/Terms.jsx']) {
      const text = read(rel);
      expect(text).toMatch(/Просмотр аналитического\s+контента/i);
      expect(text).toMatch(/после бесплатной\s+регистрации/i);
      expect(text).not.toMatch(/весь аналитический контент Сайта доступен без регистрации/i);
    }
  });

  it('RegisterNudge не обещает «снять лимит» гостю', () => {
    const text = read('frontend/src/i18n/messages.ru.js');
    expect(text).toMatch(/Просмотр графиков и таблиц бесплатен без аккаунта/);
    expect(text).toMatch(/открывает скачивание/);
    expect(text).not.toMatch(/снимает лимит/);
  });

  it('Footer и llms позиционируют РФ + регионы + доступную статистику стран', () => {
    const footerCopy = read('frontend/src/i18n/messages.ru.js');
    expect(footerCopy).toMatch(/доступная статистика\s+стран/);
    expect(footerCopy).toMatch(/России/);

    const llms = read('frontend/public/llms.txt');
    expect(llms).toMatch(/доступная статистика (отдельных )?стран/i);
    expect(llms).toMatch(/скачивание.*после бесплатной регистрации/i);
    expect(llms).toMatch(/Просмотр аналитики бесплатный/i);
    expect(llms).not.toMatch(/регистрация для просмотра не требуется$/m);
  });

  it('index.html сохраняет РФ SEO в title и без 80+/9', () => {
    const html = read('frontend/index.html');
    expect(html).toMatch(/Бесплатная аналитика экономики России/);
    expect(html).toMatch(/более 100/);
    expect(html).toMatch(/доступн\S* (статистика|данные).{0,40}стран/i);
    expect(html).not.toMatch(/\b80\s*\+/);
    expect(html).not.toMatch(/9\s+категори/);
  });
});
