import { useState, useMemo, useCallback, useEffect, useRef } from 'react';
import { createPortal } from 'react-dom';
import { useSearchParams, Link } from 'react-router-dom';
import { useQueries } from '@tanstack/react-query';
import {
  ResponsiveContainer, ComposedChart, Line, Area, ReferenceDot, XAxis, YAxis,
  Tooltip, CartesianGrid,
} from 'recharts';
import {
  ArrowLeft, Activity, Search, X, Plus, ImageDown, Sparkles,
  Landmark, MapPin, Check, ChevronDown, Globe2,
} from 'lucide-react';
import { useIndicators } from '../lib/hooks';
import { fetchIndicatorData } from '../lib/api';
import api from '../lib/api';
import { useRegionsLanding, useRegionsCatalog } from '../lib/regionsApi';
import { fetchWorldCompareOrCard, useWorldCompareCatalog } from '../lib/worldApi';
import { useWorldRegionsHub } from '../lib/worldSubnationalApi';
import { useAuth } from '../context/authContext';
import { useT, useLocale } from '../i18n';
import { currentUiLocale } from '../i18n/locale';
import {
  formatDate, formatChartAxisDate, formatAxisTick, formatValueWithUnit,
  unitSuffix, unitDigits, cn, pickChartAxisTicks, chartAxisTickBudget,
} from '../lib/format';
import useDocumentMeta from '../lib/useMeta';
import { getPageSeo } from '../lib/pageMeta';
import CompareChartState from '../components/CompareChartState';
import Chip from '../components/Chip';
import Button from '../components/Button';
import { formatValueSplit, splitUnit } from '../lib/compareUnitSplit';
import {
  formatEndValue, gapInsight, isAbsoluteUnit, spreadLabels, yForValue,
} from '../lib/compareInsight';
import { scalesDiffer } from '../lib/useCountryComparison';
import ChartBrush from '../components/ChartBrush';
import CompareCountryStep from '../components/compare/CompareCountryStep';
import {
  COMPARE_PRESETS, DEFAULT_COMPARE_PRESET, comparePresetsFor, presetIsActive, presetParams,
} from '../lib/comparePresets';
import { compareEndName, compareLabels, conceptShortLabel, unitHint } from '../lib/compareTitle';
import useMediaQuery from '../lib/useMediaQuery';
import { deltaTone, indicatorPolarity } from '../lib/deltaTone';
import {
  CHART_THEME, GRID_PROPS, NARROW_CHART_WIDTH, CHART_AREA, axisTick, axisSampleValues,
  axisWidthForLabels, chartHeightForWidth, niceAxis, COMPARE_COLORS, ribbonStopsFor,
} from '../lib/chartTheme';
import { compareTooltipRows } from '../lib/compareTooltip';
import { useElementWidth, useTouchTooltip, useChartGlassIds } from '../lib/chartHooks';
import { track, events } from '../lib/track';
import useSearchTracking from '../lib/useSearchTracking';
import useGlobalSearch from '../lib/useGlobalSearch';
import { filterSearchOptions } from '../lib/searchSynonyms';
import { filterSearchCountries } from '../lib/worldCompareSearch';
import { exportNodeToPng } from '../lib/chartImage';
import useScrollDepth from '../lib/useScrollDepth';
import {
  compareDifferenceUnit, compareLegendParts, REP_LEVEL, REP_ORDER, REP_HINT, compareRepresentationsFor, resolveCompareSeries,
  applyCompareTransform, commonIndexBase, rebaseToHundred, requiresRebasedPriceIndex, resolveStepOverride,
  worldCompareRepresentationsFor, worldCompareTransformFor, defaultWorldRepresentation,
} from '../lib/compareRepresentation';
import {
  activeCompatibilityNote,
  compareCompatibilityWithTwins,
  normalizeCompareCodes,
  parseSubnationalCompareCode,
  parseWorldCompareCode,
} from '../lib/compareCompatibility';
import { orderCountriesByGdp } from '../lib/countryOrder';
import {
  comparePath,
  countryRegionsPath,
  regionHubPath,
} from '../lib/sitePaths';
import Breadcrumbs from '../components/Breadcrumbs';
import { flagForSlug } from '../lib/slugFlags';
import { toolTrail } from '../lib/breadcrumbs';
import '../styles/regions-w4.css';
import '../styles/w6-g.css';
import '../styles/z7-compare.css';
import '../styles/k5-pages.css';
import '../styles/k4-charts.css';

/** Высота окна браузера (px); 0 до первого измерения и без window. */
function useViewportHeight() {
  const [height, setHeight] = useState(0);
  useEffect(() => {
    const read = () => setHeight(window.innerHeight || 0);
    read();
    window.addEventListener('resize', read, { passive: true });
    return () => window.removeEventListener('resize', read);
  }, []);
  return height;
}

/** После добавления ряда на телефоне плавно ведём к графику, если он ниже середины экрана или выше края. */
function scrollToCompareChart() {
  const chart = document.querySelector('[data-block="compare-chart"]');
  if (!chart) return;
  const top = chart.getBoundingClientRect().top;
  if (top >= 72 && top < window.innerHeight * 0.55) return;
  const reduce = typeof window.matchMedia === 'function'
    && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  if (typeof window.scrollTo === 'function') {
    // 88 px: шапка и лента курсов не закрывают заголовок графика.
    window.scrollTo({ top: Math.max(0, window.scrollY + top - 88), behavior: reduce ? 'auto' : 'smooth' });
  }
}

/** Подпись единицы: у «индекса» её суффикс пуст, и подпись превращалась в «Значения, .» — тогда пишем само слово. */
function unitLabel(unit) {
  return unitSuffix(unit) || String(unit ?? '').trim();
}

/** Сила связи двух рядов словами (число — только в «Как посчитано»). */
function correlationKey(r) {
  const abs = Math.abs(r);
  if (abs >= 0.7) return r > 0 ? 'w4.compare.corr.strongUp' : 'w4.compare.corr.strongDown';
  if (abs >= 0.4) return r > 0 ? 'w4.compare.corr.mediumUp' : 'w4.compare.corr.mediumDown';
  return 'w4.compare.corr.weak';
}

function compatText(t, compatibility) {
  const key = compatibility?.reasonKey || compatibility?.reason;
  return key ? t(key) : undefined;
}

// Круг 10 (Ср2): по умолчанию 25 лет. Короткий период обрезал историю («с 2016») там, где ряды сравнивают от общего старта.
const RANGE_OPTIONS = [
  { key: '3y', labelKey: 'compare.range.3y', months: 36 },
  { key: '5y', labelKey: 'compare.range.5y', months: 60 },
  { key: '10y', labelKey: 'compare.range.10y', months: 120 },
  { key: '25y', labelKey: 'c10k.compare.range.25y', months: 300 },
  { key: 'all', labelKey: 'compare.range.all', months: null },
];
const DEFAULT_RANGE = '25y';

// До 10 рядов — палитра различимых цветов из общей темы графиков (lib/chartTheme.js::COMPARE_COLORS).
// Круг 8 (C1): цвет ряда один на линию, легенду, точку на конце, заливку, подсказку и карточки итогов.
// Первые два ряда рисуются лентой-градиентом, построенным из того же цвета (светлее слева, цвет ряда у правого конца).
const PALETTE = COMPARE_COLORS;
const RIBBON_COUNT = 2;
const RIBBON_GRADIENTS = Object.freeze(
  PALETTE.slice(0, RIBBON_COUNT).map((color) => Object.freeze(ribbonStopsFor(color))),
);
const AREA_OPACITY = Object.freeze([CHART_AREA.top, 0.14]);

/** Точка на конце линии: плоский круг 6 px цвета ряда и тихое гало (как .k4-lastpoint). Рисуется поверх линии, мыши не мешает. */
function EndPoint({ cx, cy, color }) {
  if (!Number.isFinite(cx) || !Number.isFinite(cy)) return null;
  return (
    <g pointerEvents="none" className="fe-compare-bead">
      <circle cx={cx} cy={cy} r={8} fill={color} fillOpacity={0.2} />
      <circle cx={cx} cy={cy} r={3.5} fill={color} />
    </g>
  );
}

/** Флаг страны ряда для линзы на конце линии: мировой ряд по slug страны, российский показатель — Россия, регионы — без флага. */
function seriesFlag(s) {
  if (s.isWorld) return flagForSlug(parseWorldCompareCode(s.code)?.countrySlug);
  if (s.isRegion || s.isSubnational) return '';
  return flagForSlug('russia');
}

// «Общая база» вместо «Индекс», чтобы не путать со ЗНАЧЕНИЕМ представления
// «Индекс» (уровень индекса цен ИПЦ/ИЦП) у отдельного ряда — это разные вещи.
const SCALE_OPTIONS = [
  { key: 'values', labelKey: 'compare.scale.values' },
  { key: 'index', labelKey: 'compare.scale.index' },
];

const GUEST_MAX = 2;
const USER_MAX = 10;

// Шаг временной сетки: месячный ряд рядом с годовым выглядит «лесенкой» —
// приведение к общему шагу усредняет значения за период (созвон «На правки 13»).
const STEP_OPTIONS = [
  { key: 'auto', labelKey: 'compare.step.auto' },
  { key: 'month', labelKey: 'compare.step.month' },
  { key: 'quarter', labelKey: 'compare.step.quarter' },
  { key: 'year', labelKey: 'compare.step.year' },
];

function pearsonCorrelation(pairs) {
  if (pairs.length < 6) return null;
  const meanX = pairs.reduce((sum, pair) => sum + pair[0], 0) / pairs.length;
  const meanY = pairs.reduce((sum, pair) => sum + pair[1], 0) / pairs.length;
  let covariance = 0;
  let varianceX = 0;
  let varianceY = 0;
  for (const [x, y] of pairs) {
    const dx = x - meanX;
    const dy = y - meanY;
    covariance += dx * dy;
    varianceX += dx * dx;
    varianceY += dy * dy;
  }
  const denominator = Math.sqrt(varianceX * varianceY);
  return denominator > 0 ? covariance / denominator : null;
}

/** Усреднение ряда по календарному шагу (месяц/квартал/год); 'auto' — как есть. */
function aggregateToStep(points, step) {
  if (!step || step === 'auto' || !points?.length) return points || [];
  const keyFor = (dateStr) => {
    const d = new Date(dateStr);
    const y = d.getUTCFullYear();
    if (step === 'year') return `${y}-01-01`;
    const m = d.getUTCMonth();
    const first = step === 'quarter' ? Math.floor(m / 3) * 3 : m;
    return `${y}-${String(first + 1).padStart(2, '0')}-01`;
  };
  const buckets = new Map();
  for (const p of points) {
    const v = Number(p.value);
    if (p.value == null || !Number.isFinite(v)) continue;
    const k = keyFor(p.date);
    const b = buckets.get(k) || { sum: 0, n: 0 };
    b.sum += v;
    b.n += 1;
    buckets.set(k, b);
  }
  return [...buckets.entries()]
    .sort(([a], [b]) => (a < b ? -1 : 1))
    .map(([date, { sum, n }]) => ({ date, value: sum / n }));
}

const FREQ_LABEL = {
  daily: 'compare.freq.daily',
  weekly: 'compare.freq.weekly',
  monthly: 'compare.freq.monthly',
  quarterly: 'compare.freq.quarterly',
  annual: 'compare.freq.annual',
  yearly: 'compare.freq.annual',
};

function freqLabel(freq, t) {
  const key = FREQ_LABEL[freq];
  if (!key) return freq || '';
  return t ? t(key) : key;
}

/** Формат подписи даты на оси/в тултипе — по более «мелкой» частоте набора. */
function compareDateFormat(inds) {
  const freqs = inds.map((i) => i?.frequency).filter(Boolean);
  if (freqs.includes('weekly') || freqs.includes('daily')) return 'weekly';
  if (freqs.includes('monthly')) return 'short';
  if (freqs.includes('quarterly')) return 'quarterly';
  if (freqs.includes('annual') || freqs.includes('yearly')) return 'annual';
  return 'short';
}

/** Парсит коды из URL: новый `codes=a,b,c` + легаси `a`/`b`. */
function parseCodes(searchParams) {
  const raw = searchParams.get('codes');
  if (raw) {
    return raw.split(',').map((c) => c.trim()).filter(Boolean).slice(0, USER_MAX);
  }
  const legacy = [searchParams.get('a'), searchParams.get('b')].filter(Boolean);
  return legacy.slice(0, USER_MAX);
}

/**
 * Представления рядов из URL: `rep=code:pop,code2:yoy`. Ключ — код индикатора,
 * значение — id представления (level|pop|yoy). Уровень (default) в URL не пишем.
 */
function parseReps(searchParams) {
  const raw = searchParams.get('rep');
  const out = {};
  if (!raw) return out;
  raw.split(',').forEach((pair) => {
    const separator = pair.lastIndexOf(':');
    const code = separator > 0 ? pair.slice(0, separator) : '';
    const rep = separator > 0 ? pair.slice(separator + 1) : '';
    if (code && rep && REP_ORDER.includes(rep.trim())) out[code.trim()] = rep.trim();
  });
  return out;
}

// --- Региональные ряды в сравнении --------------------------------------
// Код регионального ряда в URL: `r:{регион}:{показатель}`. Данные приходят
// из регионального API и нормализуются в макро-форму (год → 1 января),
// поэтому вся остальная механика графика (индекс, оси, экспорт) общая.

function isRegionCode(code) {
  return code.startsWith('r:');
}

function isWorldCode(code) {
  return !!parseWorldCompareCode(code);
}

function isSubnationalCode(code) {
  return !!parseSubnationalCompareCode(code);
}

async function fetchRegionSeries(code, { signal }) {
  const [, slug, indCode] = code.split(':');
  const resp = await api.get(`/regions/${slug}/i/${indCode}`, { signal });
  const d = resp.data;
  return {
    data: d.series.map((p) => ({ date: `${p.year}-01-01`, value: p.value })),
    __regionMeta: {
      code,
      name: `${d.indicator.name} — ${d.region.name}`,
      unit: d.indicator.unit,
      frequency: 'annual',
      category: 'compare.category.regions',
    },
  };
}

async function fetchSubnationalSeries(code, { signal }) {
  const parsed = parseSubnationalCompareCode(code);
  if (!parsed) throw new Error('compare.error.worldCode');
  const resp = await api.get(
    `/world/${parsed.countrySlug}/regions/region/${parsed.regionSlug}/${parsed.indicatorCode}`,
    { signal },
  );
  const d = resp.data;
  const loc = currentUiLocale();
  const regionName = loc === 'en'
    ? (d.region?.name_en || d.region?.name)
    : d.region?.name;
  return {
    data: (d.series || []).map((p) => ({
      date: p.date || (p.month
        ? `${p.year}-${String(p.month).padStart(2, '0')}-01`
        : `${p.year}-01-01`),
      value: p.value,
    })),
    __regionMeta: {
      code,
      name: `${d.indicator.name} — ${regionName}`,
      unit: d.indicator.unit,
      frequency: d.indicator.frequency || 'annual',
      category: 'compare.category.regions',
    },
  };
}

async function fetchWorldSeries(code, { signal }) {
  const parsed = parseWorldCompareCode(code);
  if (!parsed) throw new Error('compare.error.worldCode');
  const payload = await fetchWorldCompareOrCard(parsed.countrySlug, parsed.conceptSlug, { signal });
  const loc = currentUiLocale();
  const countryName = loc === 'en'
    ? (payload.meta.country_name_en || payload.meta.country_name)
    : payload.meta.country_name;
  const conceptName = loc === 'en'
    ? (payload.meta.concept_name_en || payload.meta.concept_name)
    : payload.meta.concept_name;
  return {
    data: payload.data,
    __worldMeta: {
      code,
      name: `${conceptName} — ${countryName}`,
      conceptName,
      countryName,
      unit: payload.meta.unit,
      frequency: payload.meta.frequency,
      category: 'compare.category.world',
      conceptSlug: payload.meta.concept_slug,
    },
  };
}

