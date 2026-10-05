// Страж «хрусталь без границ» (R3): на карточках, панелях, чипах, кнопках, полях, вкладках и плашках нет рамок.
// Границу заменяет разница светлоты слоёв, блик сверху и тень снизу (см. шапку z1-tokens.css).
// Тест читает index.css, styles/*.css и все .jsx вне embed/ и падает при любой рамке вне явного списка исключений.
import { readdirSync, readFileSync, statSync } from 'node:fs';
import { dirname, join, relative } from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';

const here = dirname(fileURLToPath(import.meta.url));
const src = join(here, '..');

function walk(dir, out = []) {
  for (const name of readdirSync(dir)) {
    const full = join(dir, name);
    if (statSync(full).isDirectory()) {
      if (name === 'embed' || name === 'node_modules') continue;
      walk(full, out);
    } else out.push(full);
  }
  return out;
}
const allFiles = walk(src);
const cssFiles = [join(src, 'index.css'), ...allFiles.filter((f) => f.includes(`${join(src, 'styles')}/`) && f.endsWith('.css'))];
const jsxFiles = allFiles.filter((f) => f.endsWith('.jsx') && !f.endsWith('.test.jsx'));
const rel = (f) => relative(src, f);

/* ───────────────────────────── CSS ───────────────────────────── */

// Исключения для CSS: селектор правила → пункт раздела 5 эталона (или пояснение).
// Правило попадает в исключение, если его селектор подходит под pattern.
export const CSS_BORDER_ALLOW = [
  { pattern: /(?<![\w-])(tr|td|th|li|table|thead|tbody|tfoot|hr)(?![\w-])/, why: 'п.2: разделители строк таблиц и списков, hr' },
  { pattern: /fe-divider|fe-divide-y/, why: 'п.2: единственный класс-разделитель .fe-divider (и его варианты)' },
  { pattern: /:focus|focus-visible|focus-within/, why: 'п.1: фокус с клавиатуры' },
  { pattern: /aria-invalid|is-invalid/, why: 'п.5: поле в состоянии ошибки: нижняя линия 2 px, без полной рамки' },
  { pattern: /swatch|__key\b|__key-/, why: 'п.3: образец линии в легенде графика (штриховая линия прогноза)' },
  { pattern: /::?(before|after)/, why: 'п.3: глифы-псевдоэлементы (галочка чекбокса, шеврон), не рамки панелей' },
  { pattern: /slider-thumb|range-thumb/, why: 'п.3: ползунки (если остались)' },
  { pattern: /fe-gold-rule|leader/, why: 'п.4: золотая линия-украшение и акцент лидера' },
];
// Акцент слева (п.4): до 3 px, цветом. Не более одного на карточку: проверяется глазами.
const ACCENT_LEFT = /^border-left\s*:\s*[123](\.\d+)?px\s+solid\b/;

function cssBlocks(text) {
  const out = [];
  const re = /([^{}]*)\{([^{}]*)\}/g;
  let m;
  while ((m = re.exec(text))) {
    const selector = m[1].replace(/\/\*[\s\S]*?\*\//g, '').trim();
    out.push({ selector, body: m[2] });
  }
  return out;
}

const BORDER_DECL = /(?:^|[;\s])(border(?:-(?:top|bottom|left|right))?\s*:\s*[0-9.]+(?:px|rem)?\s*(?:solid|dashed|dotted)[^;}]*)/g;
const BORDER_STYLE = /(?:^|[;\s])(border(?:-(?:top|bottom|left|right))?-style\s*:\s*(?:solid|dashed|dotted))/g;
const RING_SHADOW = /box-shadow\s*:[^;}]*?(?:^|[,\s])(?:inset\s+)?0\s+0\s+0\s+[12](?:\.\d+)?px\s/;

