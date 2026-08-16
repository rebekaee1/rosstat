import { useState, useMemo, useCallback, useEffect, useRef } from 'react';
import { useSearchParams, Link } from 'react-router-dom';
import { useQueries } from '@tanstack/react-query';
import {
  ResponsiveContainer, ComposedChart, Line, XAxis, YAxis,
  Tooltip, CartesianGrid,
} from 'recharts';
import {
  ArrowLeft, Activity, GitCompare, Search, X, Plus, ImageDown, Sparkles,
  Landmark, MapPin, Check, ChevronDown, Globe2,
} from 'lucide-react';
import { useIndicators } from '../lib/hooks';
import { fetchIndicatorData } from '../lib/api';
import api from '../lib/api';
import { useRegionsLanding, useRegionsCatalog } from '../lib/regionsApi';
import { fetchWorldCompareSeries, useWorldCompareCatalog } from '../lib/worldApi';
import { useAuth } from '../context/authContext';
import { useT, useLocale } from '../i18n';
import {
  formatDate, formatChartAxisDate, formatAxisTick, formatValueWithUnit,
  unitSuffix, unitDigits, cn, pickChartAxisTicks, chartAxisTickBudget,
} from '../lib/format';
import useDocumentMeta from '../lib/useMeta';
import { getPageSeo } from '../lib/pageMeta';
import { ChartSkeleton } from '../components/Skeleton';
import { track, events } from '../lib/track';
import useSearchTracking from '../lib/useSearchTracking';
import { exportNodeToPng } from '../lib/chartImage';
import useScrollDepth from '../lib/useScrollDepth';
import {
  REP_LEVEL, REP_ORDER, REP_HINT, compareRepresentationsFor, resolveCompareSeries,
  applyCompareTransform, isIndexableBase, rebaseToHundred, resolveStepOverride,
  worldCompareRepresentationsFor, worldCompareTransformFor,
} from '../lib/compareRepresentation';
import {
  activeCompatibilityNote,
  compareCompatibility,
  parseWorldCompareCode,
  sanitizeCompareCodes,
} from '../lib/compareCompatibility';
import {
  regionHubPath,
} from '../lib/sitePaths';

const RANGE_OPTIONS = [
  { key: '3y', labelKey: 'compare.range.3y', months: 36 },
  { key: '5y', labelKey: 'compare.range.5y', months: 60 },
  { key: '10y', labelKey: 'compare.range.10y', months: 120 },
  { key: 'all', labelKey: 'compare.range.all', months: null },
];

// До 10 рядов — палитра различимых цветов (тёмный фон карточки графика).
const PALETTE = [
  '#d4a574', '#7dd3fc', '#86efac', '#f0abfc', '#fca5a5',
  '#fcd34d', '#a5b4fc', '#5eead4', '#fdba74', '#cbd5e1',
];

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

async function fetchWorldSeries(code, { signal }) {
  const parsed = parseWorldCompareCode(code);
  if (!parsed) throw new Error('compare.error.worldCode');
  const payload = await fetchWorldCompareSeries(parsed.countrySlug, parsed.conceptSlug, { signal });
  return {
    data: payload.data,
    __worldMeta: {
      code,
      name: `${payload.meta.concept_name} — ${payload.meta.country_name}`,
      unit: payload.meta.unit,
      frequency: payload.meta.frequency,
      category: 'compare.category.world',
      conceptSlug: payload.meta.concept_slug,
    },
  };
}

// Единый стиль «поля-поиска» для макро- и регионального выбора — чтобы они
// выглядели одинаково (требование: макро и регион не должны расходиться).
const FIELD_CLS =
  'flex items-center gap-2 rounded-lg border bg-obsidian-light px-3 py-2 transition-colors';

/** Шапка карточки добавления: иконка + заголовок + подсказка. */
function AddCardHeader({ icon, title, hint }) {
  const Icon = icon;
  return (
    <div className="mb-2.5 flex items-center gap-2">
      <span className="flex h-6 w-6 items-center justify-center rounded-md bg-champagne/12">
        <Icon className="h-3.5 w-3.5 text-champagne" />
      </span>
      <div className="min-w-0">
        <div className="text-[11px] font-mono uppercase tracking-widest text-text-secondary leading-none">
          {title}
        </div>
        {hint && <div className="mt-1 text-[11px] text-text-tertiary leading-tight">{hint}</div>}
      </div>
    </div>
  );
}

/**
 * Searchable single-select combobox: открывается по клику (весь список,
 * скроллится), фильтруется вводом. Поддерживает группы (секции показателей).
 * Один визуальный язык с макро-поиском (`AddIndicator`).
 */