// Единый стиль «поля-поиска» для макро- и регионального выбора — чтобы они
// выглядели одинаково (требование: макро и регион не должны расходиться).
/** Ось Y по данным, а не от нуля: линия не прибита к верху пустого графика. */
const AXIS_DOMAIN = ['auto', 'auto'];

/** Вертикальная линия при наведении: тонкая, золотая, пунктиром. */
const HOVER_CURSOR = Object.freeze({ stroke: CHART_THEME.champagne, strokeWidth: 1, strokeDasharray: '4 4' });

const FIELD_CLS =
  'flex items-center gap-2 rounded-lg px-3 py-2 transition-colors fe-glass-2';

/** Шапка карточки добавления: иконка + заголовок + подсказка. */
function AddCardHeader({ icon, title, hint }) {
  const Icon = icon;
  return (
    <div className="mb-2.5 flex items-center gap-2">
      <span className="flex h-6 w-6 items-center justify-center rounded-md bg-champagne/12">
        <Icon className="h-3.5 w-3.5 text-champagne" />
      </span>
      <div className="min-w-0">
        <div className="text-sm font-medium text-text-secondary leading-none">
          {title}
        </div>
        {hint && <div className="mt-1 text-xs text-text-secondary leading-snug">{hint}</div>}
      </div>
    </div>
  );
}

/**
 * Телефон: список выбора открывается отдельным слоем на весь экран со своим полем поиска.
 * Раньше список раскрывался прямо под полем: тап по нему прокручивал страницу, а клавиатура
 * закрывала список (тестировщик решал, что «не работает»).
 */
function ComboSheet({
  ariaLabel, searchPlaceholder, query, onQuery, filtered, total, value, onPick, onClose,
}) {
  const t = useT();
  const inputRef = useRef(null);
  useEffect(() => {
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    const onKey = (event) => { if (event.key === 'Escape') onClose(); };
    document.addEventListener('keydown', onKey);
    const focusTimer = window.setTimeout(() => inputRef.current?.focus({ preventScroll: true }), 60);
    return () => {
      document.body.style.overflow = prevOverflow;
      document.removeEventListener('keydown', onKey);
      window.clearTimeout(focusTimer);
    };
  }, [onClose]);
  return createPortal(
    <div className="fe-z7-sheet" role="dialog" aria-modal="true" aria-label={ariaLabel}>
      <div className="fe-z7-sheet__bar">
        <label className="fe-z7-sheet__search">
          <Search className="h-4 w-4 shrink-0 text-text-tertiary" aria-hidden="true" />
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => onQuery(e.target.value)}
            placeholder={searchPlaceholder}
            aria-label={ariaLabel}
            className="min-w-0 flex-1 bg-transparent text-base text-text-primary outline-none placeholder:text-text-tertiary"
          />
        </label>
        <button type="button" className="fe-z7-sheet__close" onClick={onClose} aria-label={t('common.close')}>
          <X className="h-5 w-5" aria-hidden="true" />
        </button>
      </div>
      <div className="fe-z7-sheet__list">
        {total === 0 ? (
          <div className="px-4 py-6 text-sm text-text-tertiary">{t('compare.nothingFound')}</div>
        ) : (
          filtered.map((g) => (
            <div key={g.label || '_'}>
              {g.label && <div className="fe-z7-sheet__group">{g.label}</div>}
              {g.items.map((it) => (
                <button
                  key={it.value}
                  type="button"
                  onClick={() => onPick(it.value)}
                  className="fe-z7-sheet__item"
                >
                  <span className="min-w-0 break-words text-[15px] leading-snug text-text-primary">{it.label}</span>
                  {it.value === value
                    ? <Check className="h-4 w-4 shrink-0 text-champagne-ink" aria-hidden="true" />
                    : it.hint && <span className="shrink-0 text-xs text-text-secondary">{it.hint}</span>}
                </button>
              ))}
            </div>
          ))
        )}
      </div>
    </div>,
    document.body,
  );
}

/**
 * Searchable single-select combobox: открывается по клику (весь список,
 * скроллится), фильтруется вводом. Поддерживает группы (секции показателей).
 * Один визуальный язык с макро-поиском (`AddIndicator`). На телефоне список
 * открывается слоем на весь экран (`ComboSheet`).
 */