function cssViolations() {
  const bad = [];
  for (const file of cssFiles) {
    const text = readFileSync(file, 'utf8');
    for (const { selector, body } of cssBlocks(text)) {
      const allowed = CSS_BORDER_ALLOW.some((a) => a.pattern.test(selector));
      if (allowed) continue;
      for (const re of [BORDER_DECL, BORDER_STYLE]) {
        re.lastIndex = 0;
        let m;
        while ((m = re.exec(body))) {
          const decl = m[1].trim();
          if (ACCENT_LEFT.test(decl)) continue;
          bad.push(`${rel(file)}: ${selector.slice(-70)} { ${decl} }`);
        }
      }
      if (RING_SHADOW.test(body)) bad.push(`${rel(file)}: ${selector.slice(-70)} { box-shadow-ring }`);
    }
  }
  return bad;
}

/* ───────────────────────────── JSX / Tailwind ───────────────────────────── */

// Исключения для Tailwind-утилит в JSX: файл → какие токены допустимы и почему.
export const JSX_BORDER_ALLOW = [
  { file: 'components/DataTable.jsx', token: /^border-t$|^border-border-subtle$/, why: 'п.2: строки таблицы данных (<tr>)' },
  { file: 'components/ForecastTable.jsx', token: /^border-t$|^border-border-subtle$/, why: 'п.2: строки таблицы прогноза (<tr>)' },
  { file: 'components/SessionAnalysisTab.jsx', token: /^border-b$|^border-border-subtle$/, why: 'п.2: элементы списка (<li>) служебной вкладки' },
  { file: 'pages/CalculatorPage.jsx', token: /^border-b$|^border-border-subtle(\/\d+)?$/, why: 'п.2: строки таблицы калькулятора (<tr>)' },
  { file: 'pages/AdminBI.jsx', token: /^border-[bt]$|^border-border-subtle(\/\d+)?$|^border-separate$/, why: 'п.2: строки и шапки таблиц служебной аналитики (<tr>)' },
  { file: 'pages/RegionRatingPage.jsx', token: /^border-t$|^border-border-subtle$/, why: 'п.2: строки таблицы рейтинга (<tr>)' },
  { file: 'pages/WorldRatingPage.jsx', token: /^border-t$|^border-border-subtle$/, why: 'п.2: строки таблицы рейтинга (<tr>)' },
  { file: 'pages/RegionIndicatorPage.jsx', token: /^border-t$|^border-border-subtle$/, why: 'п.2: строки таблицы значений (<tr>)' },
  { file: 'pages/WorldRegionIndicatorPage.jsx', token: /^border-t$|^border-border-subtle$/, why: 'п.2: строки таблицы значений (<tr>)' },
  { file: 'pages/TodayIndicatorPage.jsx', token: /^border-t$|^border-border-subtle$/, why: 'п.2: строки таблицы значений (<tr>)' },
  { file: 'components/PlanetLabels.jsx', token: /^border$/, why: 'не CSS: слово «border» в тексте GLSL-шейдера планеты (рамка панели на текстуре подписей)' },
  { file: 'components/RegionAnnualChart.jsx', token: /^border-t-2$|^border-dashed$/, why: 'п.3: образец штриховой линии в легенде графика' },
  { file: 'components/calendar/CalendarEventCard.jsx', token: /^border-l-(blue|emerald|amber)-500$|^border-l-\[3px\]$|^border$/, why: 'п.4: цвет акцента слева у события (3 px, рисуется ::before)' },
];

// Токен рамки Tailwind с любым вариантом (sm:, hover:, group-hover: ...). Фокусные варианты допустимы (п.1).
const TW_BORDER = /^(?:(?:[a-z0-9-]+|\[[^\]]+\]|aria-[^:]+|data-[^:]+):)*(border(?:-[trblxy])?(?:-[0-9]+|-\[[^\]\s]+\])?|border-(?:border-subtle|border-champagne|champagne|champagne-ink|subtle|white|black|negative|positive|dashed|dotted|solid|blue-\d+|emerald-\d+|amber-\d+|\[[^\]\s]+\])(?:\/[0-9]+|\/\[[^\]\s]+\])?|border-[trblxy]-(?:[a-z-]+\d*)(?:\/[0-9]+)?|ring(?:-[0-9]+)?|ring-(?:black|champagne|champagne-ink|white|negative|positive|offset-[\w-]+|\[[^\]\s]+\])(?:\/[0-9]+|\/\[[^\]\s]+\])?)!?$/;
const NEUTRAL = /^(?:[a-z0-9-]+:)*border-(?:0|none|box|collapse|separate|spacing)$|^(?:[a-z0-9-]+:)*border-[trblxy]-0$/;