function ComboSelect({
  groups, value, onChange, placeholder, searchPlaceholder, ariaLabel, disabled, trackContext,
}) {
  const t = useT();
  const [query, setQuery] = useState('');
  const [open, setOpen] = useState(false);
  const boxRef = useRef(null);

  const selectedLabel = useMemo(() => {
    for (const g of groups) {
      const hit = g.items.find((it) => it.value === value);
      if (hit) return hit.label;
    }
    return '';
  }, [groups, value]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return groups
      .map((g) => ({
        label: g.label,
        items: q ? g.items.filter((it) => it.label.toLowerCase().includes(q)) : g.items,
      }))
      .filter((g) => g.items.length);
  }, [groups, query]);

  const total = filtered.reduce((n, g) => n + g.items.length, 0);

  // Спрос-аналитика: каждый набранный запрос в комбобоксах сравнения тоже
  // уходит в search_query (директива «собирать все поиски», 2026-07-05).
  useSearchTracking(trackContext || 'compare-combo', open ? query : '', total);

  return (
    <div className="relative" ref={boxRef}>
      <div
        className={cn(
          FIELD_CLS,
          disabled ? 'border-border-subtle/50 opacity-60' : 'border-border-subtle focus-within:border-champagne/40',
          value && !open && 'border-champagne/30',
        )}
      >
        <Search className="h-4 w-4 shrink-0 text-text-tertiary" />
        <input
          type="text"
          aria-label={ariaLabel}
          disabled={disabled}
          value={open ? query : selectedLabel}
          placeholder={value && !open ? selectedLabel : (open ? searchPlaceholder : placeholder)}
          onFocus={() => { setOpen(true); setQuery(''); }}
          onBlur={() => setTimeout(() => setOpen(false), 150)}
          onChange={(e) => setQuery(e.target.value)}
          className="min-w-0 flex-1 bg-transparent text-sm text-text-primary outline-none placeholder:text-text-tertiary disabled:cursor-not-allowed"
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

      {open && !disabled && (
        <div className="absolute z-40 mt-2 max-h-72 w-full overflow-auto rounded-xl border border-border-subtle bg-surface shadow-2xl">
          {total === 0 ? (
            <div className="px-4 py-3 text-sm text-text-tertiary">{t('compare.nothingFound')}</div>
          ) : (
            filtered.map((g) => (
              <div key={g.label || '_'}>
                {g.label && (
                  <div className="sticky top-0 bg-obsidian-light px-3 py-1.5 text-[10px] font-mono uppercase tracking-wider text-text-tertiary">
                    {g.label}
                  </div>
                )}
                {g.items.map((it) => (
                  <button
                    key={it.value}
                    type="button"
                    onMouseDown={(e) => { e.preventDefault(); onChange(it.value); setQuery(''); setOpen(false); }}
                    className="flex w-full items-center justify-between gap-3 px-4 py-2.5 text-left hover:bg-obsidian-lighter transition-colors"
                  >
                    <span className="truncate text-sm text-text-primary">{it.label}</span>
                    {it.value === value
                      ? <Check className="h-3.5 w-3.5 shrink-0 text-champagne" />
                      : it.hint && <span className="shrink-0 font-mono text-[11px] text-text-tertiary">{it.hint}</span>}
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

/**
 * Добавление регионального ряда: тот же язык, что и макро-поиск, но разбит на
 * два searchable-combobox'а — «Регион» и «Показатель» — и кнопку «Добавить».
 * Оба поля можно листать целиком или искать вводом (85 регионов × десятки
 * показателей).
 */
function AddRegionSeries({
  selected, onAdd, atCap, capHint, compatibilityFor,
}) {
  const t = useT();
  const landing = useRegionsLanding();
  const catalog = useRegionsCatalog();
  const [regionSlug, setRegionSlug] = useState('');
  const [indCode, setIndCode] = useState('');

  const regionGroups = useMemo(() => {
    if (!landing.data) return [{ label: '', items: [] }];
    const items = landing.data.districts
      .flatMap((d) => d.regions.map((r) => ({ value: r.slug, label: r.name })))
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
        .map((i) => ({ value: i.code, label: i.name })),
    })).filter((section) => section.items.length);
  }, [catalog.data, compatibilityFor, regionSlug]);

  const code = regionSlug && indCode ? `r:${regionSlug}:${indCode}` : null;
  const already = code && selected.includes(code);
  const compatibility = code && compatibilityFor
    ? compatibilityFor(code)
    : { allowed: true, reason: null };
  const canAdd = code && !already && !atCap && compatibility.allowed;

  const handleAdd = () => {
    if (!canAdd) return;
    onAdd(code);
    track(events.REGION_COMPARE_ADD, { code });
    setIndCode(''); // регион оставляем — удобно добавить второй показатель того же региона
  };

  return (
    <div className="rounded-xl border border-border-subtle bg-surface p-3">
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
          onChange={setIndCode}
          ariaLabel={t('compare.regionIndicatorAria')}
          placeholder={t('compare.regionIndicatorPlaceholder')}
          searchPlaceholder={t('compare.regionIndicatorSearch')}
          disabled={atCap || !regionSlug}
          trackContext="compare-region-indicator"
        />
        <button
          type="button"
          disabled={!canAdd}
          onClick={handleAdd}
          title={atCap
            ? capHint
            : already
              ? t('compare.alreadyAdded')
              : compatibility.reason || undefined}
          className={cn(
            'inline-flex items-center justify-center gap-1.5 rounded-lg px-3 py-2 text-sm font-medium transition-colors',
            canAdd
              ? 'bg-champagne/15 text-champagne hover:bg-champagne/25'
              : 'bg-obsidian-lighter text-text-tertiary cursor-not-allowed',
          )}
        >
          <Plus className="h-3.5 w-3.5" />
          {already ? t('compare.alreadyAddedShort') : t('compare.addRegionSeries')}
        </button>
      </div>
    </div>
  );
}

function AddIndicator({
  indicators, selected, onAdd, atCap, capHint, compatibilityFor,
}) {
  const t = useT();
  const [query, setQuery] = useState('');
  const [openList, setOpenList] = useState(false);
  // Директория сравнения: показываем ВСЕ показатели (минус уже выбранные),
  // список скроллится (`max-h-80 overflow-auto`). Жёсткого «топ-8» нет —
  // листать можно весь каталог (звонок 2026-06-25). Любой новый индикатор
  // приходит из API и попадает сюда автоматически. Поиск идёт и по
  // seo_keywords (синонимы/корни), как в основном поиске.
  const results = useMemo(() => {
    const q = query.trim().toLowerCase();
    const pool = (indicators || []).filter((i) =>
      !selected.includes(i.code)
      && (!compatibilityFor || compatibilityFor(i.code).allowed));
    if (!q) return pool;
    return pool.filter((i) => {
      const hay = `${i.name || ''} ${i.name_en || ''} ${i.category || ''} ${i.code || ''} ${i.seo_keywords || ''}`.toLowerCase();
      return hay.includes(q);
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
        atCap ? 'border-border-subtle/50 opacity-60' : 'border-border-subtle focus-within:border-champagne/40',
      )}>
        <Search className="w-4 h-4 text-text-tertiary shrink-0" />
        <input
          type="text"
          value={query}
          disabled={atCap}
          onChange={(e) => setQuery(e.target.value)}
          onFocus={() => setOpenList(true)}
          onBlur={() => setTimeout(() => setOpenList(false), 150)}
          placeholder={atCap ? capHint : t('compare.macroPlaceholder')}
          className="flex-1 bg-transparent text-sm text-text-primary outline-none placeholder:text-text-tertiary disabled:cursor-not-allowed"
        />
        <ChevronDown className="w-4 h-4 shrink-0 text-text-tertiary" />
      </div>
      {openList && !atCap && results.length > 0 && (
        <div className="absolute z-40 mt-2 w-full max-h-80 overflow-auto rounded-xl border border-border-subtle bg-surface shadow-2xl">
          {results.map((ind) => (
            <button
              key={ind.code}
              type="button"
              onMouseDown={(e) => { e.preventDefault(); onAdd(ind.code); setQuery(''); }}
              className="flex w-full items-center justify-between gap-3 px-4 py-2.5 text-left hover:bg-obsidian-lighter transition-colors"
            >
              <span className="text-sm text-text-primary truncate">{ind.name}</span>
              <span className="flex items-center gap-2 shrink-0">
                <span className="text-[11px] font-mono text-text-tertiary">{unitSuffix(ind.unit)}</span>
                <Plus className="w-3.5 h-3.5 text-champagne" />
              </span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

/**
 * Показатель выбранной страны (страна уже зафиксирована в дереве пикера).
 * Код ряда — `w:{slug}:{concept}`.
 */
function AddWorldCountrySeries({
  items, countrySlug, selected, onAdd, atCap, capHint, compatibilityFor,
}) {
  const t = useT();
  const [conceptSlug, setConceptSlug] = useState('');

  const conceptItems = useMemo(() => {
    const map = new Map();
    for (const item of items || []) {
      if (item.country_slug !== countrySlug) continue;
      if (map.has(item.concept_slug)) continue;
      const freq = item.frequency === 'monthly'
        ? t('compare.freq.monthShort')
        : item.frequency === 'quarterly'
          ? t('compare.freq.quarterShort')
          : t('compare.freq.yearShort');
      map.set(item.concept_slug, {
        value: item.concept_slug,
        label: item.concept_name,
        hint: freq,
        code: item.code,
      });
    }
    return [...map.values()].sort((a, b) => a.label.localeCompare(b.label, 'ru'));
  }, [items, countrySlug, t]);

  const selectedConcept = conceptItems.find((item) => item.value === conceptSlug);
  const code = selectedConcept?.code || null;
  const already = code && selected.includes(code);
  const compatibility = code
    ? compatibilityFor(code)
    : { allowed: false, reason: null };
  const canAdd = code && !already && !atCap && compatibility.allowed;

  return (
    <div className="grid gap-2">
      <ComboSelect
        groups={[{ label: t('compare.conceptGroup'), items: conceptItems }]}
        value={conceptSlug}
        onChange={setConceptSlug}
        placeholder={t('compare.conceptPlaceholder')}
        searchPlaceholder={t('compare.conceptSearch')}
        ariaLabel={t('compare.conceptAria')}
        disabled={atCap || conceptItems.length === 0}
        trackContext="compare-world-concept"
      />
      <button
        type="button"
        disabled={!canAdd}
        onClick={() => { if (canAdd) { onAdd(code); setConceptSlug(''); } }}
        title={atCap
          ? capHint
          : already
            ? t('compare.alreadyAdded')
            : compatibility.reason || undefined}
        className={cn(
          'inline-flex min-h-10 w-full items-center justify-center gap-1.5 rounded-lg px-4 py-2 text-sm font-medium transition-colors',
          canAdd
            ? 'bg-champagne/15 text-champagne hover:bg-champagne/25'
            : 'cursor-not-allowed bg-obsidian-lighter text-text-tertiary',
        )}
      >
        <Plus className="h-3.5 w-3.5" />
        {already ? t('compare.alreadyAddedShort') : t('common.add')}
      </button>
      {code && !already && !atCap && !compatibility.allowed && (
        <p className="text-xs leading-relaxed text-text-tertiary">
          {compatibility.reason}
        </p>
      )}
      {!conceptItems.length && (
        <p className="text-xs leading-relaxed text-text-tertiary">
          {t('compare.noCountrySeries')}
        </p>
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
      className="mb-3 inline-flex items-center gap-1.5 text-xs font-mono uppercase tracking-widest text-text-tertiary hover:text-champagne transition-colors"
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
}) {
  const t = useT();
  const [countryKey, setCountryKey] = useState(null);
  const [russiaBranch, setRussiaBranch] = useState(null);
  const [countryQuery, setCountryQuery] = useState('');

  const countries = useMemo(() => {
    const map = new Map();
    for (const item of worldItems || []) {
      if (!item.country_slug || map.has(item.country_slug)) continue;
      map.set(item.country_slug, {
        key: item.country_slug,
        label: item.country_name,
      });
    }
    return [...map.values()].sort((a, b) => a.label.localeCompare(b.label, 'ru'));
  }, [worldItems]);

  const filteredCountries = useMemo(() => {
    const q = countryQuery.trim().toLowerCase();
    const russia = { key: 'russia', label: t('compare.russia') };
    const rest = q
      ? countries.filter((c) => c.label.toLowerCase().includes(q))
      : countries;
    const showRussia = !q || 'россия'.includes(q) || 'russia'.includes(q) || russia.label.toLowerCase().includes(q);
    return showRussia ? [russia, ...rest] : rest;
  }, [countries, countryQuery, t]);

  // Поиск страны в дереве сравнения — без клика по результату.
  useSearchTracking(
    'compare-country',
    countryKey ? '' : countryQuery,
    filteredCountries.length,
  );

  const selectedCountry = countryKey === 'russia'
    ? { key: 'russia', label: t('compare.russia') }
    : countries.find((c) => c.key === countryKey) || null;

  const resetCountry = () => {
    setCountryKey(null);
    setRussiaBranch(null);
    setCountryQuery('');
  };

  const selectCountry = (key) => {
    setCountryKey(key);
    setRussiaBranch(null);
    setCountryQuery('');
  };

  return (
    <div className="overflow-visible rounded-2xl border border-border-subtle bg-surface p-4 shadow-[0_16px_45px_rgba(35,30,16,0.05)] sm:p-5">
      <div className="mb-5 border-b border-border-subtle pb-4">
        <div className="text-[10px] font-mono uppercase tracking-[0.18em] text-champagne">{t('compare.addSeries')}</div>
        <div className="mt-1 text-sm text-text-secondary">
          {t('compare.pickCountryFirst')}
        </div>
      </div>

      {!countryKey && (
        <div>
          <div className="mb-2 text-[10px] font-mono uppercase tracking-[0.2em] text-text-tertiary">
            {t('compare.country')}
          </div>
          <div className={cn(FIELD_CLS, 'mb-3 border-border-subtle focus-within:border-champagne/40')}>
            <Search className="h-4 w-4 shrink-0 text-text-tertiary" />
            <input
              type="text"
              value={countryQuery}
              onChange={(e) => setCountryQuery(e.target.value)}
              placeholder={t('compare.findCountry')}
              aria-label={t('compare.findCountryAria')}
              className="min-w-0 flex-1 bg-transparent text-sm text-text-primary outline-none placeholder:text-text-tertiary"
            />
            {countryQuery && (
              <button
                type="button"
                aria-label={t('common.clear')}
                onClick={() => setCountryQuery('')}
                className="shrink-0 text-text-tertiary hover:text-text-primary"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            )}
          </div>
          <div className="max-h-80 overflow-auto rounded-xl border border-border-subtle bg-obsidian-light/45">
            {filteredCountries.length === 0 ? (
              <div className="px-4 py-3 text-sm text-text-tertiary">{t('compare.nothingFound')}</div>
            ) : (
              filteredCountries.map((c) => (
                <button
                  key={c.key}
                  type="button"
                  onClick={() => selectCountry(c.key)}
                  className="flex w-full items-center gap-3 px-4 py-2.5 text-left hover:bg-obsidian-lighter transition-colors border-b border-border-subtle/60 last:border-b-0"
                >
                  {c.key === 'russia'
                    ? <Landmark className="h-4 w-4 shrink-0 text-champagne" />
                    : <Globe2 className="h-4 w-4 shrink-0 text-champagne" />}
                  <span className="truncate text-sm text-text-primary">{c.label}</span>
                </button>
              ))
            )}
          </div>
        </div>
      )}

      {countryKey === 'russia' && !russiaBranch && (
        <div>
          <PickerBack label={t('compare.backToCountry')} onClick={resetCountry} />
          <div className="mb-2 text-[10px] font-mono uppercase tracking-[0.2em] text-text-tertiary">
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
              <span className="mt-1 block text-[11px] font-normal text-text-tertiary">
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
                {t('compare.regionsBranch')}
              </span>
              <span className="mt-1 block text-[11px] font-normal text-text-tertiary">
                {t('compare.regionsBranchHint')}
              </span>
            </button>
          </div>
        </div>
      )}

      {countryKey === 'russia' && russiaBranch === 'macro' && (
        <div>
          <PickerBack label={t('compare.backToRussia')} onClick={() => setRussiaBranch(null)} />
          <div className="mb-2 text-[10px] font-mono uppercase tracking-[0.2em] text-text-tertiary">
            {t('compare.macroRussia')}
          </div>
          <div className="rounded-xl border border-border-subtle bg-obsidian-light/45 p-3">
            <AddIndicator
              indicators={indicators}
              selected={selected}
              onAdd={onAdd}
              atCap={atCap}
              capHint={capHint}
              compatibilityFor={compatibilityFor}
            />
          </div>
        </div>
      )}

      {countryKey === 'russia' && russiaBranch === 'regions' && (
        <div>
          <PickerBack label={t('compare.backToRussia')} onClick={() => setRussiaBranch(null)} />
          <div className="mb-2 text-[10px] font-mono uppercase tracking-[0.2em] text-text-tertiary">
            {t('compare.regionalSeries')}
          </div>
          <AddRegionSeries
            selected={selected}
            onAdd={onAdd}
            atCap={atCap}
            capHint={capHint}
            compatibilityFor={compatibilityFor}
          />
          <p className="mt-3 text-xs leading-relaxed text-text-tertiary">
            {t('compare.compareRegionsCta')}{' '}
            <Link to={regionHubPath()} className="text-champagne hover:underline">
              {t('compare.regionsSection')}
            </Link>
          </p>
        </div>
      )}

      {countryKey && countryKey !== 'russia' && selectedCountry && (
        <div>
          <PickerBack label={t('compare.backToCountry')} onClick={resetCountry} />
          <div className="mb-2 text-[10px] font-mono uppercase tracking-[0.2em] text-text-tertiary">
            {t('compare.countryIndicator', { country: selectedCountry.label })}
          </div>
          <div className="rounded-xl border border-border-subtle bg-obsidian-light/45 p-3">
            <AddWorldCountrySeries
              items={worldItems}
              countrySlug={countryKey}
              selected={selected}
              onAdd={onAdd}
              atCap={atCap}
              capHint={capHint}
              compatibilityFor={compatibilityFor}
            />
          </div>
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
      className="fixed inset-0 z-[60] flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm"
      onClick={onClose}
    >
      <div
        className="w-full max-w-md rounded-2xl border border-border-subtle bg-surface shadow-2xl p-6"
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
          <button type="button" onClick={onClose} className="rounded-md p-1 text-text-tertiary hover:text-text-primary" aria-label={t('common.close')}>
            <X className="w-5 h-5" />
          </button>
        </div>
        <p className="text-sm text-text-secondary leading-relaxed mb-5">
          {t('compare.upsellBody')}
        </p>
        <div className="flex items-center gap-3">
          <Link to="/register" onClick={onClose} className="flex-1 text-center rounded-xl bg-champagne text-white text-sm font-semibold py-2.5 hover:bg-champagne-muted transition-colors">
            {t('compare.upsellRegister')}
          </Link>
          <Link to="/login" onClick={onClose} className="flex-1 text-center rounded-xl border border-border-subtle text-text-primary text-sm font-medium py-2.5 hover:border-champagne/40 transition-colors">
            {t('common.login')}
          </Link>
        </div>
      </div>
    </div>
  );
}

function CompareTooltip({ active, payload, label, dateFormat = 'short' }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="glass-surface rounded-xl border border-border-subtle px-4 py-3 shadow-2xl min-w-[220px]">
      <p className="text-xs font-mono text-text-tertiary mb-2">{formatDate(label, dateFormat)}</p>
      {payload.filter((p) => p.value != null).map((p) => (
        <div key={p.dataKey} className="flex items-center justify-between gap-4 mb-1">
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full" style={{ backgroundColor: p.color }} />
            <span className="text-xs text-text-tertiary truncate max-w-[160px]">{p.name}</span>
          </div>
          <span className="text-sm font-mono font-semibold" style={{ color: p.color }}>
            {formatValueWithUnit(p.value, p.payload?.[`${p.dataKey}_unit`] || '%')}
          </span>
        </div>
      ))}
    </div>
  );
}

export default function ComparePage() {
  const t = useT();
  const { locale } = useLocale();
  const [searchParams, setSearchParams] = useSearchParams();
  const [range, setRange] = useState('5y');
  const [scale, setScale] = useState('values');
  const [step, setStep] = useState('auto');
  const [compatibilityMessage, setCompatibilityMessage] = useState('');
  // Панорама окна: сдвиг в точках от правого края ряда («кружочек» как на
  // карточке индикатора — созвон «На правки 13»).
  const [panOffset, setPanOffset] = useState(0);
  const [upsellOpen, setUpsellOpen] = useState(false);
  const [isDragging, setIsDragging] = useState(false);
  const [plotWidth, setPlotWidth] = useState(0);
  const exportRef = useRef(null);
  const chartAreaRef = useRef(null);
  const dragRef = useRef(null);

  useEffect(() => {
    const el = chartAreaRef.current;
    if (!el || typeof ResizeObserver === 'undefined') return undefined;
    const ro = new ResizeObserver((entries) => {
      const w = entries[0]?.contentRect?.width;
      if (w) setPlotWidth(w);
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const { isAuthed } = useAuth();
  const cap = isAuthed ? USER_MAX : GUEST_MAX;
  // Гость никогда не рендерит/экспортирует больше двух рядов — даже если коды
  // переданы напрямую в URL.
  const allCodes = useMemo(() => parseCodes(searchParams), [searchParams]);
  const compatibleCodes = useMemo(() => sanitizeCompareCodes(allCodes), [allCodes]);
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
    track(events.COMPARE_OPEN, { count: codes.length, codes: codes.join(',') || null });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useScrollDepth({ key: 'compare', page: 'compare' });

  // Смена набора рядов → окно к свежим данным.
  useEffect(() => { setPanOffset(0); }, [codes]);

  const { data: indicators } = useIndicators();
  const { data: worldCompareCatalog } = useWorldCompareCatalog();
  const hasWorldSeries = codes.some(isWorldCode);
  const dataSpacesCount = [
    codes.some(isWorldCode),
    codes.some(isRegionCode),
    codes.some((code) => !isWorldCode(code) && !isRegionCode(code)),
  ].filter(Boolean).length;
  const worldCompareItems = worldCompareCatalog?.items || [];
  const compatibilityNote = activeCompatibilityNote(codes);
  const worldMetaByCode = useMemo(
    () => new Map((worldCompareCatalog?.items || []).map((item) => [item.code, {
      frequency: item.frequency,
      conceptSlug: item.concept_slug,
      unit: item.unit,
    }])),
    [worldCompareCatalog],
  );

  useEffect(() => {
    if (hasWorldSeries && step !== 'auto') setStep('auto');
  }, [hasWorldSeries, step]);

  const repByCode = useMemo(() => parseReps(searchParams), [searchParams]);

  const writeCodes = useCallback((next) => {
    const params = new URLSearchParams(searchParams);
    params.delete('a');
    params.delete('b');
    if (next.length) params.set('codes', next.join(','));
    else params.delete('codes');
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

  const addCode = useCallback((code) => {
    if (codes.includes(code)) return;
    if (codes.length >= cap) {
      if (!isAuthed) {
        track(events.COMPARE_LIMIT_HIT, { count: codes.length });
        setUpsellOpen(true);
      }
      return;
    }
    const compatibility = compareCompatibility(codes, code);
    if (!compatibility.allowed) {
      setCompatibilityMessage(compatibility.reason);
      return;
    }
    setCompatibilityMessage('');
    const next = [...codes, code];
    writeCodes(next);
    track(events.COMPARE_ADD, { code, count: next.length });
  }, [codes, cap, isAuthed, writeCodes]);

  const removeCode = useCallback((code) => {
    writeCodes(codes.filter((c) => c !== code));
    track(events.COMPARE_CHANGE, { removed: code });
  }, [codes, writeCodes]);

  // Резолв (индикатор, представление) → {код ряда для загрузки, transform, unit}.
  // Так каждый ряд грузится в выбранном виде (уровень/к пред./к году), а не в
  // нативном. Резолвер (compareRepresentation.js) знает generic-семьи и bespoke.
  const resolved = useMemo(() => codes.map((code) => {
    if (isWorldCode(code)) {
      const meta = worldMetaByCode.get(code);
      const requestedRep = repByCode[code] || REP_LEVEL;
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
    // Региональный ряд (`r:{slug}:{code}`): годовой уровень без представлений —
    // метаданные приходят вместе с данными (__regionMeta), резолвер не нужен.
    if (isRegionCode(code)) {
      return {
        code, ind: null, repId: REP_LEVEL, repLabel: t('common.value'),
        fetchCode: code, transform: null, unit: null, isRegion: true,
      };
    }
    const ind = indicators?.find((x) => x.code === code);
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
  }), [codes, indicators, repByCode, step, worldMetaByCode]);

  const results = useQueries({
    queries: resolved.map((r) => ({
      queryKey: ['indicator-data', r.fetchCode, undefined],
      queryFn: ({ signal }) => (r.isWorld
        ? fetchWorldSeries(r.fetchCode, { signal })
        : r.isRegion
        ? fetchRegionSeries(r.fetchCode, { signal })
        : fetchIndicatorData(r.fetchCode, undefined, { signal })),
      enabled: !!r.fetchCode,
      staleTime: 60 * 60 * 1000,
      gcTime: 30 * 60 * 1000,
    })),
  });

  const series = useMemo(() => resolved.map((r, i) => ({
    code: r.code,
    key: `v${i}`,
    color: PALETTE[i % PALETTE.length],
    ind: r.isWorld
      ? results[i]?.data?.__worldMeta
      : r.isRegion ? results[i]?.data?.__regionMeta : r.ind,
    rep: r.repId,
    repLabel: r.repLabel,
    unit: r.isWorld
      ? (r.repId === REP_LEVEL ? results[i]?.data?.__worldMeta?.unit : r.unit)
      : r.isRegion ? results[i]?.data?.__regionMeta?.unit : r.unit,
    isWorld: r.isWorld,
    transform: r.transform,
    stepDeep: r.stepDeep,
    data: results[i]?.data,
    loading: results[i]?.isLoading,
    error: results[i]?.isError,
  })), [resolved, results]);

  // Разные единицы измерения рядов (после резолва представления). Максимум две
  // оси — при 3+ различных единицах корректно показать нельзя, форсим индекс.
  const distinctUnits = useMemo(() => {
    const seen = [];
    series.forEach((s) => { const u = s.unit || '%'; if (!seen.includes(u)) seen.push(u); });
    return seen;
  }, [series]);
  const forceIndex = distinctUnits.length > 2;
  const indexed = forceIndex || scale === 'index';

  const chartData = useMemo(() => {
    const EMPTY = { rows: [], nonIndexableNames: [], nonIndexableKeys: new Set(), maxPan: 0 };
    if (!series.length) return EMPTY;
    const maps = series.map((s) => {
      const raw = Array.isArray(s.data?.data) ? s.data.data : [];
      const transformed = applyCompareTransform(raw, s.transform);
      // stepDeep: данные уже загружены на нативной частоте нужного шага
      // (реальный alternate_frequencies ряд) — повторная клиентская
      // агрегация не нужна и исказила бы уже готовые годовые/квартальные точки.
      const pts = s.stepDeep || s.isWorld ? transformed : aggregateToStep(transformed, step);
      return new Map(pts.map((p) => [p.date, p.value]));
    });

    const allDates = [...new Set(maps.flatMap((m) => [...m.keys()]))].sort();
    if (!allDates.length) return EMPTY;

    // Окно: длина — из пресета периода, позиция — из слайдера-панорамы.
    const rangeOpt = RANGE_OPTIONS.find((r) => r.key === range);
    let windowLen = allDates.length;
    if (rangeOpt?.months) {
      const cutoff = new Date(allDates[allDates.length - 1]);
      cutoff.setUTCMonth(cutoff.getUTCMonth() - rangeOpt.months);
      const cutoffStr = cutoff.toISOString().slice(0, 10);
      windowLen = allDates.filter((d) => d >= cutoffStr).length || allDates.length;
    }
    const maxPan = Math.max(0, allDates.length - windowLen);
    const pan = Math.min(Math.max(0, panOffset), maxPan);
    const endIdx = allDates.length - pan;
    const startIdx = Math.max(0, endIdx - windowLen);

    const last = series.map(() => null);
    for (let di = 0; di < startIdx; di += 1) {
      const d = allDates[di];
      maps.forEach((m, i) => { if (m.has(d)) last[i] = m.get(d); });
    }
    const dates = allDates.slice(startIdx, endIdx);

    // База приведения: последнее значение до окна, иначе первое значение в окне.
    const base = series.map((_, i) => last[i]);
    for (const d of dates) {
      let allSet = true;
      maps.forEach((m, i) => {
        if (base[i] == null && m.has(d)) base[i] = m.get(d);
        if (base[i] == null) allSet = false;
      });
      if (allSet) break;
    }

    // К общей базе (=100) приводится ТОЛЬКО положительный уровень. Знакопеременные
    // ряды (сальдо, счёт текущих операций, дефицит), %-ряды и представления
    // «к прошлому периоду»/«к году» (это темпы, не уровни — В-12) к базе-100 не
    // приводятся: деление на ~0 → выброс, отрицательная база → переворот знака,
    // «инфляция 5% = 100 пунктов» — смысловой мусор. Такие ряды в режиме общей
    // базы исключаем и подписываем, а не рисуем.
    const indexable = series.map((s, i) => isIndexableBase(base[i], {
      unit: s.unit,
      repId: s.rep,
      values: dates.map((d) => maps[i].get(d)),
    }));
    const nonIndexableNames = indexed
      ? series.filter((_, i) => !indexable[i]).map((s) => s.ind?.name || s.code)
      : [];
    const nonIndexableKeys = new Set(
      indexed ? series.filter((_, i) => !indexable[i]).map((s) => s.key) : [],
    );
    const idxUnit = t('compare.indexUnit');

    // В-13 (CTO-аудит 2026-07-06): значение пишется в строку ТОЛЬКО на датах,
    // где у ряда есть реальная точка. Раньше carry-forward (LOCF) протягивал
    // последнее значение через даты без данных: тултип показывал «значение»
    // там, где наблюдения нет, а линия шла ступенькой. Разрывы между точками
    // соединяет connectNulls на <Line> — честная интерполяция между фактами.
    const rows = dates.map((d) => {
      const row = { date: d };
      maps.forEach((m, i) => {
        if (!m.has(d)) return;
        const v = m.get(d);
        const s = series[i];
        if (indexed) {
          if (indexable[i]) { row[s.key] = rebaseToHundred(v, base[i]); row[`${s.key}_unit`] = idxUnit; }
        } else {
          row[s.key] = v;
          row[`${s.key}_unit`] = s.unit || '%';
        }
      });
      return row;
    });
    return { rows, nonIndexableNames, nonIndexableKeys, maxPan };
  }, [series, range, indexed, step, panOffset]);

  const chartRows = chartData.rows;
  const { nonIndexableNames, nonIndexableKeys, maxPan } = chartData;
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
  const hasError = series.some((s) => s.error);
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
    return pickChartAxisTicks(
      chartRows,
      chartAxisTickBudget(axisW, labelSpec),
      { cadence, plotWidthPx: axisW, formatLabel },
    );
  }, [chartRows, plotWidth, compareDateFmt]);

  // Оси: индекс → одна левая. Значения → группировка по единице: первая
  // единица слева, вторая справа (ряды одной единицы делят общую ось).
  const axisFor = (i) => {
    if (indexed) return 'left';
    const u = series[i]?.unit || '%';
    return distinctUnits[0] === u ? 'left' : 'right';
  };
  const leftUnit = distinctUnits[0];
  const rightUnit = distinctUnits[1];
  const leftColor = series.find((s) => (s.unit || '%') === leftUnit)?.color;
  const rightColor = series.find((s) => (s.unit || '%') === rightUnit)?.color;

  // Перетаскивание графика мышью/пальцем — как на карточке индикатора.
  // Тащим вправо → окно уходит в прошлое (panOffset растёт), влево → к свежим.
  const handlePointerDown = useCallback((e) => {
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
    ? t('compare.capAuthed', { n: USER_MAX })
    : t('compare.capGuest');
  const title = series.length
    ? `${t('compare.badge')}: ${series.map((s) => s.ind?.name || s.code).join(' — ')}`
    : t('compare.title');

  return (
    <div className="max-w-7xl mx-auto px-4 md:px-8 pt-24 md:pt-28 pb-24 md:pb-28">
      <UpsellModal open={upsellOpen} onClose={() => setUpsellOpen(false)} />

      <div className="mb-10 md:mb-12 max-w-4xl">
        <Link
          to="/"
          className="inline-flex items-center gap-2 text-xs font-mono uppercase tracking-widest text-text-tertiary hover:text-champagne transition-colors mb-8 lift-hover group"
        >
          <ArrowLeft className="w-4 h-4 group-hover:-translate-x-1 transition-transform" />
          {t('common.home')}
        </Link>

        <div className="flex items-center gap-3 mb-4">
          <span className="px-3 py-1 rounded-full border border-border-subtle bg-obsidian-light text-[10px] font-mono uppercase tracking-widest text-text-secondary flex items-center gap-2">
            <GitCompare className="w-3 h-3 text-champagne" />
            {t('compare.badge')}
          </span>
        </div>

        <h1 className="text-4xl md:text-5xl lg:text-6xl font-display font-bold tracking-tight mb-4 leading-tight">
          {t('compare.title')}
        </h1>
        <p className="text-sm md:text-base text-text-tertiary max-w-2xl">
          {t('compare.subtitle')}
        </p>
      </div>

      <section data-block="compare-add" className="mb-6">
        <CompareSeriesPicker
          indicators={indicators}
          worldItems={worldCompareItems}
          selected={codes}
          onAdd={addCode}
          atCap={atCap}
          capHint={capHint}
          compatibilityFor={(code) => compareCompatibility(codes, code)}
        />

        {compatibilityMessage && (
          <div className="mt-3 rounded-xl border border-champagne/25 bg-champagne/[0.06] px-3.5 py-2.5 text-xs leading-relaxed text-text-secondary" role="status">
            {compatibilityMessage}
          </div>
        )}

        <div className="mt-3 flex items-center text-xs text-text-tertiary">
          {isAuthed
            ? t('compare.selectedAuthed', { n: codes.length, max: USER_MAX })
            : `${t('compare.selectedGuest', { n: codes.length, max: GUEST_MAX })} `}
          {!isAuthed && (
            <button type="button" onClick={() => { setUpsellOpen(true); track(events.REGISTER_NUDGE_EXPAND, { from: 'compare' }); }} className="ml-1 text-champagne hover:underline">
              {t('compare.wantMore')}
            </button>
          )}
        </div>

        {codes.length > 0 && (
          <div className="mt-4 flex flex-col gap-2">
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
                  className="flex flex-wrap items-center gap-2 rounded-xl border border-border-subtle bg-obsidian-light px-3 py-2"
                >
                  <span className="w-2.5 h-2.5 rounded-full shrink-0" style={{ backgroundColor: s.color }} />
                  <span className="text-sm text-text-primary mr-1">{s.ind?.name || s.code}</span>
                  {reps.length > 1 && (
                    <div className="flex gap-0.5 p-0.5 rounded-lg bg-obsidian-lighter border border-border-subtle">
                      {reps.map((o) => (
                        <button
                          key={o.id}
                          type="button"
                          title={REP_HINT[o.id]}
                          onClick={() => setRep(s.code, o.id)}
                          className={cn(
                            'px-2 py-1 text-[11px] rounded-md transition-colors',
                            s.rep === o.id
                              ? 'bg-champagne/15 text-champagne'
                              : 'text-text-tertiary hover:text-text-secondary',
                          )}
                        >
                          {o.label}
                        </button>
                      ))}
                    </div>
                  )}
                  <button type="button" onClick={() => removeCode(s.code)} className="ml-auto text-text-tertiary hover:text-text-primary" aria-label={t('common.remove')}>
                    <X className="w-4 h-4" />
                  </button>
                </div>
              );
            })}
          </div>
        )}
        {dataSpacesCount > 1 && compatibilityNote && (
          <div className="mt-3 rounded-xl border border-champagne/20 bg-champagne/[0.06] px-3.5 py-2.5 text-xs leading-relaxed text-text-secondary">
            {compatibilityNote}
          </div>
        )}
      </section>

      {hasError && (
        <div className="mb-6 rounded-2xl border border-champagne/35 bg-warn-surface px-4 py-4 text-sm shadow-md" role="alert">
          <p className="text-text-primary">
            <span className="font-semibold">{t('compare.loadPartial')}</span>{' '}
            {t('compare.loadPartialHint')}
          </p>
        </div>
      )}

      <section data-block="compare-chart" className="mb-8">
        <div className="flex items-center gap-4 border-b border-border-subtle pb-4 mb-6 flex-wrap">
          <Activity className="w-4 h-4 text-champagne" />
          <span className="text-[11px] font-mono uppercase tracking-widest text-text-tertiary">{t('compare.periodLabel')}</span>
          <div className="flex gap-1 p-1 rounded-xl bg-obsidian-lighter border border-border-subtle">
            {RANGE_OPTIONS.map((opt) => (
              <button
                key={opt.key}
                onClick={() => { setRange(opt.key); setPanOffset(0); track(events.COMPARE_RANGE, { range: opt.key }); }}
                className={cn(
                  'px-3 py-1.5 text-xs font-medium rounded-lg transition-all duration-200',
                  range === opt.key ? 'bg-champagne/15 text-champagne' : 'text-text-tertiary hover:text-text-secondary',
                )}
              >
                {t(opt.labelKey)}
              </button>
            ))}
          </div>

          <span
            className="text-[11px] font-mono uppercase tracking-widest text-text-tertiary md:ml-4"
            title={t('compare.stepTitle')}
          >
            {t('compare.stepLabel')}
          </span>
          <div className="flex gap-1 p-1 rounded-xl bg-obsidian-lighter border border-border-subtle">
            {STEP_OPTIONS.map((opt) => (
              <button
                key={opt.key}
                disabled={hasWorldSeries && opt.key !== 'auto'}
                onClick={() => { setStep(opt.key); setPanOffset(0); track(events.COMPARE_RANGE, { step: opt.key }); }}
                title={hasWorldSeries && opt.key !== 'auto' ? t('compare.worldOfficialOnly') : undefined}
                className={cn(
                  'px-3 py-1.5 text-xs font-medium rounded-lg transition-all duration-200',
                  step === opt.key ? 'bg-champagne/15 text-champagne' : 'text-text-tertiary hover:text-text-secondary',
                  hasWorldSeries && opt.key !== 'auto' && 'cursor-not-allowed opacity-45 hover:text-text-tertiary',
                )}
              >
                {t(opt.labelKey)}
              </button>
            ))}
          </div>

          <span className="text-[11px] font-mono uppercase tracking-widest text-text-tertiary md:ml-4">{t('compare.scaleLabel')}</span>
          <div className="flex gap-1 p-1 rounded-xl bg-obsidian-lighter border border-border-subtle">
            {SCALE_OPTIONS.map((opt) => {
              const disabled = forceIndex && opt.key === 'values';
              return (
                <button
                  key={opt.key}
                  disabled={disabled}
                  onClick={() => { setScale(opt.key); track(events.COMPARE_RANGE, { scale: opt.key }); }}
                  title={disabled ? t('compare.indexOnlyUnits') : undefined}
                  className={cn(
                    'px-3 py-1.5 text-xs font-medium rounded-lg transition-all duration-200',
                    (indexed ? opt.key === 'index' : range && scale === opt.key && !forceIndex)
                      ? 'bg-champagne/15 text-champagne' : 'text-text-tertiary hover:text-text-secondary',
                    disabled && 'opacity-40 cursor-not-allowed',
                  )}
                >
                  {t(opt.labelKey)}
                </button>
              );
            })}
          </div>

          <button
            type="button"
            onClick={handleExport}
            disabled={!hasData}
            className={cn(
              'ml-auto flex items-center gap-1.5 px-3 py-1.5 rounded-lg border text-xs font-mono uppercase tracking-wider transition-colors',
              hasData ? 'border-border-subtle text-text-tertiary hover:text-champagne hover:border-champagne/30' : 'border-border-subtle/50 text-text-tertiary/40 cursor-not-allowed',
            )}
            title={t('compare.downloadChart')}
          >
            <ImageDown className="w-3.5 h-3.5" />
            {t('compare.imageButton')}
          </button>
        </div>

        {forceIndex && (
          <p className="-mt-3 mb-6 text-xs text-text-tertiary">
            {t('compare.forceIndexHint')}
          </p>
        )}

        {loading ? (
          <ChartSkeleton />
        ) : !hasData ? (
          <div className="h-96 rounded-[2rem] bg-surface border border-border-subtle border-dashed flex flex-col items-center justify-center text-text-tertiary p-8">
            <GitCompare className="w-10 h-10 mb-4 opacity-20" />
            <p className="text-sm text-center max-w-md">
              {codes.length === 0
                ? t('compare.emptyAdd')
                : t('compare.emptyData')}
            </p>
          </div>
        ) : (
          <div ref={exportRef} className="rounded-[2rem] bg-surface border border-border-subtle p-4 md:p-6">
            <h2 className="text-center text-lg md:text-xl font-display font-bold text-text-primary mb-1">
              {title}
            </h2>
            <p className="text-center text-xs text-text-tertiary mb-4">
              {indexed
                ? t('compare.hintIndex')
                : t('compare.hintValues')}
              {` ${t('compare.periodLabel')}: ${t(RANGE_OPTIONS.find((r) => r.key === range)?.labelKey || 'compare.range.all').toLowerCase()}`}
            </p>

            <div className="mb-4 flex flex-wrap items-center justify-center gap-x-6 gap-y-2 text-xs font-mono border-b border-border-subtle pb-4">
              {series.map((s, i) => {
                const dropped = nonIndexableKeys.has(s.key);
                return (
                  <span key={s.code} className={cn('flex items-center gap-2', dropped && 'opacity-40')}>
                    <span className="w-3 h-0.5 rounded-full" style={{ backgroundColor: s.color }} />
                    <span style={{ color: s.color }}>{s.ind?.name || s.code}</span>
                    <span className="text-text-tertiary">
                      ({s.repLabel}{dropped
                        ? t('compare.notRebased')
                        : indexed
                          ? t('compare.start100')
                          : `, ${unitSuffix(s.unit)}${s.ind?.frequency ? `, ${freqLabel(s.ind.frequency, t)}` : ''}, ${axisFor(i) === 'left' ? t('compare.axisLeft') : t('compare.axisRight')}`})
                    </span>
                  </span>
                );
              })}
            </div>

            {nonIndexableNames.length > 0 && (
              <p className="mb-4 -mt-1 text-center text-[11px] text-text-tertiary">
              {t('compare.nonIndexableNote', { names: nonIndexableNames.join(', ') })}
              </p>
            )}

            <div
              ref={chartAreaRef}
              onPointerDown={handlePointerDown}
              onPointerMove={handlePointerMove}
              onPointerUp={handlePointerUp}
              onPointerCancel={handlePointerUp}
              className={cn(
                'relative rounded-2xl',
                maxPan > 0 && (isDragging ? 'cursor-grabbing select-none' : 'cursor-grab'),
              )}
              style={{ touchAction: 'pan-y' }}
            >
              {/* Бренд на экране; в PNG зарегистрированным не попадает
                  (data-no-export + watermark:false в exportNodeToPng). */}
              <div
                aria-hidden="true"
                data-no-export="true"
                className="pointer-events-none absolute left-1/2 top-1/2 z-10 -translate-x-1/2 -translate-y-1/2 -rotate-6 select-none whitespace-nowrap text-3xl font-display font-bold tracking-[0.18em] text-text-primary opacity-[0.055] md:text-5xl"
              >
                forecasteconomy.com
              </div>
              <ResponsiveContainer width="100%" height={480}>
                <ComposedChart data={chartRows} margin={{ top: 10, right: 20, bottom: 44, left: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" vertical={false} />
                  <XAxis
                    dataKey="date"
                    tickFormatter={(d) => formatChartAxisDate(d, compareDateFmt, { multiYear: true })}
                    tick={{ fill: 'rgba(0,0,0,0.45)', fontSize: 10, fontFamily: 'monospace' }}
                    axisLine={{ stroke: 'rgba(0,0,0,0.12)' }}
                    tickLine={false}
                    ticks={xTicks}
                    interval={0}
                    tickMargin={8}
                    height={36}
                    label={{ value: t('compare.periodLabel'), position: 'insideBottom', offset: -2, fill: 'rgba(0,0,0,0.5)', fontSize: 11, fontFamily: 'monospace' }}
                  />
                  <YAxis
                    yAxisId="left"
                    tick={{ fill: indexed ? 'rgba(0,0,0,0.45)' : leftColor, fontSize: 10, fontFamily: 'monospace' }}
                    axisLine={false}
                    tickLine={false}
                    width={60}
                    tickFormatter={(v) => (indexed ? formatAxisTick(v, 0) : formatAxisTick(v, unitDigits(leftUnit)))}
                  />
                  {!indexed && distinctUnits.length > 1 && (
                    <YAxis
                      yAxisId="right"
                      orientation="right"
                      tick={{ fill: rightColor, fontSize: 10, fontFamily: 'monospace' }}
                      axisLine={false}
                      tickLine={false}
                      width={60}
                      tickFormatter={(v) => formatAxisTick(v, unitDigits(rightUnit))}
                    />
                  )}
                  <Tooltip content={<CompareTooltip dateFormat={compareDateFmt} />} cursor={{ stroke: 'rgba(0,0,0,0.12)' }} />
                  {series.map((s, i) => (
                    <Line
                      key={s.key}
                      yAxisId={axisFor(i)}
                      type="monotone"
                      dataKey={s.key}
                      name={s.ind?.name || s.code}
                      stroke={s.color}
                      strokeWidth={2}
                      dot={false}
                      connectNulls
                      isAnimationActive={false}
                    />
                  ))}
                </ComposedChart>
              </ResponsiveContainer>
            </div>

            {/* Панорама окна по всей истории — как на карточке индикатора. */}
            {maxPan > 0 && (
              <div className="px-2 mt-2" data-no-export="true">
                <input
                  type="range"
                  min={0}
                  max={maxPan}
                  value={maxPan - Math.min(panOffset, maxPan)}
                  onChange={(e) => setPanOffset(maxPan - Number(e.target.value))}
                  aria-label={t('compare.panAria')}
                  className="w-full h-1.5 appearance-none bg-obsidian-lighter rounded-full
                    [&::-webkit-slider-thumb]:appearance-none
                    [&::-webkit-slider-thumb]:w-4 [&::-webkit-slider-thumb]:h-4
                    [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-champagne
                    [&::-webkit-slider-thumb]:cursor-pointer [&::-webkit-slider-thumb]:shadow-md
                    [&::-moz-range-thumb]:w-4 [&::-moz-range-thumb]:h-4
                    [&::-moz-range-thumb]:rounded-full [&::-moz-range-thumb]:bg-champagne
                    [&::-moz-range-thumb]:cursor-pointer [&::-moz-range-thumb]:border-0"
                />
                <div className="flex justify-between text-[10px] font-mono text-text-tertiary mt-1">
                  <span>{chartRows[0] ? formatDate(chartRows[0].date, compareDateFmt) : ''}</span>
                  <span className="hidden sm:inline text-text-tertiary/70 normal-case">
                    {t('compare.panHint')}
                  </span>
                  <span>{chartRows.length ? formatDate(chartRows[chartRows.length - 1].date, compareDateFmt) : ''}</span>
                </div>
              </div>
            )}
          </div>
        )}
      </section>

      {hasData && analysisSummary.metrics.some((metric) => metric.last) && (
        <section data-block="compare-analysis" className="rounded-[2rem] border border-border-subtle bg-surface p-5 shadow-[0_16px_45px_rgba(35,30,16,0.05)] md:p-7">
          <div className="mb-5 flex flex-col gap-2 border-b border-border-subtle pb-4 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <div className="text-[10px] font-mono uppercase tracking-[0.18em] text-champagne">
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

          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            {analysisSummary.metrics.filter((metric) => metric.last).map((metric) => {
              const displayUnit = indexed ? t('compare.points') : (metric.item.unit || '%');
              return (
                <div key={metric.item.code} className="rounded-2xl border border-border-subtle bg-obsidian-light p-4">
                  <div className="flex items-start gap-2">
                    <span className="mt-1 h-2.5 w-2.5 shrink-0 rounded-full" style={{ backgroundColor: metric.item.color }} />
                    <div className="min-w-0 text-sm font-medium leading-5 text-text-primary">
                      {metric.item.ind?.name || metric.item.code}
                    </div>
                  </div>
                  <div className="mt-4 grid grid-cols-2 gap-3">
                    <div>
                      <div className="text-[10px] uppercase tracking-wide text-text-tertiary">{t('compare.analysis.last')}</div>
                      <div className="mt-1 font-mono text-lg font-semibold text-text-primary">
                        {formatValueWithUnit(metric.last.value, displayUnit)}
                      </div>
                    </div>
                    <div>
                      <div className="text-[10px] uppercase tracking-wide text-text-tertiary">{t('compare.analysis.change')}</div>
                      <div className={cn(
                        'mt-1 font-mono text-lg font-semibold',
                        metric.change > 0 ? 'text-positive' : metric.change < 0 ? 'text-negative' : 'text-text-primary',
                      )}>
                        {metric.change > 0 ? '+' : ''}
                        {formatValueWithUnit(metric.change, displayUnit)}
                      </div>
                    </div>
                  </div>
                  <div className="mt-3 flex items-center justify-between border-t border-border-subtle pt-2.5 font-mono text-[10px] text-text-tertiary">
                    <span>{formatDate(metric.first.date, compareDateFmt)} → {formatDate(metric.last.date, compareDateFmt)}</span>
                    <span>{t('compare.analysis.pointsCount', { n: metric.points.length })}</span>
                  </div>
                </div>
              );
            })}
          </div>

          {analysisSummary.correlations.length > 0 && (
            <div className="mt-5 rounded-2xl border border-champagne/15 bg-champagne/[0.05] p-4">
              <div className="flex items-center gap-2 text-xs font-semibold text-text-primary">
                <Sparkles size={14} className="text-champagne" />
                {t('compare.analysis.sync')}
              </div>
              <div className="mt-3 grid gap-2 sm:grid-cols-2">
                {analysisSummary.correlations.map((result) => (
                  <div key={result.item.code} className="flex items-center justify-between gap-3 rounded-xl bg-white/65 px-3 py-2.5">
                    <span className="min-w-0 truncate text-xs text-text-secondary">
                      {result.item.ind?.name || result.item.code}
                    </span>
                    <span className="shrink-0 font-mono text-sm font-semibold text-text-primary">
                      r = {result.value.toFixed(2)}
                    </span>
                  </div>
                ))}
              </div>
              <p className="mt-3 text-[10px] leading-4 text-text-tertiary">
                {t('compare.analysis.pearson', {
                  counts: analysisSummary.correlations.map((item) => item.observations).join(', '),
                })}
              </p>
            </div>
          )}
        </section>
      )}
    </div>
  );
}