function ComboSelect({
  groups, value, onChange, placeholder, searchPlaceholder, ariaLabel, disabled, trackContext,
}) {
  const t = useT();
  const phone = useMediaQuery('(max-width: 639px)');
  const [query, setQuery] = useState('');
  const [open, setOpen] = useState(false);
  const boxRef = useRef(null);
  const fieldRef = useRef(null);

  const selectedLabel = useMemo(() => {
    for (const g of groups) {
      const hit = g.items.find((it) => it.value === value);
      if (hit) return hit.label;
    }
    return '';
  }, [groups, value]);

  const filtered = useMemo(() => {
    const searchKind = trackContext === 'compare-region' || trackContext === 'compare-world-region' ? 'region' : undefined;
    return groups
      .map((g) => ({
        label: g.label,
        items: filterSearchOptions(g.items, query, {
          searchKind,
          getSearchItem: (item) => ({ ...item, section_name: g.label }),
        }),
      }))
      .filter((g) => g.items.length);
  }, [groups, query, trackContext]);

  const total = filtered.reduce((n, g) => n + g.items.length, 0);

  // Спрос-аналитика: каждый набранный запрос в комбобоксах сравнения тоже
  // уходит в search_query (директива «собирать все поиски», 2026-07-05).
  useSearchTracking(trackContext || 'compare-combo', open ? query : '', total);

  const closeSheet = useCallback(() => {
    setOpen(false);
    setQuery('');
    fieldRef.current?.blur();
  }, []);

  return (
    <div className="relative" ref={boxRef}>
      <div
        className={cn(
          FIELD_CLS,
          'pointer-coarse:min-h-12',
          disabled ? 'opacity-60' : '',
          value && !open && '',
        )}
      >
        <Search className="h-4 w-4 shrink-0 text-text-tertiary" />
        <input
          ref={fieldRef}
          type="text"
          aria-label={ariaLabel}
          disabled={disabled}
          readOnly={phone}
          value={open && !phone ? query : selectedLabel}
          placeholder={value && !open ? selectedLabel : (open && !phone ? searchPlaceholder : placeholder)}
          onFocus={() => { setOpen(true); setQuery(''); }}
          onClick={() => setOpen(true)}
          onBlur={phone ? undefined : () => setTimeout(() => setOpen(false), 150)}
          onChange={(e) => setQuery(e.target.value)}
          className="min-w-0 flex-1 bg-transparent text-sm text-text-primary outline-none placeholder:text-text-tertiary disabled:cursor-not-allowed pointer-coarse:text-base"
        />
        {value && !open ? (
          <button
            type="button"
            aria-label={t('common.clear')}
            onMouseDown={(e) => { e.preventDefault(); onChange(''); setQuery(''); }}
            className="shrink-0 text-text-tertiary hover:text-text-primary"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        ) : (
          <ChevronDown className={cn('h-4 w-4 shrink-0 text-text-tertiary transition-transform', open && 'rotate-180')} />
        )}
      </div>

      {open && !disabled && phone && (
        <ComboSheet
          ariaLabel={ariaLabel}
          searchPlaceholder={searchPlaceholder}
          query={query}
          onQuery={setQuery}
          filtered={filtered}
          total={total}
          value={value}
          onClose={closeSheet}
          onPick={(picked) => { onChange(picked); closeSheet(); }}
        />
      )}

      {open && !disabled && !phone && (
        <div className="absolute z-40 mt-2 max-h-72 w-full overflow-auto rounded-xl shadow-2xl fe-glass-pop">
          {total === 0 ? (
            <div className="px-4 py-3 text-sm text-text-tertiary">{t('compare.nothingFound')}</div>
          ) : (
            filtered.map((g) => (
              <div key={g.label || '_'}>
                {g.label && (
                  <div className="sticky top-0 bg-obsidian-light px-3 py-1.5 text-xs font-medium text-text-secondary">
                    {g.label}
                  </div>
                )}
                {g.items.map((it) => (
                  <button
                    key={it.value}
                    type="button"
                    onMouseDown={(e) => { e.preventDefault(); onChange(it.value); setQuery(''); setOpen(false); }}
                    title={it.label}
                    className="fe-tap flex w-full items-start justify-between gap-3 px-4 py-2.5 text-left hover:bg-obsidian-lighter transition-colors"
                  >
                    <span className="line-clamp-2 min-w-0 break-words text-sm leading-snug text-text-primary">{it.label}</span>
                    {it.value === value
                      ? <Check className="mt-0.5 h-3.5 w-3.5 shrink-0 text-champagne" />
                      : it.hint && <span className="mt-0.5 shrink-0 text-xs text-text-secondary">{it.hint}</span>}
                  </button>
                ))}
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
}

/** Лимит рядов достигнут: говорим, что сделать, и даём кнопку для гостя (поле при этом серое). */
function CapNotice({ text, onLimit, onClear }) {
  const t = useT();
  return (
    <div className="fe-z7-cap" role="status" data-testid="compare-cap-notice">
      <p>{text}</p>
      {onClear && (
        <button type="button" onClick={onClear} className="fe-z7-cap__btn" data-testid="compare-cap-clear">
          {t('c9d.compare.startOver')}
        </button>
      )}
      {onLimit && (
        <button type="button" onClick={onLimit} className="fe-z7-cap__btn">
          {t('w6a.compare.register')}
        </button>
      )}
    </div>
  );
}

/**
 * Добавление регионального ряда: тот же язык, что и макро-поиск, но разбит на
 * два searchable-combobox'а — «Регион» и «Показатель» — и кнопку «Добавить».
 * Оба поля можно листать целиком или искать вводом (85 регионов × десятки
 * показателей).
 */
function AddRegionSeries({
  selected, onAdd, atCap, capHint, compatibilityFor, onLimit,
}) {
  const t = useT();
  const landing = useRegionsLanding();
  const catalog = useRegionsCatalog();
  const [regionSlug, setRegionSlug] = useState('');
  const [indCode, setIndCode] = useState('');

  const regionGroups = useMemo(() => {
    if (!landing.data) return [{ label: '', items: [] }];
    const items = landing.data.districts
      .flatMap((d) => d.regions.map((r) => ({ ...r, value: r.slug, label: r.name })))
      .sort((a, b) => a.label.localeCompare(b.label, 'ru'));
    return [{ label: '', items }];
  }, [landing.data]);

  const indicatorGroups = useMemo(() => {
    const sections = catalog.data?.sections || [];
    return sections.map((s) => ({
      label: s.name,
      items: s.indicators
        .filter((indicator) => !regionSlug
          || !compatibilityFor
          || compatibilityFor(`r:${regionSlug}:${indicator.code}`).allowed)
        .map((i) => ({ ...i, value: i.code, label: i.name })),
    })).filter((section) => section.items.length);
  }, [catalog.data, compatibilityFor, regionSlug]);

  // Выбор показателя сразу ставит ряд на график. Регион остаётся: удобно добавить второй показатель того же региона.
  const handlePick = (value) => {
    setIndCode('');
    if (!value || !regionSlug || atCap) return;
    const code = `r:${regionSlug}:${value}`;
    const compatibility = compatibilityFor ? compatibilityFor(code) : { allowed: true };
    if (selected.includes(code) || !compatibility.allowed) return;
    onAdd(code);
    track(events.REGION_COMPARE_ADD, { code });
  };

  return (
    <div className="fe-glass-lite rounded-xl p-3">
      <AddCardHeader
        icon={MapPin}
        title={t('compare.addRegionTitle')}
        hint={t('compare.addRegionHint')}
      />
      <div className="flex flex-col gap-2">
        <ComboSelect
          groups={regionGroups}
          value={regionSlug}
          onChange={setRegionSlug}
          ariaLabel={t('compare.regionAria')}
          placeholder={t('compare.regionPlaceholder')}
          searchPlaceholder={t('compare.regionSearch')}
          disabled={atCap}
          trackContext="compare-region"
        />
        <ComboSelect
          groups={indicatorGroups}
          value={indCode}
          onChange={handlePick}
          ariaLabel={t('compare.regionIndicatorAria')}
          placeholder={t('compare.regionIndicatorPlaceholder')}
          searchPlaceholder={t('compare.regionIndicatorSearch')}
          disabled={atCap || !regionSlug}
          trackContext="compare-region-indicator"
        />
        {atCap && <CapNotice text={capHint} onLimit={onLimit} />}
      </div>
    </div>
  );
}

function AddSubnationalSeries({
  countrySlug, selected, onAdd, atCap, capHint, compatibilityFor, onLimit,
}) {
  const t = useT();
  const { locale } = useLocale();
  const hub = useWorldRegionsHub(countrySlug);
  const [regionSlug, setRegionSlug] = useState('');
  const [indCode, setIndCode] = useState('');
  const kindPlural = hub.data?.kind_label_plural || t('world.regions.fallbackKindPlural');

  const regionGroups = useMemo(() => {
    const items = (hub.data?.regions || [])
      .map((r) => ({
        ...r,
        value: r.slug,
        label: locale === 'en' ? (r.name_en || r.name) : r.name,
      }))
      .sort((a, b) => a.label.localeCompare(b.label, locale === 'en' ? 'en' : 'ru'));
    return [{ label: '', items }];
  }, [hub.data, locale]);

  const indicatorGroups = useMemo(() => {
    const sections = hub.data?.sections || [];
    if (sections.length) {
      return sections.map((s) => ({
        label: s.name,
        items: (s.indicators || [])
          .filter((indicator) => !regionSlug
            || !compatibilityFor
            || compatibilityFor(`s:${countrySlug}:${regionSlug}:${indicator.code}`).allowed)
          .map((i) => ({ ...i, value: i.code, label: i.name })),
      })).filter((section) => section.items.length);
    }
    return [{
      label: '',
      items: (hub.data?.indicators || [])
        .filter((indicator) => !regionSlug
          || !compatibilityFor
          || compatibilityFor(`s:${countrySlug}:${regionSlug}:${indicator.code}`).allowed)
        .map((i) => ({ ...i, value: i.code, label: i.name })),
    }].filter((section) => section.items.length);
  }, [hub.data, compatibilityFor, countrySlug, regionSlug]);

  const handlePick = (value) => {
    setIndCode('');
    if (!value || !regionSlug || atCap) return;
    const code = `s:${countrySlug}:${regionSlug}:${value}`;
    const compatibility = compatibilityFor ? compatibilityFor(code) : { allowed: true };
    if (selected.includes(code) || !compatibility.allowed) return;
    onAdd(code);
    track(events.REGION_COMPARE_ADD, { code, world: true });
  };

  return (
    <div className="fe-glass-lite rounded-xl p-3">
      <AddCardHeader
        icon={MapPin}
        title={t('compare.addSubnationalTitle', { kind: kindPlural })}
        hint={t('compare.addSubnationalHint')}
      />
      <div className="flex flex-col gap-2">
        <ComboSelect
          groups={regionGroups}
          value={regionSlug}
          onChange={setRegionSlug}
          ariaLabel={t('compare.subnationalAria', { kind: kindPlural })}
          placeholder={t('compare.subnationalPlaceholder', { kind: kindPlural })}
          searchPlaceholder={t('compare.subnationalSearch')}
          disabled={atCap}
          trackContext="compare-world-region"
        />
        <ComboSelect
          groups={indicatorGroups}
          value={indCode}
          onChange={handlePick}
          ariaLabel={t('compare.regionIndicatorAria')}
          placeholder={t('compare.regionIndicatorPlaceholder')}
          searchPlaceholder={t('compare.regionIndicatorSearch')}
          disabled={atCap || !regionSlug}
          trackContext="compare-world-region-indicator"
        />
        {atCap && <CapNotice text={capHint} onLimit={onLimit} />}
      </div>
    </div>
  );
}

function russiaLandingPool(indicators, worldItems, locale) {
  const macros = [...(indicators || [])];
  const seen = new Set(macros.map((item) => item.code));
  for (const item of worldItems || []) {
    if (item.country_slug !== 'russia' || seen.has(item.code)) continue;
    seen.add(item.code);
    const conceptName = locale === 'en'
      ? (item.concept_name_en || item.concept_name)
      : item.concept_name;
    macros.push({
      code: item.code,
      // Понятие нужно поиску: по слову «ВВП» находится «Валовой внутренний продукт» России из общего набора стран.
      concept_slug: item.concept_slug,
      name: conceptName,
      name_en: item.concept_name_en || item.concept_name,
      category: item.category || '',
      unit: item.unit || '',
      seo_keywords: '',
    });
  }
  return macros;
}

function AddIndicator({
  indicators, selected, onAdd, atCap, capHint, compatibilityFor, placeholder, onLimit, onClear,
}) {
  const t = useT();
  const { locale } = useLocale();
  const [query, setQuery] = useState('');
  const [openList, setOpenList] = useState(false);
  // Директория сравнения: показываем ВСЕ показатели (минус уже выбранные),
  // список скроллится (`max-h-80 overflow-auto`). Жёсткого «топ-8» нет —
  // листать можно весь каталог (звонок 2026-06-25). Любой новый индикатор
  // приходит из API и попадает сюда автоматически. Поиск идёт и по
  // seo_keywords (синонимы/корни), как в основном поиске.
  const results = useMemo(() => {
    const pool = (indicators || []).filter((i) =>
      !selected.includes(i.code)
      && (!compatibilityFor || compatibilityFor(i.code).allowed));
    // Круг 10 (Ср1): рядом с рядами других стран российский показатель добавляется своим двойником из общего набора.
    // Если двойник уже есть в списке сам («ВВП в текущих долларах США» и тот же показатель из набора стран), второй не показываем.
    const targets = new Set(pool.map((i) => i.code));
    const unique = compatibilityFor
      ? pool.filter((i) => {
        const target = compatibilityFor(i.code).addCode;
        return !target || target === i.code || !targets.has(target);
      })
      : pool;
    return filterSearchOptions(unique, query, {
      getSearchItem: (item) => ({ ...item, country_slug: 'russia' }),
    });
  }, [indicators, selected, query, compatibilityFor]);

  // Dual-write спрос-аналитики (даже без клика по результату):
  // 1) легаси compare_search — Пульс/BI уже читают этот канал;
  // 2) единый search_query (context=compare-macro) — общий контур всех поисков.
  const resultsCount = results.length;
  useEffect(() => {
    const q = query.trim();
    if (q.length < 2) return undefined;
    const timer = setTimeout(() => {
      track(events.COMPARE_SEARCH, { q: q.slice(0, 40), results: resultsCount });
    }, 900);
    return () => clearTimeout(timer);
  }, [query, resultsCount]);
  useSearchTracking('compare-macro', query, resultsCount);

  return (
    <div className="relative">
      <div className={cn(
        FIELD_CLS,
        atCap ? 'opacity-60' : '',
      )}>
        <Search className="w-4 h-4 text-text-tertiary shrink-0" />
        <input
          type="text"
          value={query}
          disabled={atCap}
          onChange={(e) => setQuery(e.target.value)}
          onFocus={() => setOpenList(true)}
          onBlur={() => setTimeout(() => setOpenList(false), 150)}
          placeholder={atCap ? t('z7.compare.capField') : (placeholder || t('compare.macroPlaceholder'))}
          className="flex-1 bg-transparent text-sm text-text-primary outline-none placeholder:text-text-tertiary disabled:cursor-not-allowed"
        />
        <ChevronDown className="w-4 h-4 shrink-0 text-text-tertiary" />
      </div>
      {atCap && <div className="mt-2"><CapNotice text={capHint} onLimit={onLimit} onClear={onClear} /></div>}
      {openList && !atCap && results.length === 0 && (
        <div className="absolute z-40 mt-2 w-full rounded-xl px-4 py-3 text-sm text-text-tertiary shadow-2xl fe-glass-pop">
          {query.trim() ? t('compare.nothingFound') : t('c9d.compare.nothingLeft')}
        </div>
      )}
      {openList && !atCap && results.length > 0 && (
        <div className="absolute z-40 mt-2 w-full max-h-80 overflow-auto rounded-xl shadow-2xl fe-glass-pop">
          {results.map((ind) => (
            <button
              key={ind.code}
              type="button"
              onMouseDown={(e) => { e.preventDefault(); onAdd(ind.code); setQuery(''); }}
              title={ind.name}
              className="fe-tap flex w-full items-start justify-between gap-3 px-4 py-2.5 text-left hover:bg-obsidian-lighter transition-colors"
            >
              <span className="line-clamp-2 min-w-0 break-words text-sm leading-snug text-text-primary">{ind.name}</span>
              <span className="mt-0.5 flex items-center gap-2 shrink-0">
                <span className="text-xs text-text-secondary">{unitHint(ind.unit, locale)}</span>
                <Plus className="w-3.5 h-3.5 text-champagne" />
              </span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

/** Показатели, которые люди ищут чаще всего: показываются в списке первыми. */
const POPULAR_CONCEPTS = ['gdp-usd', 'hicp-index', 'unemployment-rate', 'population', 'gdp-per-capita-usd'];

/**
 * Показатель выбранной страны (страна уже зафиксирована в дереве пикера).
 * Код ряда — `w:{slug}:{concept}`. Выбор в списке сразу ставит ряд на график, без второго нажатия.
 */
function AddWorldCountrySeries({
  items, countrySlug, selected, onAdd, atCap, capHint, compatibilityFor, onLimit, onClear,
}) {
  const t = useT();
  const { locale } = useLocale();

  const conceptItems = useMemo(() => {
    const map = new Map();
    for (const item of items || []) {
      if (item.country_slug !== countrySlug) continue;
      if (selected.includes(item.code) || !compatibilityFor(item.code).allowed) continue;
      if (map.has(item.concept_slug)) continue;
      const freq = item.frequency === 'monthly'
        ? t('compare.freq.monthShort')
        : item.frequency === 'quarterly'
          ? t('compare.freq.quarterShort')
          : t('compare.freq.yearShort');
      const fullName = locale === 'en' ? (item.concept_name_en || item.concept_name) : item.concept_name;
      map.set(item.concept_slug, {
        ...item,
        value: item.concept_slug,
        // Короткое название для списка; полное остаётся в поиске (name).
        label: conceptShortLabel(item.concept_slug, fullName, t),
        name: fullName,
        name_en: item.concept_name_en,
        hint: freq,
        code: item.code,
      });
    }
    return [...map.values()].sort((a, b) => a.label.localeCompare(b.label, locale === 'en' ? 'en' : 'ru'));
  }, [items, countrySlug, selected, compatibilityFor, t, locale]);

  const groups = useMemo(() => {
    const popular = POPULAR_CONCEPTS
      .map((slug) => conceptItems.find((item) => item.value === slug))
      .filter(Boolean);
    const rest = conceptItems.filter((item) => !popular.includes(item));
    return [
      { label: t('w6g.compare.popular'), items: popular },
      { label: popular.length ? t('w6g.compare.allIndicators') : t('compare.conceptGroup'), items: rest },
    ].filter((group) => group.items.length);
  }, [conceptItems, t]);

  // Пустой список бывает по трём разным причинам, и говорить про них надо по-разному.
  const emptyKey = (() => {
    if (conceptItems.length) return null;
    const own = (items || []).filter((item) => item.country_slug === countrySlug);
    if (own.some((item) => selected.includes(item.code))) return 'y1.compare.allAdded';
    return own.length ? 'y1.compare.noMatch' : 'compare.noCountrySeries';
  })();

  const pick = (conceptSlug) => {
    const item = conceptItems.find((it) => it.value === conceptSlug);
    if (!item || atCap) return;
    onAdd(item.code);
  };

  // Круг 10: к уже выбранному подходит ровно один показатель — добавляем его одним нажатием, без открытия списка.
  const onlyItem = selected.length > 0 && conceptItems.length === 1 ? conceptItems[0] : null;

  return (
    <div className="grid gap-2">
      {onlyItem && !atCap ? (
        <Button
          variant="primary"
          onClick={() => pick(onlyItem.value)}
          data-testid="compare-add-only"
          className="justify-self-start"
        >
          <Plus className="h-4 w-4" aria-hidden="true" />
          {t('c10k.compare.addOnly', { name: onlyItem.label })}
        </Button>
      ) : (
        <ComboSelect
          groups={groups}
          value=""
          onChange={pick}
          placeholder={t('w6g.compare.findIndicator')}
          searchPlaceholder={t('w6g.compare.findIndicator')}
          ariaLabel={t('compare.conceptAria')}
          disabled={atCap || conceptItems.length === 0}
          trackContext="compare-world-concept"
        />
      )}
      {atCap && <CapNotice text={capHint} onLimit={onLimit} onClear={onClear} />}
      {emptyKey && (
        <p className="text-xs leading-relaxed text-text-secondary">
          {t(emptyKey)}
        </p>
      )}
      {emptyKey === 'y1.compare.noMatch' && onClear && (
        <button type="button" onClick={onClear} className="fe-z7-cap__btn justify-self-start" data-testid="compare-nomatch-clear">
          {t('c9d.compare.startOver')}
        </button>
      )}
    </div>
  );
}

const BRANCH_BTN = (active) => cn(
  'rounded-xl px-3 py-2.5 text-sm font-medium transition-colors text-left',
  active
    ? 'bg-champagne/15 text-champagne'
    : 'bg-obsidian-lighter text-text-secondary hover:text-champagne',
);

/** Шаг назад в дереве пикера. */
function PickerBack({ label, onClick }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="mb-3 inline-flex items-center gap-1.5 text-sm font-medium text-text-secondary hover:text-champagne-ink transition-colors"
    >
      <ArrowLeft className="h-3.5 w-3.5" />
      {label}
    </button>
  );
}

/**
 * Дерево «сначала страна»: Россия → макро | регионы; другая страна → показатель.
 */
function CompareSeriesPicker({
  indicators, worldItems, selected, onAdd, atCap, capHint, compatibilityFor,
  status = '', catalogLoading = false, onLimit, onClear,
}) {
  const t = useT();
  const { locale } = useLocale();
  const [countryKey, setCountryKey] = useState(null);
  const [russiaBranch, setRussiaBranch] = useState(null);
  const [worldBranch, setWorldBranch] = useState(null);
  const [countryQuery, setCountryQuery] = useState('');
  const subnationalHub = useWorldRegionsHub(
    countryKey && countryKey !== 'russia' ? countryKey : undefined,
  );
  const hasSubnational = Boolean(subnationalHub.data?.regions?.length);
  const subnationalKind = subnationalHub.data?.kind_label_plural || t('world.regions.fallbackKindPlural');

  const countries = useMemo(() => {
    const map = new Map();
    for (const item of worldItems || []) {
      if (!item.country_slug || map.has(item.country_slug)) continue;
      map.set(item.country_slug, {
        key: item.country_slug,
        country_slug: item.country_slug,
        country_name: item.country_name,
        country_name_en: item.country_name_en,
        label: locale === 'en'
          ? (item.country_name_en || item.country_name)
          : item.country_name,
      });
    }
    return [...map.values()].sort((a, b) => a.label.localeCompare(b.label, locale === 'en' ? 'en' : 'ru'));
  }, [worldItems, locale]);

  // Круг 10 (Ср1): к уже выбранному подходят не все страны. Оставляем те, у кого есть ряд, который можно добавить,
  // чтобы выбор не заканчивался тупиком «не нашлось» (особенно когда сначала взяли США, а потом идут к России).
  const availableSlugs = useMemo(() => {
    if (!selected.length || !compatibilityFor) return null;
    const set = new Set();
    for (const item of worldItems || []) {
      if (selected.includes(item.code)) {
        // Страна, ряд которой уже на графике, остаётся в списке: открыв её, человек увидит, что добавлено всё подходящее.
        set.add(item.country_slug);
        continue;
      }
      if (set.has(item.country_slug)) continue;
      if (compatibilityFor(item.code).allowed) set.add(item.country_slug);
    }
    if (!set.has('russia') && (indicators || []).some((ind) => (
      !selected.includes(ind.code) && compatibilityFor(ind.code).allowed
    ))) set.add('russia');
    return set.size ? set : null;
  }, [selected, worldItems, indicators, compatibilityFor]);

  const filteredCountries = useMemo(() => {
    const q = countryQuery.trim().toLowerCase();
    const russia = { key: 'russia', country_slug: 'russia', label: t('compare.russia') };
    const worldOnly = countries.filter((c) => c.key !== 'russia');
    if (q) {
      // Английская версия: Россия в поиске стоит там, где её поставит релевантность, а не первой.
      if (locale === 'en') return filterSearchCountries([...worldOnly, russia], q);
      const found = filterSearchCountries(worldOnly, q);
      return filterSearchCountries([russia], q).length > 0 ? [russia, ...found] : found;
    }
    const pool = availableSlugs ? worldOnly.filter((c) => availableSlugs.has(c.key)) : worldOnly;
    const showRussia = !availableSlugs || availableSlugs.has('russia');
    // Английская версия: по размеру ВВП, Россия на своём месте и не первая. Русская: Россия первой, дальше по алфавиту.
    if (locale === 'en') {
      return orderCountriesByGdp([...pool, ...(showRussia ? [russia] : [])], (c) => c.key);
    }
    return showRussia ? [russia, ...pool] : pool;
  }, [countries, countryQuery, locale, t, availableSlugs]);
  const countriesRestricted = Boolean(availableSlugs)
    && (countries.some((c) => c.key !== 'russia' && !availableSlugs.has(c.key)) || !availableSlugs.has('russia'));

  // Человек часто вводит сюда сам показатель («дизель», «инфляция»), а не страну.
  // Вместо тупика «Ничего не найдено» спрашиваем общий поиск и показываем
  // подходящие российские ряды — их можно добавить сразу. Общий поиск знает и
  // карточки вне витрины (дизель, АИ-95), которых нет в списке `indicators`.
  const indicatorNeedle = !countryKey && filteredCountries.length === 0 ? countryQuery.trim() : '';
  const indicatorSearch = useGlobalSearch(indicatorNeedle, { enabled: indicatorNeedle.length >= 2, limit: 30 });
  const indicatorMatches = useMemo(() => {
    if (indicatorNeedle.length < 2 || indicatorSearch.isDebouncing) return [];
    return (indicatorSearch.data?.results || [])
      // Базовая карточка показателя: производные режимы открываются уже на графике.
      .filter((item) => item.kind === 'russia' && item.code && !String(item.path || '').includes('?'))
      .filter((item) => !selected.includes(item.code)
        && (!compatibilityFor || compatibilityFor(item.code).allowed))
      .slice(0, 12);
  }, [indicatorNeedle, indicatorSearch.data, indicatorSearch.isDebouncing, selected, compatibilityFor]);
  const indicatorMatchesPending = indicatorNeedle.length >= 2
    && (indicatorSearch.isDebouncing || indicatorSearch.isFetching);

  // Поиск страны в дереве сравнения — без клика по результату.
  useSearchTracking(
    'compare-country',
    countryKey ? '' : countryQuery,
    filteredCountries.length + indicatorMatches.length,
  );

  const selectedCountry = countryKey === 'russia'
    ? { key: 'russia', label: t('compare.russia') }
    : countries.find((c) => c.key === countryKey) || null;
  const activeWorldConcept = selected.map(parseWorldCompareCode).find(Boolean)?.conceptSlug;
  const activeWorldConceptItem = worldItems.find((item) => item.concept_slug === activeWorldConcept);
  const activeWorldConceptName = activeWorldConceptItem
    ? conceptShortLabel(
      activeWorldConcept,
      locale === 'en' ? (activeWorldConceptItem.concept_name_en || activeWorldConceptItem.concept_name) : activeWorldConceptItem.concept_name,
      t,
    )
    : undefined;

  // Тот же показатель у России одним нажатием: ряд США уже на графике, и Россию не нужно искать в общем списке.
  const russiaSameItem = activeWorldConcept
    ? worldItems.find((item) => item.code === `w:russia:${activeWorldConcept}`)
    : null;
  const russiaSameAllowed = Boolean(russiaSameItem)
    && !selected.includes(russiaSameItem.code)
    && compatibilityFor(russiaSameItem.code).allowed;

  // Подсказка шага зависит от состояния: не просим «выбрать показатель», когда все уже на графике.
  const countryHasOptions = Boolean(
    countryKey && countryKey !== 'russia'
    && worldItems.some((item) => item.country_slug === countryKey
      && !selected.includes(item.code) && compatibilityFor(item.code).allowed),
  );
  const stepHint = !countryKey
    ? t('compare.pickCountryFirst')
    : countryKey === 'russia' || countryHasOptions || !selectedCountry
      ? t('w6g.compare.pickIndicatorInstant')
      : t('w6g.compare.countryDone', { country: selectedCountry.label });

  const resetCountry = () => {
    setCountryKey(null);
    setRussiaBranch(null);
    setWorldBranch(null);
    setCountryQuery('');
  };

  const selectCountry = (key) => {
    setCountryKey(key);
    setRussiaBranch(null);
    setWorldBranch(null);
    setCountryQuery('');
  };

  return (
    <div className="fe-panel overflow-visible rounded-2xl p-4 shadow-[0_16px_45px_rgba(35,30,16,0.05)] sm:p-5">
      <div className="mb-5 pb-5 k5-seam">
        <div className="text-sm font-medium text-champagne-ink">{t('w6g.compare.pickerTitle')}</div>
        <div className="mt-1 text-[15px] text-text-primary">{stepHint}</div>
        {status && (
          <p role="status" data-testid="compare-status" className="mt-2 text-[13px] leading-snug text-champagne-ink">
            {status}
          </p>
        )}
        {activeWorldConceptName && (
          <p className="mt-2 text-xs leading-relaxed text-text-tertiary">
            {t('compare.sameConceptHint', { indicator: activeWorldConceptName })}
          </p>
        )}
      </div>

      {!countryKey && atCap && (
        <CapNotice text={capHint} onLimit={onLimit} onClear={onClear} />
      )}

      {!countryKey && !atCap && (
        <CompareCountryStep
          countries={filteredCountries}
          query={countryQuery}
          onQuery={setCountryQuery}
          onSelect={selectCountry}
          indicatorMatches={indicatorMatches.map((item) => ({
            code: item.code,
            label: locale === 'en' ? (item.name_en || item.name) : (item.name_ru || item.name),
          }))}
          matchesPending={indicatorMatchesPending}
          onAddIndicator={(item) => { onAdd(item.code); setCountryQuery(''); }}
          atCap={atCap}
          capHint={capHint}
          loading={catalogLoading}
          restrictNote={countriesRestricted ? t('c10k.compare.onlyMatching', {
            indicator: activeWorldConceptName || t('c10k.compare.chosenIndicator'),
          }) : ''}
        />
      )}

      {countryKey === 'russia' && !russiaBranch && (
        <div>
          <PickerBack label={t('compare.backToCountry')} onClick={resetCountry} />
          {russiaSameAllowed && !atCap && (
            <Button
              variant="primary"
              className="mb-4"
              data-testid="compare-add-russia-same"
              onClick={() => onAdd(russiaSameItem.code)}
            >
              <Plus className="h-4 w-4" aria-hidden="true" />
              {t('c10k.compare.addRussiaSame', { name: activeWorldConceptName || t('c10k.compare.chosenIndicator') })}
            </Button>
          )}
          <div className="mb-4">
            <div className="mb-2 text-sm font-medium text-text-secondary">
              {t('compare.conceptGroup')}
            </div>
            <div className="rounded-xl p-3 fe-glass-2">
              <AddIndicator
                indicators={russiaLandingPool(indicators, worldItems, locale)}
                selected={selected}
                onAdd={onAdd}
                atCap={atCap}
                capHint={capHint}
                compatibilityFor={compatibilityFor}
                placeholder={t('compare.conceptSearch')}
                onLimit={onLimit}
                onClear={onClear}
              />
            </div>
          </div>
          <div className="mb-2 text-sm font-medium text-text-secondary">
            {t('compare.russiaWhat')}
          </div>
          <div className="grid gap-2 sm:grid-cols-2">
            <button
              type="button"
              onClick={() => setRussiaBranch('macro')}
              className={BRANCH_BTN(false)}
            >
              <span className="flex items-center gap-2">
                <Landmark className="h-4 w-4 shrink-0" />
                {t('compare.macro')}
              </span>
              <span className="mt-1 block text-xs font-normal text-text-secondary">
                {t('compare.macroHint')}
              </span>
            </button>
            <button
              type="button"
              onClick={() => setRussiaBranch('regions')}
              className={BRANCH_BTN(false)}
            >
              <span className="flex items-center gap-2">
                <MapPin className="h-4 w-4 shrink-0" />
                {t('w6g.compare.regionsRussia')}
              </span>
              <span className="mt-1 block text-xs font-normal text-text-secondary">
                {t('compare.regionsBranchHint')}
              </span>
            </button>
          </div>
        </div>
      )}

      {countryKey === 'russia' && russiaBranch === 'macro' && (
        <div>
          <PickerBack label={t('compare.backToRussia')} onClick={() => setRussiaBranch(null)} />
          <div className="mb-2 text-sm font-medium text-text-secondary">
            {t('compare.macroRussia')}
          </div>
          <div className="rounded-xl p-3 fe-glass-2">
            <AddIndicator
              indicators={russiaLandingPool(indicators, worldItems, locale)}
              selected={selected}
              onAdd={onAdd}
              atCap={atCap}
              capHint={capHint}
              compatibilityFor={compatibilityFor}
              onLimit={onLimit}
              onClear={onClear}
            />
          </div>
        </div>
      )}

      {countryKey === 'russia' && russiaBranch === 'regions' && (
        <div>
          <PickerBack label={t('compare.backToRussia')} onClick={() => setRussiaBranch(null)} />
          <div className="mb-2 text-sm font-medium text-text-secondary">
            {t('compare.regionalSeries')}
          </div>
          <AddRegionSeries
            selected={selected}
            onAdd={onAdd}
            atCap={atCap}
            capHint={capHint}
            compatibilityFor={compatibilityFor}
            onLimit={onLimit}
          />
          <p className="mt-3 text-xs leading-relaxed text-text-tertiary">
            {t('compare.compareRegionsCta')}{' '}
            <Link to={regionHubPath()} className="text-champagne hover:underline">
              {t('compare.regionsSection')}
            </Link>
          </p>
        </div>
      )}

      {countryKey && countryKey !== 'russia' && selectedCountry && hasSubnational && !worldBranch && (
        <div>
          <PickerBack label={t('compare.backToCountry')} onClick={resetCountry} />
          <div className="mb-2 text-sm font-medium text-text-secondary">
            {t('compare.countryWhat', { country: selectedCountry.label })}
          </div>
          <div className="grid gap-2 sm:grid-cols-2">
            <button
              type="button"
              onClick={() => setWorldBranch('macro')}
              className={BRANCH_BTN(false)}
            >
              <span className="flex items-center gap-2">
                <Globe2 className="h-4 w-4 shrink-0" />
                {t('compare.macro')}
              </span>
              <span className="mt-1 block text-xs font-normal text-text-secondary">
                {t('compare.macroHint')}
              </span>
            </button>
            <button
              type="button"
              onClick={() => setWorldBranch('regions')}
              className={BRANCH_BTN(false)}
            >
              <span className="flex items-center gap-2">
                <MapPin className="h-4 w-4 shrink-0" />
                {subnationalKind}
              </span>
              <span className="mt-1 block text-xs font-normal text-text-secondary">
                {t('compare.subnationalBranchHint')}
              </span>
            </button>
          </div>
        </div>
      )}

      {countryKey && countryKey !== 'russia' && selectedCountry && (
        (hasSubnational ? worldBranch === 'macro' : true)
      ) && (
        <div>
          <PickerBack
            label={hasSubnational ? t('compare.countryWhat', { country: selectedCountry.label }) : t('compare.backToCountry')}
            onClick={hasSubnational ? () => setWorldBranch(null) : resetCountry}
          />
          <div className="mb-2 text-sm font-medium text-text-secondary">
            {t('compare.countryIndicator', { country: selectedCountry.label })}
          </div>
          <div className="rounded-xl p-3 fe-glass-2">
            <AddWorldCountrySeries
              items={worldItems}
              countrySlug={countryKey}
              selected={selected}
              onAdd={onAdd}
              atCap={atCap}
              capHint={capHint}
              compatibilityFor={compatibilityFor}
              onLimit={onLimit}
              onClear={onClear}
            />
          </div>
        </div>
      )}

      {countryKey && countryKey !== 'russia' && selectedCountry && worldBranch === 'regions' && (
        <div>
          <PickerBack
            label={t('compare.countryWhat', { country: selectedCountry.label })}
            onClick={() => setWorldBranch(null)}
          />
          <div className="mb-2 text-sm font-medium text-text-secondary">
            {t('compare.subnationalSeries', { kind: subnationalKind })}
          </div>
          <AddSubnationalSeries
            countrySlug={countryKey}
            selected={selected}
            onAdd={onAdd}
            atCap={atCap}
            capHint={capHint}
            compatibilityFor={compatibilityFor}
            onLimit={onLimit}
          />
          <p className="mt-3 text-xs leading-relaxed text-text-tertiary">
            {t('compare.compareRegionsCta')}{' '}
            <Link to={countryRegionsPath(countryKey)} className="text-champagne hover:underline">
              {t('compare.subnationalSection', { kind: subnationalKind })}
            </Link>
          </p>
        </div>
      )}
    </div>
  );
}

function UpsellModal({ open, onClose }) {
  const t = useT();
  if (!open) return null;
  return (
    <div
      className="fixed inset-0 z-[200] flex items-center justify-center p-4 bg-text-primary/35 backdrop-blur-sm"
      onClick={onClose}
    >
      <div
        className="fe-panel fe-dialog-panel w-full max-w-md max-h-[calc(100dvh-2rem)] overflow-y-auto rounded-2xl shadow-2xl p-6"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
      >
        <div className="flex items-start justify-between gap-3 mb-4">
          <div className="flex items-center gap-3">
            <div className="flex items-center justify-center w-10 h-10 rounded-xl bg-champagne/15">
              <Sparkles className="w-5 h-5 text-champagne" />
            </div>
            <h2 className="text-lg font-display font-bold text-text-primary">{t('compare.upsellTitle')}</h2>
          </div>
          <button type="button" onClick={onClose} className="flex min-h-11 min-w-11 items-center justify-center rounded-lg p-1 text-text-tertiary hover:text-text-primary" aria-label={t('common.close')}>
            <X className="w-5 h-5" />
          </button>
        </div>
        <p className="text-sm text-text-secondary leading-relaxed mb-5">
          {t('compare.upsellBody')}
        </p>
        <div className="flex items-center gap-3">
          <Link to="/register" onClick={onClose} className="fe-button-primary flex-1 text-center rounded-xl text-sm font-semibold py-2.5">
            {t('compare.upsellRegister')}
          </Link>
          <Link to="/login" onClick={onClose} className="flex-1 text-center rounded-xl text-text-primary text-sm font-medium py-2.5 transition-colors fe-glass-2">
            {t('common.login')}
          </Link>
        </div>
      </div>
    </div>
  );
}

function CompareTooltip({
  active, payload, label, dateFormat = 'short', colors = null,
}) {
  if (!active || !payload?.length) return null;
  const rows = compareTooltipRows(payload, colors);
  if (!rows.length) return null;
  return (
    <div className="glass-surface min-w-[200px] max-w-[calc(100vw-48px)] rounded-xl px-4 py-3 shadow-2xl">
      <p className="mb-2 text-xs text-text-secondary">{formatDate(label, dateFormat)}</p>
      {rows.map((p) => (
        <div key={p.dataKey} className="mb-1 flex items-center justify-between gap-4">
          <div className="flex min-w-0 items-center gap-2">
            <span className="h-2 w-2 shrink-0 rounded-full" style={{ backgroundColor: colors?.[p.dataKey] || p.color }} />
            <span className="max-w-[160px] truncate text-xs text-text-secondary">{p.name}</span>
          </div>
          <span className="shrink-0 whitespace-nowrap text-sm font-semibold tabular-nums text-text-primary">
            {formatValueWithUnit(p.value, p.payload?.[`${p.dataKey}_unit`] || '%').replace(/ (?=[^\s]+$)/, '\u00A0')}
          </span>
        </div>
      ))}
    </div>
  );
}

export default function ComparePage() {
  const t = useT();
  const glass = useChartGlassIds('k5c');
  const { locale } = useLocale();
  const [searchParams, setSearchParams] = useSearchParams();
  const [range, setRange] = useState(DEFAULT_RANGE);
  // Свой период, выбранный ручками под графиком: длина окна в точках (range === 'custom').
  const [customLen, setCustomLen] = useState(0);
  const [scale, setScale] = useState('values');
  // Человек сам выбрал «Значения» или «Проценты»: автоматика больше не переключает.
  const [scaleChosen, setScaleChosen] = useState(false);
  const [step, setStep] = useState('auto');
  const [compatibilityMessage, setCompatibilityMessage] = useState('');
  // Подсказка после добавления: что произошло и что делать дальше.
  const [status, setStatus] = useState('');
  const [pickerOpen, setPickerOpen] = useState(false);
  const coarsePointer = useMediaQuery('(pointer: coarse)');
  // Панорама окна: сдвиг в точках от правого края ряда («кружочек» как на
  // карточке индикатора — созвон «На правки 13»).
  const [panOffset, setPanOffset] = useState(0);
  const [upsellOpen, setUpsellOpen] = useState(false);
  const [isDragging, setIsDragging] = useState(false);
  const exportRef = useRef(null);
  const chartAreaRef = useRef(null);
  const [setPlotNode, plotWidth] = useElementWidth();
  const [setSectionNode, sectionWidth] = useElementWidth();
  const touchTip = useTouchTooltip(chartAreaRef);
  const setChartArea = useCallback((node) => {
    chartAreaRef.current = node;
    setPlotNode(node);
  }, [setPlotNode]);
  const dragRef = useRef(null);

  const { isAuthed, isLoading: isAuthLoading } = useAuth();
  const cap = isAuthed ? USER_MAX : GUEST_MAX;
  // Гость никогда не рендерит/экспортирует больше двух рядов — даже если коды
  // переданы напрямую в URL.
  // Без `codes` в адресе страница открывается готовым живым сравнением, а не пустой анкетой.
  const isDemo = !searchParams.has('codes') && !searchParams.has('a') && !searchParams.has('b');
  const allCodes = useMemo(
    () => (isDemo ? DEFAULT_COMPARE_PRESET.codes : parseCodes(searchParams)),
    [isDemo, searchParams],
  );
  const { data: worldCompareCatalog, isLoading: worldCatalogLoading } = useWorldCompareCatalog();
  const worldCompareItems = useMemo(() => worldCompareCatalog?.items || [], [worldCompareCatalog]);
  const worldCodeSet = useMemo(() => new Set(worldCompareItems.map((item) => item.code)), [worldCompareItems]);
  const hasWorldCode = useCallback((code) => worldCodeSet.has(code), [worldCodeSet]);
  // Круг 10 (Ср1): набор из адреса приводим к сопоставимому, и порядок кодов не важен: российский показатель с двойником
  // в общем наборе стран (ВВП, инфляция…) становится двойником, пока каталог не загрузился, считаем двойника существующим.
  const compatibleCodes = useMemo(
    () => normalizeCompareCodes(allCodes, worldCodeSet.size ? hasWorldCode : () => true),
    [allCodes, worldCodeSet, hasWorldCode],
  );
  const codes = useMemo(
    () => (isAuthed ? compatibleCodes : compatibleCodes.slice(0, GUEST_MAX)),
    [compatibleCodes, isAuthed],
  );

  const compareSeo = getPageSeo('compare', locale);
  useDocumentMeta({
    title: compareSeo.title,
    description: compareSeo.description,
    path: compareSeo.path,
  });

  useEffect(() => {
    // Готовый пример (без выбора в адресе) в аналитику не пишем как выбор человека.
    track(events.COMPARE_OPEN, { count: isDemo ? 0 : codes.length, codes: isDemo ? null : (codes.join(',') || null), demo: isDemo });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useScrollDepth({ key: 'compare', page: 'compare' });

  // Смена набора рядов → окно к свежим данным.
  useEffect(() => { setPanOffset(0); }, [codes]);

  const { data: indicators, isFetched: indicatorsFetched } = useIndicators();
  // Карточки вне витрины (дизель, АИ-95 и подобные) приходят из общего поиска и
  // по прямой ссылке. Полный список нужен только для них, поэтому запрашивается
  // лишь когда выбранного кода нет в витрине.
  const needsUnlisted = indicatorsFetched && codes.some((code) =>
    !isWorldCode(code) && !isRegionCode(code) && !isSubnationalCode(code)
    && !indicators?.some((item) => item.code === code));
  const { data: unlistedIndicators, isFetched: unlistedFetched } = useIndicators({
    includeUnlisted: true, enabled: needsUnlisted,
  });
  const hasWorldSeries = codes.some(isWorldCode);
  const dataSpacesCount = [
    codes.some((code) => isWorldCode(code) || isSubnationalCode(code)),
    codes.some(isRegionCode),
    codes.some((code) => !isWorldCode(code) && !isRegionCode(code) && !isSubnationalCode(code)),
  ].filter(Boolean).length;
  const compatibilityNote = activeCompatibilityNote(codes);
  const worldMetaByCode = useMemo(
    () => new Map((worldCompareCatalog?.items || []).map((item) => [item.code, {
      frequency: item.frequency,
      conceptSlug: item.concept_slug,
      unit: item.unit,
      peerMode: item.peer_mode,
    }])),
    [worldCompareCatalog],
  );

  // Название мировой серии известно из каталога сразу после выбора — до прихода данных.
  const worldNameByCode = useMemo(() => new Map((worldCompareCatalog?.items || []).map((item) => {
    const concept = locale === 'en' ? (item.concept_name_en || item.concept_name) : item.concept_name;
    const country = locale === 'en' ? (item.country_name_en || item.country_name) : item.country_name;
    return [item.code, country ? `${concept} — ${country}` : concept];
  })), [worldCompareCatalog, locale]);

  useEffect(() => {
    if (hasWorldSeries && step !== 'auto') setStep('auto');
  }, [hasWorldSeries, step]);

  const repByCode = useMemo(
    () => (isDemo ? DEFAULT_COMPARE_PRESET.reps : parseReps(searchParams)),
    [isDemo, searchParams],
  );

  const writeCodes = useCallback((next) => {
    const params = new URLSearchParams(searchParams);
    params.delete('a');
    params.delete('b');
    // Пустой `codes=` отличает «убрал всё» от «пришёл без выбора» (там показывается готовый пример).
    params.set('codes', next.join(','));
    // Убираем rep-записи удалённых кодов, чтобы URL не тащил мусор.
    const rawRep = params.get('rep');
    if (rawRep) {
      const kept = rawRep.split(',').filter((pair) => {
        const separator = pair.lastIndexOf(':');
        return separator > 0 && next.includes(pair.slice(0, separator));
      });
      if (kept.length) params.set('rep', kept.join(','));
      else params.delete('rep');
    }
    setSearchParams(params, { replace: true });
  }, [searchParams, setSearchParams]);

  const setRep = useCallback((code, rep) => {
    const params = new URLSearchParams(searchParams);
    const nextMap = { ...repByCode, [code]: rep };
    const entries = Object.entries(nextMap).filter(([, r]) => r && r !== REP_LEVEL);
    if (entries.length) params.set('rep', entries.map(([c, r]) => `${c}:${r}`).join(','));
    else params.delete('rep');
    setSearchParams(params, { replace: true });
    track(events.COMPARE_CHANGE, { code, rep });
  }, [searchParams, setSearchParams, repByCode]);

  // Короткое имя ряда для подсказки «… добавлен на график».
  const shortNameForCode = useCallback((code) => {
    const parsed = parseWorldCompareCode(code);
    if (parsed) {
      const item = worldCompareItems.find((it) => it.code === code);
      if (!item) return '';
      const concept = conceptShortLabel(
        item.concept_slug,
        locale === 'en' ? (item.concept_name_en || item.concept_name) : item.concept_name,
        t,
      );
      const country = locale === 'en' ? (item.country_name_en || item.country_name) : item.country_name;
      return country ? `${concept}, ${country}` : concept;
    }
    return indicators?.find((item) => item.code === code)?.name || '';
  }, [worldCompareItems, indicators, locale, t]);

  const addCode = useCallback((code) => {
    // Из готового примера «с нуля» не добавляем: пример только показ, выбор начинается пустым.
    const current = isDemo ? [] : codes;
    if (current.includes(code)) return;
    if (current.length >= cap) {
      if (!isAuthed) {
        track(events.COMPARE_LIMIT_HIT, { count: current.length });
        setUpsellOpen(true);
      }
      return;
    }
    const compatibility = compareCompatibilityWithTwins(current, code, hasWorldCode);
    if (!compatibility.allowed) {
      setCompatibilityMessage(compatText(t, compatibility) || '');
      return;
    }
    setCompatibilityMessage('');
    // Российский показатель заменён своим «двойником» в общем наборе стран: так он сравним с рядом другой страны.
    // Это работает в обе стороны: уже выбранный заменяется (`replaceWith`), добавляемый заменяется на двойника (`addCode`).
    const added = compatibility.addCode || code;
    const next = [...(compatibility.replaceWith || current), added];
    writeCodes(next);
    const name = shortNameForCode(added) || t('z2.compare.seriesFallback');
    const statusKey = compatibility.swapNoteKey
      || (next.length >= cap && !isAuthed ? 'w6g.compare.addedLimit' : 'w6g.compare.added');
    setStatus(t(statusKey, { name }));
    // Круг 9 (C3): после второго ряда выбор сворачивается, и график виден сразу, а не через два экрана.
    setPickerOpen(next.length < 2 && next.length < cap);
    track(events.COMPARE_ADD, { code: added, count: next.length });
    // График остаётся ниже выбора: подкручиваем к нему на любом экране, если он не в поле зрения.
    window.setTimeout(scrollToCompareChart, 140);
  }, [codes, isDemo, cap, isAuthed, writeCodes, t, shortNameForCode, hasWorldCode]);

  // Что можно добавить к уже выбранному: решение одно и то же для списка стран, списка показателей и самого добавления.
  const compatibilityFor = useCallback(
    (code) => compareCompatibilityWithTwins(isDemo ? [] : codes, code, hasWorldCode),
    [isDemo, codes, hasWorldCode],
  );

  // «Начать заново»: убрать все ряды и открыть выбор (гость упёрся в лимит или набор не сочетается).
  const clearAll = useCallback(() => {
    writeCodes([]);
    setStatus('');
    setCompatibilityMessage('');
    setPickerOpen(true);
    track(events.COMPARE_CHANGE, { cleared: true });
  }, [writeCodes]);

  const removeCode = useCallback((code) => {
    writeCodes(codes.filter((c) => c !== code));
    setStatus('');
    track(events.COMPARE_CHANGE, { removed: code });
  }, [codes, writeCodes]);

  // Готовый набор одним нажатием: график строится сразу.
  const applyPreset = useCallback((preset) => {
    setSearchParams(presetParams(preset, searchParams), { replace: true });
    setStatus('');
    setCompatibilityMessage('');
    track(events.COMPARE_CHANGE, { preset: preset.id });
  }, [searchParams, setSearchParams]);

  // «Изменить» на готовом примере: пример становится рабочим сравнением, выбор раскрывается.
  const startEditing = useCallback(() => {
    if (isDemo) setSearchParams(presetParams(DEFAULT_COMPARE_PRESET, searchParams), { replace: true });
    setPickerOpen(true);
  }, [isDemo, searchParams, setSearchParams]);

  // Резолв (индикатор, представление) → {код ряда для загрузки, transform, unit}.
  // Так каждый ряд грузится в выбранном виде (уровень/к пред./к году), а не в
  // нативном. Резолвер (compareRepresentation.js) знает generic-семьи и bespoke.
  const resolved = useMemo(() => codes.map((code) => {
    if (isWorldCode(code)) {
      const meta = worldMetaByCode.get(code);
      // Индекс цен уровнем рядом с рядом в процентах за год сразу показываем в процентах (круг 9, C1).
      const requestedRep = repByCode[code] || defaultWorldRepresentation(
        meta,
        codes.filter((other) => other !== code).map((other) => worldMetaByCode.get(other)),
      );
      const options = worldCompareRepresentationsFor(meta);
      const repId = options.some((item) => item.id === requestedRep)
        ? requestedRep
        : REP_LEVEL;
      return {
        code, ind: null, repId,
        repLabel: options.find((item) => item.id === repId)?.label || t('common.value'),
        fetchCode: code,
        transform: worldCompareTransformFor(repId, meta?.frequency),
        unit: repId === REP_LEVEL ? meta?.unit : '%',
        isWorld: true,
      };
    }
    // Региональный ряд (`r:{slug}:{code}`) и субнациональный (`s:{страна}:{slug}:{code}`):
    // уровень без представлений, метаданные приходят вместе с данными.
    if (isRegionCode(code) || isSubnationalCode(code)) {
      return {
        code, ind: null, repId: REP_LEVEL, repLabel: t('common.value'),
        fetchCode: code, transform: null, unit: null,
        isRegion: isRegionCode(code),
        isSubnational: isSubnationalCode(code),
      };
    }
    const ind = indicators?.find((x) => x.code === code)
      || unlistedIndicators?.find((x) => x.code === code);
    if (!indicatorsFetched || (!ind && needsUnlisted && !unlistedFetched)) {
      return {
        code, ind: null, repId: REP_LEVEL, repLabel: t('common.value'),
        fetchCode: null, transform: null, unit: null, waitingCatalog: true,
      };
    }
    if (!ind) {
      return {
        code, ind: null, repId: REP_LEVEL, repLabel: t('common.value'),
        fetchCode: null, transform: null, unit: null, unknown: true,
      };
    }
    const repId = repByCode[code] || REP_LEVEL;
    const spec = resolveCompareSeries(ind || { code }, repId)
      || { code, transform: null, unit: ind?.unit, repId: REP_LEVEL, label: t('common.value') };
    // Третий слой (compareRepresentation.js::resolveStepOverride): «Шаг»
    // переключает на реальный более глубокий ряд вместо клиентского
    // усреднения, если он есть у показателя на этой частоте.
    const stepAlt = resolveStepOverride(ind, spec.repId, step);
    return {
      code, ind, repId: spec.repId, repLabel: spec.label,
      fetchCode: stepAlt || spec.code, transform: stepAlt ? null : spec.transform,
      unit: spec.unit, stepDeep: !!stepAlt,
    };
  }), [codes, indicators, indicatorsFetched, needsUnlisted, unlistedIndicators, unlistedFetched, repByCode, step, worldMetaByCode, t]);

  const results = useQueries({
    queries: resolved.map((r) => ({
      queryKey: ['indicator-data', r.fetchCode, undefined],
      queryFn: ({ signal }) => (r.isWorld
        ? fetchWorldSeries(r.fetchCode, { signal })
        : r.isSubnational
        ? fetchSubnationalSeries(r.fetchCode, { signal })
        : r.isRegion
        ? fetchRegionSeries(r.fetchCode, { signal })
        : fetchIndicatorData(r.fetchCode, undefined, { signal })),
      enabled: !!r.fetchCode,
      retry: (count, err) => {
        const status = err?.response?.status;
        if (status && status >= 400 && status < 500 && status !== 429) return false;
        return count < 1;
      },
      staleTime: 60 * 60 * 1000,
      gcTime: 30 * 60 * 1000,
    })),
  });

  const series = useMemo(() => resolved.map((r, i) => {
    const known = r.isWorld
      ? (results[i]?.data?.__worldMeta?.name || worldNameByCode.get(r.code))
      : (r.isRegion || r.isSubnational) ? results[i]?.data?.__regionMeta?.name : r.ind?.name;
    return {
    code: r.code,
    // Внутренний код никогда не показываем: пока название не пришло — null (скелетон).
    name: known || null,
    key: `v${i}`,
    color: PALETTE[i % PALETTE.length],
    ind: r.isWorld
      ? results[i]?.data?.__worldMeta
      : (r.isRegion || r.isSubnational) ? results[i]?.data?.__regionMeta : r.ind,
    rep: r.repId,
    repLabel: r.repLabel,
    unit: r.isWorld
      ? (r.repId === REP_LEVEL ? results[i]?.data?.__worldMeta?.unit : r.unit)
      : (r.isRegion || r.isSubnational) ? results[i]?.data?.__regionMeta?.unit : r.unit,
    isWorld: r.isWorld,
    isSubnational: r.isSubnational,
    transform: r.transform,
    stepDeep: r.stepDeep,
    data: results[i]?.data,
    loading: results[i]?.isLoading || r.waitingCatalog,
    error: results[i]?.isError || r.unknown,
    };
  }), [resolved, results, worldNameByCode]);

  // Разные единицы измерения рядов (после резолва представления). Максимум две
  // оси — при 3+ различных единицах корректно показать нельзя, форсим индекс.
  const distinctUnits = useMemo(() => {
    const seen = [];
    series.forEach((s) => { const u = s.unit || '%'; if (!seen.includes(u)) seen.push(u); });
    return seen;
  }, [series]);
  const mixedPriceIndexBases = requiresRebasedPriceIndex(series);
  const forceIndex = distinctUnits.length > 2 || mixedPriceIndexBases;
  // Ряды в одной единице, но разного размера (США и Австрия): на общей оси меньший кажется ровным.
  // Тогда сразу показываем рост в процентах от начала периода и оставляем кнопку «Показать значения».
  const autoIndex = useMemo(() => {
    if (scaleChosen || scale !== 'values' || forceIndex || series.length < 2) return false;
    if (distinctUnits.length !== 1 || !isAbsoluteUnit(distinctUnits[0])) return false;
    if (series.some((s) => s.loading || s.error || s.rep !== REP_LEVEL || s.transform)) return false;
    const levels = series.map((s) => (Array.isArray(s.data?.data) ? s.data.data : []));
    if (levels.some((points) => !points.length)) return false;
    return scalesDiffer(levels[0], levels.slice(1).map((data) => ({ data })));
  }, [scaleChosen, scale, forceIndex, series, distinctUnits]);
  const indexed = forceIndex || scale === 'index' || autoIndex;

  const chartData = useMemo(() => {
    const EMPTY = {
      rows: [], nonIndexableNames: [], nonIndexableKeys: new Set(), maxPan: 0, baseDate: null, noSharedBase: false,
      brushRows: [], windowStart: 0, windowEnd: 0,
    };
    if (!series.length) return EMPTY;
    const maps = series.map((s) => {
      const raw = Array.isArray(s.data?.data) ? s.data.data : [];
      const transformed = applyCompareTransform(raw, s.transform);
      // stepDeep: данные уже загружены на нативной частоте нужного шага
      // (реальный alternate_frequencies ряд) — повторная клиентская
      // агрегация не нужна и исказила бы уже готовые годовые/квартальные точки.
      const pts = s.stepDeep || s.isWorld || s.isSubnational ? transformed : aggregateToStep(transformed, step);
      return new Map(pts.map((p) => [p.date, p.value]));
    });

    const allDates = [...new Set(maps.flatMap((m) => [...m.keys()]))].sort();
    if (!allDates.length) return EMPTY;

    // Окно: длина — из пресета периода, позиция — из слайдера-панорамы.
    const rangeOpt = RANGE_OPTIONS.find((r) => r.key === range);
    let windowLen = allDates.length;
    if (range === 'custom' && customLen > 0) {
      windowLen = Math.min(allDates.length, customLen);
    } else if (rangeOpt?.months) {
      const cutoff = new Date(allDates[allDates.length - 1]);
      cutoff.setUTCMonth(cutoff.getUTCMonth() - rangeOpt.months);
      const cutoffStr = cutoff.toISOString().slice(0, 10);
      windowLen = allDates.filter((d) => d >= cutoffStr).length || allDates.length;
    }
    const maxPan = Math.max(0, allDates.length - windowLen);
    const pan = Math.min(Math.max(0, panOffset), maxPan);
    const endIdx = allDates.length - pan;
    const startIdx = Math.max(0, endIdx - windowLen);

    const dates = allDates.slice(startIdx, endIdx);
    // Уменьшенная копия первого ряда по всей истории: на ней стоят ручки периода.
    const brushRows = allDates.map((d) => ({ date: d, actual: maps[0]?.get(d) ?? null }));

    // К общей базе (=100) приводится ТОЛЬКО положительный уровень. Знакопеременные
    // ряды (сальдо, счёт текущих операций, дефицит), %-ряды и представления
    // «к прошлому периоду»/«к году» (это темпы, не уровни — В-12) к базе-100 не
    // приводятся: деление на ~0 → выброс, отрицательная база → переворот знака,
    // «инфляция 5% = 100 пунктов» — смысловой мусор. Такие ряды в режиме общей
    // базы исключаем и подписываем, а не рисуем.
    const { date: baseDate, candidates, bases } = indexed
      ? commonIndexBase(maps, series, dates)
      : { date: null, candidates: [], bases: [] };
    const indexable = series.map((_, i) => candidates.includes(i));
    const nonIndexableNames = indexed
      ? series.filter((_, i) => !indexable[i]).map((s) => s.name || t('z2.compare.seriesFallback'))
      : [];
    const nonIndexableKeys = new Set(
      indexed ? series.filter((_, i) => !indexable[i]).map((s) => s.key) : [],
    );
    if (indexed && !baseDate) {
      return {
        ...EMPTY, nonIndexableNames, nonIndexableKeys, maxPan, noSharedBase: candidates.length > 0,
      };
    }
    const idxUnit = t('compare.indexUnit');

    // В-13 (CTO-аудит 2026-07-06): значение пишется в строку ТОЛЬКО на датах,
    // где у ряда есть реальная точка. Раньше carry-forward (LOCF) протягивал
    // последнее значение через даты без данных: тултип показывал «значение»
    // там, где наблюдения нет, а линия шла ступенькой. Разрывы между точками
    // соединяет connectNulls на <Line> — честная интерполяция между фактами.
    const visibleDates = indexed ? dates.filter((date) => date >= baseDate) : dates;
    const rows = visibleDates.map((d) => {
      const row = { date: d };
      maps.forEach((m, i) => {
        if (!m.has(d)) return;
        const v = m.get(d);
        const s = series[i];
        if (indexed) {
          if (indexable[i]) { row[s.key] = rebaseToHundred(v, bases[i]); row[`${s.key}_unit`] = idxUnit; }
        } else {
          row[s.key] = v;
          row[`${s.key}_unit`] = s.unit || '%';
        }
      });
      return row;
    });
    return {
      rows, nonIndexableNames, nonIndexableKeys, maxPan, baseDate, noSharedBase: false,
      brushRows, windowStart: startIdx, windowEnd: endIdx,
    };
  }, [series, range, customLen, indexed, step, panOffset, t]);

  const chartRows = chartData.rows;
  const {
    nonIndexableNames, nonIndexableKeys, maxPan, baseDate, noSharedBase, brushRows, windowStart, windowEnd,
  } = chartData;
  const analysisSummary = useMemo(() => {
    const metrics = series.map((item) => {
      const points = chartRows
        .filter((row) => Number.isFinite(Number(row[item.key])))
        .map((row) => ({ date: row.date, value: Number(row[item.key]) }));
      if (!points.length) return { item, points: [], first: null, last: null };
      const first = points[0];
      const last = points[points.length - 1];
      return {
        item,
        points,
        first,
        last,
        minimum: Math.min(...points.map((point) => point.value)),
        maximum: Math.max(...points.map((point) => point.value)),
        change: last.value - first.value,
      };
    });
    const base = metrics[0];
    const correlations = base?.points?.length
      ? metrics.slice(1).map((metric) => {
          const byDate = new Map(metric.points.map((point) => [point.date, point.value]));
          const pairs = base.points
            .filter((point) => byDate.has(point.date))
            .map((point) => [point.value, byDate.get(point.date)]);
          return {
            item: metric.item,
            value: pearsonCorrelation(pairs),
            observations: pairs.length,
          };
        }).filter((result) => result.value != null)
      : [];
    return { metrics, correlations, base: base?.item || null };
  }, [chartRows, series]);
  const hasData = chartRows.length > 0;
  const loading = series.some((s) => s.loading);
  const loadFailed = series.some((s) => s.error);
  const hasError = series.some((s) => s.error);
  // Повтор — только для сетевых сбоев (запрос упал); неизвестный код в адресе повторять бессмысленно.
  const failedQueries = results.filter((r) => r.isError);
  const retrying = failedQueries.some((r) => r.isFetching);
  const retryFailed = () => { failedQueries.forEach((r) => r.refetch()); };
  // Широкий график не выше ~половины экрана: на ноутбуке 1280x720 он целиком в первом экране, на высоких мониторах 480 px.
  const viewportHeight = useViewportHeight();
  const baseChartHeight = chartHeightForWidth(sectionWidth);
  const chartHeight = baseChartHeight >= 480 && viewportHeight > 0
    ? Math.min(baseChartHeight, Math.max(360, Math.round(viewportHeight * 0.52)))
    : baseChartHeight;
  const narrow = plotWidth > 0 && plotWidth < NARROW_CHART_WIDTH;
  // Формат дат оси: агрегированный шаг диктует гранулярность, иначе — частоты рядов.
  const compareDateFmt = step === 'year'
    ? 'annual'
    : step === 'quarter'
      ? 'quarterly'
      : step === 'month'
        ? 'short'
        : compareDateFormat(series.map((s) => s.ind));

  // Подписи оси X: бюджет от ширины + formatChartAxisDate (как tickFormatter).
  const xTicks = useMemo(() => {
    const axisW = Math.max(0, plotWidth - 80);
    const formatLabel = (d) => formatChartAxisDate(d, compareDateFmt, { multiYear: true });
    const sample = chartRows[0]?.date ?? chartRows[chartRows.length - 1]?.date;
    const labelSpec = sample != null
      ? formatLabel(sample)
      : (compareDateFmt === 'annual' ? 4 : compareDateFmt === 'quarterly' ? 10 : 8);
    const cadence = compareDateFmt === 'annual' || compareDateFmt === 'quarterly'
      ? compareDateFmt
      : null;
    // Круг 9 (C4): подпись оси считаем по 7,4 px на знак и берём ширину с запасом 12 %, чтобы соседние подписи
    // («июн 2022» и «ноя 2022») не слипались; при самой узкой оси остаётся одна подпись.
    const sampleChars = typeof labelSpec === 'string' ? labelSpec.length : Number(labelSpec) || 8;
    const budget = chartAxisTickBudget(axisW * 0.88, Math.max(41, Math.ceil(sampleChars * 7.4) + 8));
    return pickChartAxisTicks(
      chartRows,
      axisW < 180 ? 2 : budget,
      { cadence, plotWidthPx: axisW * 0.88, formatLabel },
    );
  }, [chartRows, plotWidth, compareDateFmt]);

  // Оси: индекс → одна левая. Значения → группировка по единице: первая
  // единица слева, вторая справа (ряды одной единицы делят общую ось).
  const axisFor = (i) => {
    if (indexed) return 'left';
    const u = series[i]?.unit || '%';
    return distinctUnits[0] === u ? 'left' : 'right';
  };
  // Короткая подпись легенды: без повтора «Значение», длинных единиц и «шкала слева»
  // при одной оси — единицы видны на оси и в сводке ниже.
  const legendDetail = (s, i, dropped) => {
    const parts = [];
    if (s.rep && s.rep !== REP_LEVEL) parts.push(s.repLabel);
    if (dropped) parts.push(t('compare.notRebased'));
    else if (indexed) parts.push(t('compare.start100'));
    else {
      const short = splitUnit(s.unit).short;
      if (short && short.length <= 14) parts.push(unitLabel(short));
      // Частота — только если у рядов она разная: иначе это лишнее слово в каждой подписи.
      if (new Set(series.map((x) => x.ind?.frequency).filter(Boolean)).size > 1 && s.ind?.frequency) {
        parts.push(freqLabel(s.ind.frequency, t));
      }
      if (distinctUnits.length > 1) parts.push(axisFor(i) === 'left' ? t('compare.axisLeft') : t('compare.axisRight'));
    }
    const text = compareLegendParts(parts);
    return text ? `(${text})` : '';
  };
  const leftUnit = distinctUnits[0];
  const rightUnit = distinctUnits[1];
  // Ширина оси Y — по самой длинной подписи: фиксированные 46–60 px резали левую цифру
  // («355 000» читалось как «55 000»).
  const axisValues = (id) => {
    const vals = [];
    series.forEach((s, i) => {
      if (axisFor(i) !== id) return;
      chartRows.forEach((r) => { if (r[s.key] != null) vals.push(r[s.key]); });
    });
    return vals;
  };
  // Ровный шаг оси (1/2/5 × 10^k) вместо автодомена с шагом вроде 55 000.
  const axisScales = {
    left: niceAxis(axisValues('left'), narrow ? 4 : 5),
    right: niceAxis(axisValues('right'), narrow ? 4 : 5),
  };
  const { headline: chartHeadline, labels } = compareLabels(series, {
    t, locale, fallback: t('z2.compare.seriesFallback'),
  });
  // Подписи осей крупнее: 12 px на узком графике, 13 px на широком (раньше 11 px).
  const axisFontSize = narrow ? 12 : 13;
  const axisWidths = (() => {
    const calc = (id, unit) => {
      const vals = axisValues(id);
      const digits = indexed ? 0 : unitDigits(unit);
      return axisWidthForLabels(
        axisSampleValues(vals).map((v) => formatAxisTick(v, digits)),
        { min: narrow ? 42 : 52, perChar: narrow ? 7.4 : 8, pad: 12 },
      );
    };
    return { left: calc('left', leftUnit), right: calc('right', rightUnit) };
  })();

  // Подписи концов линий («США 30 767») вместо легенды: только на широком графике и при одной оси.
  const xAxisHeight = narrow ? 28 : 32;
  const showEndLabels = !narrow && plotWidth >= 560 && distinctUnits.length === 1
    && series.length > 0 && chartRows.length > 0 && !!axisScales.left;
  const endLabelWidth = plotWidth >= 900 ? 136 : 116;
  const chartMarginRight = showEndLabels ? endLabelWidth : (narrow ? 14 : 24);
  const endLabels = (() => {
    if (!showEndLabels) return [];
    const plotTop = 10;
    const plotHeight = chartHeight - plotTop - 4 - xAxisHeight;
    const raw = [];
    series.forEach((s, i) => {
      for (let r = chartRows.length - 1; r >= 0; r -= 1) {
        const v = chartRows[r][s.key];
        if (v == null || !Number.isFinite(Number(v))) continue;
        const y = yForValue(v, axisScales.left.domain, { top: plotTop, plotHeight });
        if (y != null) {
          raw.push({
            key: s.key, y, color: s.color, value: v, flag: seriesFlag(s),
            name: compareEndName(labels[i] || t('z2.compare.seriesFallback'), endLabelWidth >= 136 ? 26 : 22),
          });
        }
        break;
      }
    });
    const placed = spreadLabels(raw, { min: 17, max: plotTop + plotHeight + 6, gap: 38 });
    return raw.map((item) => ({
      ...item,
      top: placed[item.key] - 17,
      text: formatEndValue(item.value, { unit: leftUnit, locale, indexed }),
    }));
  })();
  // Легенду прячем (оставляем для скринридера), когда подписи концов уже всё сказали.
  const legendNeeded = !showEndLabels
    || nonIndexableNames.length > 0
    || series.some((s) => s.rep && s.rep !== REP_LEVEL)
    || new Set(series.map((x) => x.ind?.frequency).filter(Boolean)).size > 1;
  // Единицы одной фразой над графиком: «Значения, млрд $».
  const unitsCaption = (() => {
    if (indexed || distinctUnits.length !== 1) return '';
    const unit = splitUnit(distinctUnits[0]).short || distinctUnits[0];
    return unit && unit !== '%' ? t('z7.compare.valuesIn', { unit: unitLabel(unit) }) : '';
  })();
  // Разрыв двух величин словами: «США больше, чем Китай, в 1,6 раза».
  const gap = (() => {
    if (indexed || series.length !== 2 || distinctUnits.length !== 1 || !isAbsoluteUnit(distinctUnits[0])) return null;
    if (series.some((s) => s.rep !== REP_LEVEL)) return null;
    const lasts = analysisSummary.metrics.map((m) => m.last?.value);
    if (lasts.some((v) => v == null)) return null;
    return gapInsight(series.map((s, i) => ({ label: labels[i], value: lasts[i] })), locale);
  })();

  // Перетаскивание графика мышью/пальцем — как на карточке индикатора.
  // Тащим вправо → окно уходит в прошлое (panOffset растёт), влево → к свежим.
  const handlePointerDown = useCallback((e) => {
    // Круг 8 (C3): пальцем график не двигает период, а показывает подсказку; период двигают ручки под графиком.
    if (e.pointerType === 'touch') return;
    if (maxPan <= 0) return;
    const rect = chartAreaRef.current?.getBoundingClientRect();
    if (!rect) return;
    dragRef.current = {
      startX: e.clientX,
      startY: e.clientY,
      initPan: Math.min(panOffset, maxPan),
      chartWidth: rect.width,
      phase: 'deciding',
    };
  }, [maxPan, panOffset]);

  const handlePointerMove = useCallback((e) => {
    let d = dragRef.current;
    if (!d) return;
    if (d.phase === 'deciding') {
      const dx = e.clientX - d.startX;
      const dy = e.clientY - d.startY;
      if (Math.hypot(dx, dy) < 8) return;
      if (Math.abs(dy) >= Math.abs(dx)) { dragRef.current = null; return; }
      d.phase = 'dragging';
      try { e.currentTarget.setPointerCapture(e.pointerId); } catch { /* ok */ }
      setIsDragging(true);
    }
    d = dragRef.current;
    if (!d || d.phase !== 'dragging') return;
    const windowLen = chartRows.length || 1;
    const pixelsPerPoint = d.chartWidth / windowLen;
    const shift = Math.round((e.clientX - d.startX) / pixelsPerPoint);
    setPanOffset(Math.max(0, Math.min(d.initPan + shift, maxPan)));
  }, [chartRows.length, maxPan]);

  const handlePointerUp = useCallback((e) => {
    const d = dragRef.current;
    if (d?.phase === 'dragging') {
      try { e.currentTarget.releasePointerCapture(e.pointerId); } catch { /* ok */ }
    }
    dragRef.current = null;
    setIsDragging(false);
  }, []);

  // Скачивание картинки сравнения — только для зарегистрированных, без
  // watermark (правило 2026-07-08, единое по сайту — см.
  // IndicatorChartSection.jsx); до этой правки гость мог скачать сравнение
  // без входа.
  const handleExport = async () => {
    if (!hasData) return;
    if (!isAuthed) {
      track(events.COMPARE_IMAGE_BLOCKED, { count: codes.length });
      window.dispatchEvent(new CustomEvent('fe:download-limit'));
      return;
    }
    const ok = await exportNodeToPng(exportRef.current, {
      filename: `compare_${codes.join('-').replace(/:/g, '_') || 'chart'}.png`,
      watermark: false,
    }).catch(() => false);
    if (ok) {
      track(events.COMPARE_IMAGE_DOWNLOAD, { count: codes.length, watermark: false, authed: isAuthed });
    } else {
      track(events.COMPARE_IMAGE_BLOCKED, { count: codes.length });
    }
  };

  const atCap = codes.length >= cap;
  const capHint = isAuthed
    ? t('z7.compare.capAuthedFix', { n: USER_MAX })
    : t('z7.compare.capGuestFix');
  const openLimit = () => {
    track(events.COMPARE_LIMIT_HIT, { count: codes.length });
    setUpsellOpen(true);
  };
  // Короткое имя ряда для плашек и сводки: «ВВП, текущие цены, США»; полное остаётся в подсказке.
  const shortSeriesName = (s) => (s.isWorld && s.ind?.countryName && s.ind?.conceptName
    ? `${conceptShortLabel(s.ind.conceptSlug, s.ind.conceptName, t)}, ${s.ind.countryName}`
    : s.name);
  const handleBrush = (start, end) => {
    setRange('custom');
    setCustomLen(end - start);
    setPanOffset(Math.max(0, brushRows.length - end));
  };
  const chooseScale = (key) => {
    setScale(key);
    setScaleChosen(true);
    track(events.COMPARE_RANGE, { scale: key });
  };
  const headline = series.length ? chartHeadline : t('compare.title');
  const showPicker = pickerOpen || (!isDemo && codes.length === 0);
  const activePreset = COMPARE_PRESETS.find((preset) => presetIsActive(preset, codes));
  // Подсказка красит точки сплошным цветом ряда: у лент первых двух рядов stroke — ссылка на градиент.
  const seriesColors = Object.fromEntries(series.map((s) => [s.key, s.color]));
  // Последняя точка каждого ряда в окне: сюда ставится бусина ленты.
  const endDots = [];
  series.forEach((s, i) => {
    for (let r = chartRows.length - 1; r >= 0; r -= 1) {
      const v = chartRows[r][s.key];
      if (v == null || !Number.isFinite(Number(v))) continue;
      endDots.push({
        key: s.key, index: i, x: chartRows[r].date, y: Number(v), color: s.color, axis: axisFor(i),
      });
      break;
    }
  });

  return (
    <div className="fe-data-page fe-compare-page pt-24 md:pt-28 pb-12 md:pb-16">
      <UpsellModal open={upsellOpen} onClose={() => setUpsellOpen(false)} />

      <div className="mb-3 md:mb-5 max-w-4xl">
        <Breadcrumbs items={toolTrail(t('compare.title'), comparePath())} className="mb-3 md:mb-4" />

        <h1 className="fe-compare-h1 text-[28px] md:text-[40px] font-display font-bold tracking-tight mb-1.5 md:mb-2 leading-[1.1]">
          {t('compare.title')}
        </h1>
        {/* На телефоне пояснение в одну строку, чтобы график был виден без прокрутки. */}
        <p className="max-w-2xl text-sm leading-snug text-text-secondary sm:hidden">
          {t('w7p.compare.subtitleShort')}
        </p>
        <p className="hidden max-w-2xl text-[15px] leading-snug text-text-secondary sm:block md:text-base">
          {t('w6g.compare.subtitle')}
        </p>
      </div>

      <section data-block="compare-add" className="mb-4 md:mb-6">
        {/* Готовые сравнения: один тап, и график уже построен. */}
        <div className="mb-2.5 md:mb-4" role="group" aria-label={t('w6g.compare.presetsAria')}>
          <div className="fe-scroll-row">
            {comparePresetsFor(locale).map((preset) => (
              <Chip
                key={preset.id}
                active={activePreset?.id === preset.id}
                onClick={() => applyPreset(preset)}
              >
                {t(preset.labelKey)}
              </Chip>
            ))}
            {!isDemo && codes.length > 0 && (
              <Chip onClick={clearAll} aria-pressed={undefined} data-testid="compare-clear">
                {t('c9d.compare.startOver')}
              </Chip>
            )}
          </div>
        </div>

        {isDemo && (
          <div className="fe-compare-demo mb-3 md:mb-4" data-testid="compare-demo">
            <p className="fe-compare-demo__text">
              <span className="sm:hidden">{t('w7p.compare.demoShort')}</span>
              <span className="hidden sm:inline">{t('w6g.compare.demoNote')}</span>
            </p>
            <Button variant="primary" size="sm" onClick={startEditing}>
              {t('w6g.compare.edit')}
            </Button>
          </div>
        )}

        {/* Гостю про лимит говорим только тогда, когда он упёрся в него (волна 6, 15.3), а не заранее. */}
        {!isDemo && (isAuthed || atCap) && (
          <p className="mt-3 text-[13px] leading-snug text-text-secondary" data-testid="compare-limit-note">
            {isAuthed
              ? t('compare.selectedAuthed', { n: codes.length, max: USER_MAX })
              : t('w6a.compare.guestLimit')}
            {!isAuthed && (
              <>
                {' '}
                <button type="button" onClick={() => { setUpsellOpen(true); track(events.REGISTER_NUDGE_EXPAND, { from: 'compare' }); }} className="relative inline font-medium text-champagne-ink hover:underline after:absolute after:-inset-x-2 after:-inset-y-3 after:content-['']">
                  {t('w6a.compare.register')}
                </button>
              </>
            )}
          </p>
        )}

        {!isDemo && codes.length > 0 && (
          <div className="fe-compare-picked mt-4">
            {series.map((s) => {
              const reps = s.isWorld
                ? worldCompareRepresentationsFor({
                    frequency: s.ind?.frequency,
                    conceptSlug: s.ind?.conceptSlug,
                  })
                : compareRepresentationsFor(s.ind || { code: s.code });
              return (
                <div
                  key={s.code}
                  className="fe-compare-picked__card"
                >
                  {/* Название и «×» — одна строка; варианты показа — отдельным рядом ниже, без пустоты справа. */}
                  <div className="flex items-start gap-2">
                    <span className="mt-1.5 h-2.5 w-2.5 shrink-0 rounded-full" style={{ backgroundColor: s.color }} />
                    <span title={s.name || undefined} className="min-w-0 flex-1 break-words text-sm leading-snug text-text-primary">{shortSeriesName(s) || (s.loading
                      ? <span className="block text-text-secondary" role="status" aria-busy="true">{t('compare.loadingSeries')}</span>
                      : t('z2.compare.seriesFallback'))}</span>
                    <button type="button" onClick={() => removeCode(s.code)} className="-my-1 -mr-1.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-lg text-text-secondary hover:text-text-primary pointer-coarse:h-11 pointer-coarse:w-11" aria-label={t('common.remove')}>
                      <X className="h-4 w-4" aria-hidden="true" />
                    </button>
                  </div>
                  {reps.length > 1 && (
                    <div className="fe-compare-reps mt-2 flex gap-1.5 pl-[1.125rem]">
                      {reps.map((o) => (
                        <Chip
                          key={o.id}
                          title={REP_HINT[o.id]}
                          active={s.rep === o.id}
                          onClick={() => setRep(s.code, o.id)}
                        >
                          {o.label}
                        </Chip>
                      ))}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}

        {dataSpacesCount > 1 && compatibilityNote && (
          <div className="mb-4 rounded-xl bg-champagne/[0.06] px-3.5 py-2.5 text-xs leading-relaxed text-text-secondary fe-shadow-2">
            {t(compatibilityNote)}
          </div>
        )}

        {/* Выбор свернулся после второго ряда: что именно добавлено (и что заменено) остаётся видно. */}
        {!showPicker && status && (
          <p role="status" data-testid="compare-status" className="mb-3 text-[13px] leading-snug text-champagne-ink">
            {status}
          </p>
        )}

        {!isDemo && codes.length > 0 && (
          <Button
            variant="secondary"
            aria-expanded={showPicker}
            onClick={() => setPickerOpen((open) => !open)}
            className="mb-4"
          >
            {showPicker ? <ChevronDown className="h-4 w-4 rotate-180" aria-hidden="true" /> : <Plus className="h-4 w-4" aria-hidden="true" />}
            {showPicker ? t('w6g.compare.hidePicker') : t('w6g.compare.addMore')}
          </Button>
        )}

        {showPicker && (
          <>
            <CompareSeriesPicker
              indicators={indicators}
              worldItems={worldCompareItems}
              selected={isDemo ? [] : codes}
              onAdd={addCode}
              atCap={atCap}
              capHint={capHint}
              compatibilityFor={compatibilityFor}
              onClear={clearAll}
              status={status}
              catalogLoading={worldCatalogLoading}
              onLimit={isAuthed ? undefined : openLimit}
            />

            {compatibilityMessage && (
              <div className="mt-3 rounded-xl bg-champagne/[0.06] px-3.5 py-2.5 text-xs leading-relaxed text-text-secondary fe-shadow-2" role="status">
                {compatibilityMessage}
              </div>
            )}

            {(atCap || !isAuthed) && (
              <p className="mt-3 text-[13px] leading-snug text-text-secondary">
                {isAuthed
                  ? t('compare.selectedAuthed', { n: codes.length, max: USER_MAX })
                  : t('compare.selectedGuest', { n: codes.length, max: GUEST_MAX })}
                {!isAuthed && (
                  <>
                    {' '}
                    <button type="button" onClick={() => { setUpsellOpen(true); track(events.REGISTER_NUDGE_EXPAND, { from: 'compare' }); }} className="font-medium text-champagne-ink hover:underline">
                      {t('compare.wantMore')}
                    </button>
                  </>
                )}
              </p>
            )}
          </>
        )}
      </section>

      {hasError && hasData && !loading && (
        <div className="mb-6 flex flex-col gap-3 rounded-2xl bg-warn-surface px-4 py-4 text-sm shadow-md sm:flex-row sm:items-center sm:justify-between fe-shadow-2" role="alert">
          <p className="min-w-0 text-text-primary">
            <span className="font-semibold">{t('compare.loadPartial')}</span>{' '}
            {t('compare.loadPartialHint')}
          </p>
          {failedQueries.length > 0 && (
            <Button variant="secondary" size="sm" onClick={retryFailed} loading={retrying} className="shrink-0">
              {t('common.retry')}
            </Button>
          )}
        </div>
      )}

      <section ref={setSectionNode} data-block="compare-chart" className="mb-8">
        {loading ? (
          <CompareChartState kind="loading" height={chartHeight} />
        ) : !hasData ? (
          <CompareChartState
            kind={codes.length === 0 ? 'none' : loadFailed ? 'error' : 'empty'}
            compact={codes.length === 0}
            height={chartHeight}
            onRetry={failedQueries.length > 0 ? retryFailed : undefined}
            retrying={retrying}
            message={
              codes.length === 0
                ? t('w6g.compare.emptyAdd')
                : loadFailed
                  ? t('w4.compare.emptyUnavailable')
                  : noSharedBase
                    ? t('compare.noSharedBase')
                    : indexed && nonIndexableNames.length === series.length
                      ? t('compare.noIndexableBase')
                      : t('compare.emptyData')
            }
          />
        ) : (
          <div ref={exportRef} className="fe-panel fe-reveal fe-compare-card">
            <div className="fe-compare-card__head">
              <h2 className="fe-compare-card__title">
                {headline}
              </h2>
              <p className="fe-compare-card__caption">
                {indexed
                  ? t('compare.hintIndex', { date: formatDate(baseDate, compareDateFmt) })
                  : (unitsCaption || t('compare.hintValues'))}
                {` ${t('compare.periodLabel')}: ${range === 'custom'
                  ? `${formatDate(chartRows[0]?.date, compareDateFmt)} – ${formatDate(chartRows[chartRows.length - 1]?.date, compareDateFmt)}`
                  : t(RANGE_OPTIONS.find((r) => r.key === range)?.labelKey || 'compare.range.all').toLowerCase()}`}
              </p>
            </div>

            {/* Круг 10 (Ср2): что значит «старт = 100» сказано словами и с примером, а настоящие числа возвращает видимая кнопка рядом. */}
            {indexed && !forceIndex && baseDate && (
              <div className="fe-compare-auto" role="status" data-testid={autoIndex ? 'compare-auto-index' : 'compare-index-note'} data-no-export="true">
                <p>{t(autoIndex ? 'c10k.compare.autoIndex' : 'c10k.compare.manualIndex', { date: formatDate(baseDate, compareDateFmt) })}</p>
                <Button variant="secondary" size="sm" onClick={() => chooseScale('values')}>
                  {t('z7.scale.backToValues')}
                </Button>
              </div>
            )}

            {gap && (
              <p className="fe-compare-gap" data-testid="compare-gap">
                <span className="fe-compare-gap__beads" aria-hidden="true">
                  {series.slice(0, 2).map((s) => (
                    <i key={s.key} style={{ '--bead': s.color }} />
                  ))}
                </span>
                <span>
                  {gap.equal
                    ? t('z7.compare.gapEqual', { a: gap.a, b: gap.b })
                    : t('z7.compare.gap', {
                      leader: gap.leader, other: gap.other, ratio: gap.ratio, times: t(`z7.compare.times.${gap.plural}`),
                    })}
                </span>
              </p>
            )}

            <div className={cn('fe-compare-legend', !legendNeeded && 'sr-only')}>
              {series.map((s, i) => {
                const dropped = nonIndexableKeys.has(s.key);
                return (
                  <span key={s.code} className={cn('flex min-w-0 max-w-full items-start gap-2', dropped && 'opacity-60')}>
                    <span className="mt-[7px] h-[3px] w-5 shrink-0 rounded-full" style={{ backgroundColor: s.color }} />
                    <span className="min-w-0 break-words">
                    <span className="font-semibold text-text-primary">{labels[i] || t('z2.compare.seriesFallback')}</span>{' '}
                    <span className="text-text-secondary">
                      {legendDetail(s, i, dropped)}
                    </span>
                    </span>
                  </span>
                );
              })}
            </div>

            {nonIndexableNames.length > 0 && (
              <p className="mb-4 -mt-1 text-left text-xs text-text-secondary">
              {t(mixedPriceIndexBases ? 'compare.priceIndexPercentExcluded' : 'compare.nonIndexableNote', {
                names: nonIndexableNames.join(', '),
              })}
              </p>
            )}

            <div
              ref={setChartArea}
              role="img"
              aria-label={t('compare.chartAria')}
              onPointerDownCapture={touchTip.onPointerDownCapture}
              onPointerDown={handlePointerDown}
              onPointerMove={handlePointerMove}
              onPointerUp={handlePointerUp}
              onPointerCancel={handlePointerUp}
              className={cn(
                'fe-compare-plot k4-glass-plot relative rounded-2xl',
                maxPan > 0 && (isDragging ? 'cursor-grabbing select-none' : 'cursor-grab'),
              )}
              style={{ touchAction: 'pan-y' }}
            >
              <ResponsiveContainer width="100%" height={chartHeight}>
                <ComposedChart
                  data={chartRows}
                  margin={{ top: 10, right: chartMarginRight, bottom: 4, left: 0 }}
                >
                  <defs>
                    {RIBBON_GRADIENTS.map((stops, gi) => (
                      <linearGradient key={gi} id={`${glass.ribbon}-${gi}`} gradientUnits="userSpaceOnUse" x1="0" y1="0" x2={Math.max(plotWidth, 320)} y2="0">
                        {stops.map((stop) => <stop key={stop.offset} offset={stop.offset} stopColor={stop.color} />)}
                      </linearGradient>
                    ))}
                    {PALETTE.slice(0, RIBBON_COUNT).map((color, gi) => (
                      <linearGradient key={`area-${gi}`} id={gi === 0 ? glass.area : glass.areaSapphire} x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor={color} stopOpacity={AREA_OPACITY[gi]} />
                        <stop offset="100%" stopColor={color} stopOpacity={0} />
                      </linearGradient>
                    ))}
                  </defs>
                  <CartesianGrid {...GRID_PROPS} />
                  <XAxis
                    dataKey="date"
                    tickFormatter={(d) => formatChartAxisDate(d, compareDateFmt, { multiYear: true })}
                    tick={axisTick({ fontSize: axisFontSize })}
                    axisLine={{ stroke: CHART_THEME.axisLine }}
                    tickLine={false}
                    ticks={xTicks}
                    interval={0}
                    tickMargin={8}
                    height={xAxisHeight}
                  />
                  <YAxis
                    yAxisId="left"
                    domain={axisScales.left?.domain || AXIS_DOMAIN}
                    ticks={axisScales.left?.ticks}
                    tick={axisTick({ fontSize: axisFontSize })}
                    axisLine={false}
                    tickLine={false}
                    width={axisWidths.left}
                    tickFormatter={(v) => (indexed ? formatAxisTick(v, 0) : formatAxisTick(v, unitDigits(leftUnit)))}
                  />
                  {!indexed && distinctUnits.length > 1 && (
                    <YAxis
                      yAxisId="right"
                      orientation="right"
                      domain={axisScales.right?.domain || AXIS_DOMAIN}
                      ticks={axisScales.right?.ticks}
                      tick={axisTick({ fontSize: axisFontSize })}
                      axisLine={false}
                      tickLine={false}
                      width={axisWidths.right}
                      tickFormatter={(v) => formatAxisTick(v, unitDigits(rightUnit))}
                    />
                  )}
                  <Tooltip
                    content={<CompareTooltip dateFormat={compareDateFmt} colors={seriesColors} />}
                    cursor={HOVER_CURSOR}
                    {...touchTip.tooltipProps}
                  />
                  {/* Мягкая заливка под лентами первых двух рядов: тот же цвет ряда, 16 % / 14 % у линии, к оси 0. */}
                  {series.slice(0, RIBBON_COUNT).map((s, i) => (
                    <Area
                      key={`${s.key}-area`}
                      yAxisId={axisFor(i)}
                      type="monotone"
                      dataKey={s.key}
                      stroke="none"
                      fill={`url(#${i === 0 ? glass.area : glass.areaSapphire})`}
                      dot={false}
                      activeDot={false}
                      connectNulls
                      isAnimationActive={false}
                      legendType="none"
                      tooltipType="none"
                    />
                  ))}
                  {series.map((s, i) => (
                    <Line
                      key={s.key}
                      yAxisId={axisFor(i)}
                      type="monotone"
                      dataKey={s.key}
                      name={labels[i] || t('z2.compare.seriesFallback')}
                      className={i === 0 ? 'k4-ribbon' : i === 1 ? 'k4-ribbon k4-ribbon--sapphire' : 'k4-ribbon k4-ribbon--plain'}
                      stroke={i < RIBBON_COUNT ? `url(#${glass.ribbon}-${i})` : s.color}
                      strokeWidth={3.5}
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      dot={false}
                      activeDot={isDragging ? false : { r: 5, fill: s.color, stroke: '#FFFFFF', strokeWidth: 2 }}
                      connectNulls
                      isAnimationActive={false}
                    />
                  ))}
                  {/* Белый блик-штрих 1 px поверх каждой ленты, на 1 px выше (css k4-gloss). */}
                  {series.slice(0, RIBBON_COUNT).map((s, i) => (
                    <Line
                      key={`${s.key}-gloss`}
                      className="k4-gloss"
                      yAxisId={axisFor(i)}
                      type="monotone"
                      dataKey={s.key}
                      stroke="rgba(255,255,255,0.9)"
                      strokeWidth={1.4}
                      strokeLinecap="round"
                      dot={false}
                      activeDot={false}
                      connectNulls
                      isAnimationActive={false}
                      legendType="none"
                      tooltipType="none"
                    />
                  ))}
                  {/* Плоская точка на конце каждой линии (при перетаскивании окна прячется, как у карточки показателя). */}
                  {!isDragging && endDots.map((dot) => (
                    <ReferenceDot
                      key={dot.key}
                      yAxisId={dot.axis}
                      x={dot.x}
                      y={dot.y}
                      r={5}
                      ifOverflow="visible"
                      shape={(props) => (
                        <EndPoint cx={props.cx} cy={props.cy} color={dot.color} />
                      )}
                    />
                  ))}
                </ComposedChart>
              </ResponsiveContainer>
              {/* Подписи концов линий: имя и последнее значение прямо у линии, без поиска по легенде. */}
              {endLabels.map((item) => (
                <div
                  key={item.key}
                  className="fe-compare-end"
                  data-testid="compare-end-label"
                  style={{ top: item.top, width: endLabelWidth - 10, '--bead': item.color }}
                >
                  {item.flag ? <span className="fe-compare-end__flag" aria-hidden="true">{item.flag}</span> : <span className="fe-compare-end__flag fe-compare-end__flag--dot" aria-hidden="true" />}
                  <span className="fe-compare-end__text">
                    <span className="fe-compare-end__name">{item.name}</span>
                    <span className="fe-compare-end__value fe-num">{item.text}</span>
                  </span>
                </div>
              ))}
              {/* Знак сайта стоит под графиком, а не поверх него: раньше он налезал на подписи дат. */}
              {!isAuthed && !isAuthLoading && (
                <div
                  aria-hidden="true"
                  data-no-export="true"
                  className="pointer-events-none select-none whitespace-nowrap pb-0.5 pr-2 pt-0.5 text-right text-[11px] font-medium text-text-primary opacity-40"
                >
                  forecasteconomy.com
                </div>
              )}
            </div>

            {/* Период: две ручки (начало и конец) на уменьшенной копии ряда, середина двигает окно. */}
            {brushRows.length >= 8 && (
              <div className="fe-compare-brush" data-no-export="true">
                <ChartBrush
                  rows={brushRows}
                  start={windowStart}
                  end={windowEnd}
                  minWindow={Math.min(4, Math.max(2, brushRows.length - 1))}
                  onChange={handleBrush}
                  labels={{
                    group: t('chart.windowAria'),
                    from: t('w6e.brush.from'),
                    to: t('w6e.brush.to'),
                  }}
                />
                <div className="fe-compare-brush__dates">
                  <span>{chartRows[0] ? formatDate(chartRows[0].date, compareDateFmt) : ''}</span>
                  <span className="hidden sm:inline">
                    {t(coarsePointer ? 'z7.compare.brushHintTouch' : 'z7.compare.brushHint')}
                  </span>
                  <span>{chartRows.length ? formatDate(chartRows[chartRows.length - 1].date, compareDateFmt) : ''}</span>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Настройки — после графика и только когда есть что настраивать. */}
        {hasData && !loading && (
          <div
            data-block="compare-settings"
            className="mt-5 grid gap-4 pt-5 sm:flex sm:flex-wrap sm:items-end sm:gap-x-6 k5-seam k5-seam--top"
          >
            <div className="min-w-0">
              <div className="mb-1.5 flex items-center gap-1.5 text-xs font-medium text-text-secondary">
                <Activity className="h-3.5 w-3.5 text-champagne" aria-hidden="true" />
                {t('compare.periodLabel')}
              </div>
              <div className="fe-scroll-row">
                {RANGE_OPTIONS.map((opt) => (
                  <Chip
                    key={opt.key}
                    active={range === opt.key}
                    onClick={() => { setRange(opt.key); setPanOffset(0); track(events.COMPARE_RANGE, { range: opt.key }); }}
                  >
                    {t(opt.labelKey)}
                  </Chip>
                ))}
              </div>
            </div>

            <div className="min-w-0">
              <div
                className="mb-1.5 text-xs font-medium text-text-secondary"
                title={t(hasWorldSeries ? 'compare.worldOfficialOnly' : 'compare.stepTitle')}
              >
                {t('w4.compare.stepLabel')}
              </div>
              {hasWorldSeries ? (
                <span className="inline-flex min-h-[34px] items-center rounded-xl px-3 text-xs text-text-secondary fe-glass-2">
                  {t('w6g.compare.step.official')}
                </span>
              ) : (
                <div className="fe-scroll-row">
                  {STEP_OPTIONS.map((opt) => (
                    <Chip
                      key={opt.key}
                      active={step === opt.key}
                      onClick={() => { setStep(opt.key); setPanOffset(0); track(events.COMPARE_RANGE, { step: opt.key }); }}
                    >
                      {t(opt.labelKey === 'compare.step.auto' ? 'w6g.compare.step.auto' : opt.labelKey)}
                    </Chip>
                  ))}
                </div>
              )}
            </div>

            <div className="min-w-0">
              <div className="mb-1.5 text-xs font-medium text-text-secondary">{t('w4.compare.scaleLabel')}</div>
              <div className="fe-scroll-row">
                {SCALE_OPTIONS.map((opt) => {
                  const disabled = forceIndex && opt.key === 'values';
                  return (
                    <Chip
                      key={opt.key}
                      disabled={disabled}
                      active={indexed ? opt.key === 'index' : scale === opt.key && !forceIndex}
                      onClick={() => chooseScale(opt.key)}
                      title={disabled ? t('compare.indexOnlyUnits') : undefined}
                    >
                      {t(opt.key === 'index' ? 'w6g.compare.scale.index' : 'w6g.compare.scale.values')}
                    </Chip>
                  );
                })}
              </div>
            </div>

            <Button
              variant="secondary"
              size="sm"
              onClick={handleExport}
              className="w-full sm:ml-auto sm:w-auto"
              title={t('compare.downloadChart')}
            >
              <ImageDown className="h-3.5 w-3.5" aria-hidden="true" />
              {t('w6g.compare.saveImage')}
            </Button>
          </div>
        )}

        {forceIndex && hasData && (
          <p className="mt-4 text-xs text-text-tertiary">
            {t(mixedPriceIndexBases ? 'compare.priceIndexBaseHint' : 'compare.forceIndexHint')}
            {mixedPriceIndexBases && (
              <> {' '}<Link to="/world/rating/hicp-index" className="text-champagne hover:underline">
                {t('world.chart.compareInflationRates')}
              </Link></>
            )}
          </p>
        )}
      </section>

      {hasData && analysisSummary.metrics.some((metric) => metric.last) && (
        <section data-block="compare-analysis" className="fe-panel fe-compare-analysis rounded-[2rem] p-5 md:p-7">
          <div className="mb-5 flex flex-col gap-2 pb-5 sm:flex-row sm:items-end sm:justify-between k5-seam">
            <div>
              <div className="text-sm font-medium text-champagne-ink">
                {t('compare.analysis.eyebrow')}
              </div>
              <h2 className="mt-1 font-display text-2xl font-bold text-text-primary">
                {t('compare.analysis.title')}
              </h2>
            </div>
            <div className="text-[11px] leading-5 text-text-tertiary">
              {t('compare.analysis.note')}
            </div>
          </div>

          <div className="fe-compare-summary" data-count={analysisSummary.metrics.filter((metric) => metric.last).length}>
            {analysisSummary.metrics.filter((metric) => metric.last).map((metric) => {
              const displayUnit = indexed ? t('compare.points') : (metric.item.unit || '%');
              // Большие числа без дробной части: «3 360 622», а не «3 360 621,70».
              const bigDigits = (v) => (Math.abs(v) >= 1000 ? 0 : undefined);
              const lastValue = formatValueSplit(metric.last.value, displayUnit, bigDigits(metric.last.value));
              const changeValue = formatValueSplit(
                metric.change,
                compareDifferenceUnit(metric.item.unit || '%', { indexed, locale }),
                bigDigits(metric.change),
              );
              return (
                <div key={metric.item.code} className="fe-compare-summary__card" style={{ '--fe-series': metric.item.color }}>
                  <div className="flex items-start gap-2">
                    <span className="mt-1 h-2.5 w-2.5 shrink-0 rounded-full" style={{ backgroundColor: metric.item.color }} />
                    <div title={metric.item.name || undefined} className="min-w-0 text-sm font-medium leading-5 text-text-primary">
                      {shortSeriesName(metric.item) || t('z2.compare.seriesFallback')}
                    </div>
                  </div>
                  <div className="mt-4 grid grid-cols-2 gap-3">
                    <div>
                      <div className="text-xs font-medium text-text-secondary">{t('compare.analysis.last')}</div>
                      <div className="fe-num mt-1 text-lg font-semibold leading-tight text-text-primary">
                        {lastValue.main}
                      </div>
                    </div>
                    <div>
                      <div className="text-xs font-medium text-text-secondary">{t('compare.analysis.change')}</div>
                      <div className={cn(
                        'fe-num mt-1 text-lg font-semibold leading-tight',
                        `fe-tone--${deltaTone(metric.change, indicatorPolarity(metric.item.ind?.name, metric.item.code))}`,
                      )}>
                        {metric.change > 0 ? '+' : ''}
                        {changeValue.main}
                      </div>
                    </div>
                  </div>
                  {(lastValue.tail || changeValue.tail) && (
                    <p className="mt-2 text-xs leading-snug text-text-secondary">
                      {lastValue.tail || changeValue.tail}
                    </p>
                  )}
                  {indexed && baseDate && (
                    <p className="mt-1 text-xs leading-snug text-text-tertiary">
                      {t('c9d.compare.indexBase', { date: formatDate(baseDate, compareDateFmt) })}
                    </p>
                  )}
                  {/п\.\s?п\.|p\.p\./.test(changeValue.unitShort || '') && (
                    <p className="mt-1 text-xs leading-snug text-text-tertiary">{t('x4.compare.ppHint')}</p>
                  )}
                  <div className="mt-3 pt-2.5 text-xs text-text-secondary">
                    {formatDate(metric.first.date, compareDateFmt)} → {formatDate(metric.last.date, compareDateFmt)}
                  </div>
                </div>
              );
            })}
          </div>

          {analysisSummary.correlations.length > 0 && (
            <div className="mt-5 rounded-2xl bg-champagne/[0.05] p-4 fe-shadow-2">
              <div className="flex items-center gap-2 text-xs font-semibold text-text-primary">
                <Sparkles size={14} className="text-champagne" />
                {t('compare.analysis.sync')}
              </div>
              <div className="mt-3 grid gap-2 sm:grid-cols-2">
                {analysisSummary.correlations.map((result) => (
                  <div key={result.item.code} className="flex items-center justify-between gap-3 rounded-xl bg-white/65 px-3 py-2.5">
                    <span className="min-w-0 break-words text-xs text-text-secondary">
                      {shortSeriesName(result.item) || t('z2.compare.seriesFallback')}
                    </span>
                    <span className="shrink-0 text-sm font-semibold text-text-primary">
                      {t(correlationKey(result.value))}
                    </span>
                  </div>
                ))}
              </div>
              <details className="fe-acc mt-3 text-xs leading-5 text-text-secondary">
                <summary className="fe-tap-inline gap-1 text-champagne-ink">
                  {t('w4.compare.corr.how')}
                  <ChevronDown className="fe-acc__chev h-3.5 w-3.5" aria-hidden="true" />
                </summary>
                <p className="mt-1">
                  {t('w4.compare.corr.details', {
                    values: analysisSummary.correlations
                      .map((item) => item.value.toFixed(2).replace('.', locale === 'en' ? '.' : ','))
                      .join(', '),
                  })}
                </p>
              </details>
            </div>
          )}
        </section>
      )}
    </div>
  );
}
