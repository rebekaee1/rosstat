/**
 * Одноразовый дамп текстов секции «Методология» (24 комбинации состав × режим).
 * Запуск: cd frontend && npx vitest run src/lib/dump-cpi-methodology-temp.test.js
 */
import { describe, it, expect } from 'vitest';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { renderToStaticMarkup } from 'react-dom/server';
import { getViewModeContent } from './cpiViewModeContent.jsx';
import { CPI_VIEW_MODES_FLAT } from './cpiViewModeGroups.js';
import { dataModeForUrlMode } from './cpiViewModeResolve.js';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = path.resolve(__dirname, '../../..');
const OUT_FILE = path.join(REPO_ROOT, 'cpi-methodology-combinations.temp.txt');

const COMPOSITION_GROUP = 'Состав индекса потребительских цен';
const MODE_GROUP = 'Режим инфляции';

const COMPOSITIONS = [
  { code: 'cpi', label: 'Все товары и услуги' },
  { code: 'cpi-food', label: 'Продовольствие' },
  { code: 'cpi-nonfood', label: 'Непродовольственные' },
  { code: 'cpi-services', label: 'Услуги' },
];

const INDICATORS_BY_CODE = {
  cpi: {
    code: 'cpi',
    name: 'Индекс потребительских цен на товары и услуги',
    source: 'Росстат',
    source_url: 'https://rosstat.gov.ru/statistics/price',
    description:
      'Индекс потребительских цен (ИПЦ) измеряет изменение цен на товары и услуги, '
      + 'приобретаемые населением для непроизводственного потребления. ИПЦ является ключевым '
      + 'показателем инфляции и используется для индексации заработной платы, пенсий и '
      + 'социальных выплат.',
    methodology:
      'ИПЦ рассчитывается как отношение стоимости фиксированного набора товаров и услуг '
      + 'в текущем периоде к его стоимости в базисном периоде. Наблюдение осуществляется '
      + 'в 283 населённых пунктах по 510 наименованиям товаров и услуг. '
      + 'База сравнения — предыдущий месяц (100%).',
  },
  'cpi-food': {
    code: 'cpi-food',
    name: 'Индекс потребительских цен на продовольственные товары',
    source: 'Росстат',
    source_url: 'https://rosstat.gov.ru/statistics/price',
    description: 'Индекс потребительских цен на продовольственные товары.',
    methodology: '',
  },
  'cpi-nonfood': {
    code: 'cpi-nonfood',
    name: 'Индекс потребительских цен на непродовольственные товары',
    source: 'Росстат',
    source_url: 'https://rosstat.gov.ru/statistics/price',
    description: 'Индекс потребительских цен на непродовольственные товары.',
    methodology: '',
  },
  'cpi-services': {
    code: 'cpi-services',
    name: 'Индекс потребительских цен на услуги',
    source: 'Росстат',
    source_url: 'https://rosstat.gov.ru/statistics/price',
    description: 'Индекс потребительских цен на услуги.',
    methodology: '',
  },
};

function jsxToPlain(node) {
  if (node == null || node === false) return '';
  if (typeof node === 'string') return node;
  if (typeof node === 'number') return String(node);
  if (Array.isArray(node)) return node.map(jsxToPlain).join(' ');
  if (typeof node === 'object' && node.$$typeof != null) {
    const html = renderToStaticMarkup(node);
    return html
      .replace(/<sub>/gi, '')
      .replace(/<\/sub>/gi, '')
      .replace(/<[^>]+>/g, ' ')
      .replace(/&minus;/g, '−')
      .replace(/&nbsp;/g, ' ')
      .replace(/\s+/g, ' ')
      .trim();
  }
  if (typeof node === 'object' && node.props != null) {
    return jsxToPlain(node.props.children);
  }
  return '';
}

function normalizePlain(text) {
  return String(text)
    .replace(/\u00a0/g, ' ')
    .replace(/[ \t]+\n/g, '\n')
    .replace(/\n{3,}/g, '\n\n')
    .trim();
}

function loadCpiSeoBlocks() {
  const pyPath = path.join(REPO_ROOT, 'backend/app/data/indicator_seo.py');
  const src = fs.readFileSync(pyPath, 'utf8');
  const marker = 'INDICATOR_SEO_BLOCKS: dict[str, list[dict[str, str]]] = {';
  const start = src.indexOf(marker);
  if (start < 0) return [];

  const cpiStart = src.indexOf('"cpi": [', start);
  if (cpiStart < 0) return [];

  let depth = 0;
  let i = cpiStart + '"cpi": ['.length;
  let chunk = '';
  for (; i < src.length; i += 1) {
    const ch = src[i];
    if (ch === '[') depth += 1;
    if (ch === ']') {
      if (depth === 0) break;
      depth -= 1;
    }
    chunk += ch;
  }

  const blocks = [];
  const blockRe = /\{\s*"title":\s*"([^"]+)",\s*"body":\s*\(\s*((?:"[^"]*"\s*)+)\),?\s*\}/gs;
  let m;
  while ((m = blockRe.exec(chunk)) !== null) {
    const title = m[1];
    const bodyParts = m[2].match(/"([^"]*)"/g) || [];
    const body = bodyParts.map((p) => p.slice(1, -1)).join('');
    blocks.push({ title, body });
  }
  return blocks;
}