// Строки в кавычках (одна строка) и шаблонные литералы (в том числе многострочные, с вставками ${...}).
const STR = /(["'])((?:\\.|(?!\1)[^\\\n])*?)\1|(`)((?:\\.|[^`\\])*)\3/g;

function jsxViolations() {
  const bad = [];
  for (const file of jsxFiles) {
    const text = readFileSync(file, 'utf8');
    const allows = JSX_BORDER_ALLOW.filter((a) => a.file === rel(file));
    STR.lastIndex = 0;
    let m;
    while ((m = STR.exec(text))) {
      const body = m[2] ?? m[4] ?? '';
      if (!/(?:^|[\s:])(?:border|ring)/.test(body)) continue;
      for (const tok of body.split(/\s+/)) {
        if (!tok || NEUTRAL.test(tok)) continue;
        const match = TW_BORDER.exec(tok);
        if (!match) continue;
        // фокусные кольца и рамки допустимы: клавиатурный фокус (п.1)
        if (/(?:^|:)(?:focus|focus-visible|focus-within):/.test(tok) || /^(?:[a-z0-9-]+:)*(?:focus|focus-visible|focus-within):/.test(tok)) continue;
        if (allows.some((a) => a.token.test(tok.replace(/^(?:[a-z0-9-]+:)+/, '')))) continue;
        const line = text.slice(0, m.index).split('\n').length;
        bad.push(`${rel(file)}:${line}: ${tok}`);
      }
    }
  }
  return bad;
}

// Инлайн-стили с рамкой в JSX (вне embed): только спиннер маршрута встраивания в App.jsx.
const INLINE_BORDER = /border(?:Top|Bottom|Left|Right)?\s*:\s*['"`]?[0-9.]+px\s+(?:solid|dashed)/g;
const INLINE_ALLOW = [{ file: 'App.jsx', why: 'п.6: запасной спиннер маршрута встраивания (embed) живёт своей палитрой' }];

function inlineViolations() {
  const bad = [];
  for (const file of jsxFiles) {
    if (INLINE_ALLOW.some((a) => a.file === rel(file))) continue;
    const text = readFileSync(file, 'utf8');
    INLINE_BORDER.lastIndex = 0;
    let m;
    while ((m = INLINE_BORDER.exec(text))) bad.push(`${rel(file)}:${text.slice(0, m.index).split('\n').length}: ${m[0]}`);
  }
  return bad;
}

describe('no-borders: хрусталь без границ', () => {
  it('в CSS нет рамок и «колец» 0 0 0 1px вне исключений эталона', () => {
    expect(cssViolations()).toEqual([]);
  });

  it('в JSX нет Tailwind-утилит рамки (border, border-*, ring-*) вне исключений', () => {
    expect(jsxViolations()).toEqual([]);
  });

  it('в JSX нет инлайн-рамок вне запасного спиннера embed', () => {
    expect(inlineViolations()).toEqual([]);
  });

  it('золотая кромка --fe-panel-edge удалена, --fe-glow-gold не рисует кольцо', () => {
    const tokens = readFileSync(join(here, 'z1-tokens.css'), 'utf8');
    const index = readFileSync(join(src, 'index.css'), 'utf8');
    expect(tokens + index).not.toMatch(/--fe-panel-edge/);
    const glow = /--fe-glow-gold\s*:([^;]*);/.exec(tokens);
    expect(glow).not.toBeNull();
    expect(glow[1]).not.toMatch(/0\s+0\s+0\s+\d+(\.\d+)?px/);
  });

  it('каждое исключение в списках объяснено', () => {
    for (const a of [...CSS_BORDER_ALLOW, ...JSX_BORDER_ALLOW]) expect(a.why.length).toBeGreaterThan(10);
  });
});