function panelContent(compositionCode, mode) {
  const indicator = INDICATORS_BY_CODE[compositionCode];
  return getViewModeContent({
    chartMode: dataModeForUrlMode(mode),
    safeViewMode: mode,
    isPriceCategory: true,
    indicator,
  });
}

function formatCombination(composition, modeItem, index) {
  const { code: compositionCode, label: compositionLabel } = composition;
  const { mode, label: modeLabel } = modeItem;
  const indicator = INDICATORS_BY_CODE[compositionCode];
  const content = panelContent(compositionCode, mode);

  const lines = [];
  lines.push('='.repeat(80));
  lines.push(`[${index}/${COMPOSITIONS.length * CPI_VIEW_MODES_FLAT.length}] ${COMPOSITION_GROUP} × ${MODE_GROUP}`);
  lines.push('='.repeat(80));
  lines.push(`Состав: ${compositionLabel} (код: ${compositionCode})`);
  lines.push(`Режим: ${modeLabel} (код режима: ${mode})`);
  lines.push(`Индикатор (API): ${indicator.name}`);
  lines.push('');
  lines.push('--- Секция «Методология» на карточке (IndicatorMethodologyPanel) ---');
  lines.push('');
  lines.push('[1] Описание (content.description):');
  lines.push(normalizePlain(content.description || '(пусто)'));
  lines.push('');
  lines.push('[2] Методология (content.methodology):');
  lines.push(normalizePlain(jsxToPlain(content.methodology) || '(пусто)'));
  lines.push('');
  lines.push('[3] Источник (блок под текстом, не меняется от режима):');
  lines.push(`Источник: ${indicator.source}`);
  lines.push(`URL: ${indicator.source_url}`);
  lines.push('');
  lines.push('--- Справка: поля индикатора в БД (НЕ подменяют режимный UI) ---');
  lines.push('');
  lines.push('[DB] description:');
  lines.push(normalizePlain(indicator.description || '(пусто)'));
  lines.push('');
  lines.push('[DB] methodology:');
  lines.push(normalizePlain(indicator.methodology || '(пусто)'));
  lines.push('');
  return lines.join('\n');
}

describe('dump CPI methodology combinations', () => {
  it('writes cpi-methodology-combinations.temp.txt', () => {
    const modes = CPI_VIEW_MODES_FLAT;
    expect(modes.length).toBe(10);
    expect(COMPOSITIONS.length).toBe(4);

    const seoBlocks = loadCpiSeoBlocks();
    expect(seoBlocks.length).toBeGreaterThanOrEqual(4);

    const header = [
      'ДАМП: тексты методологии ИПЦ — все комбинации «Состав» × «Режим инфляции»',
      `Сгенерировано: ${new Date().toISOString()}`,
      'Пересобрать: cd frontend && npx vitest run --config vitest.dump.config.js',
      'Источник UI: frontend/src/lib/cpiViewModeContent.jsx → getViewModeContent()',
      'Источник переключателей: indicatorVariants.js (состав), cpiViewModes.js (режим)',
      'Панель: frontend/src/components/IndicatorMethodologyPanel.jsx',
      '',
      `Всего комбинаций: ${COMPOSITIONS.length} × ${modes.length} = ${COMPOSITIONS.length * modes.length} (6 активных режимов)`,
      '',
    ].join('\n');

    const parts = [header];
    let n = 0;
    for (const composition of COMPOSITIONS) {
      for (const modeItem of modes) {
        n += 1;
        parts.push(formatCombination(composition, modeItem, n));
      }
    }

    parts.push('='.repeat(80));
    parts.push('ПРИЛОЖЕНИЕ: блок «О показателе» (IndicatorSeoBlocks)');
    parts.push('Только для состава «Все товары и услуги» (cpi). Не зависит от режима инфляции.');
    parts.push('='.repeat(80));
    for (const [i, block] of seoBlocks.entries()) {
      parts.push('');
      parts.push(`[SEO ${i + 1}/${seoBlocks.length}] ${block.title}`);
      parts.push(normalizePlain(block.body));
    }
    parts.push('');
    parts.push('--- конец файла ---');

    fs.writeFileSync(OUT_FILE, `${parts.join('\n')}\n`, 'utf8');
    expect(fs.existsSync(OUT_FILE)).toBe(true);
  });
});
