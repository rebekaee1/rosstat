import { useState, useMemo, useCallback, useEffect, useRef } from 'react';
import { useSearchParams, Link } from 'react-router-dom';
import { useQueries } from '@tanstack/react-query';
import {
  ResponsiveContainer, ComposedChart, Line, XAxis, YAxis,
  Tooltip, CartesianGrid,
} from 'recharts';
import {
  ArrowLeft, Activity, GitCompare, Search, X, Plus, ImageDown, Sparkles,
  Landmark, MapPin, Check, ChevronDown,
} from 'lucide-react';
import { useIndicators } from '../lib/hooks';
import { fetchIndicatorData } from '../lib/api';
import api from '../lib/api';
import { useRegionsLanding, useRegionsCatalog } from '../lib/regionsApi';
import { useAuth } from '../context/authContext';
import {
  formatDate, formatChartAxisDate, formatAxisTick, formatValueWithUnit,
  unitSuffix, unitDigits, cn, pickChartAxisTicks,
} from '../lib/format';
import useDocumentMeta from '../lib/useMeta';
import { ChartSkeleton } from '../components/Skeleton';
import { track, events } from '../lib/track';
import useSearchTracking from '../lib/useSearchTracking';
import { exportNodeToPng } from '../lib/chartImage';
import useScrollDepth from '../lib/useScrollDepth';
import {
  REP_LEVEL, REP_ORDER, compareRepresentationsFor, resolveCompareSeries,
  applyCompareTransform, isIndexableBase, rebaseToHundred,
} from '../lib/compareRepresentation';

const RANGE_OPTIONS = [
  { key: '3y', label: '3 года', months: 36 },
  { key: '5y', label: '5 лет', months: 60 },
  { key: '10y', label: '10 лет', months: 120 },
  { key: 'all', label: 'Все', months: null },
];

// До 10 рядов — палитра различимых цветов (тёмный фон карточки графика).
const PALETTE = [
  '#d4a574', '#7dd3fc', '#86efac', '#f0abfc', '#fca5a5',
  '#fcd34d', '#a5b4fc', '#5eead4', '#fdba74', '#cbd5e1',
];

// «Общая база» вместо «Индекс», чтобы не путать со ЗНАЧЕНИЕМ представления
// «Индекс» (уровень индекса цен ИПЦ/ИЦП) у отдельного ряда — это разные вещи.
const SCALE_OPTIONS = [
  { key: 'values', label: 'Исходные значения' },
  { key: 'index', label: 'Общая база (=100)' },
];

const GUEST_MAX = 2;
const USER_MAX = 10;

// Шаг временной сетки: месячный ряд рядом с годовым выглядит «лесенкой» —
// приведение к общему шагу усредняет значения за период (созвон «На правки 13»).
const STEP_OPTIONS = [
  { key: 'auto', label: 'Авто' },
  { key: 'month', label: 'Месяц' },
  { key: 'quarter', label: 'Квартал' },
  { key: 'year', label: 'Год' },
];

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
  daily: 'ежедневно',
  weekly: 'еженедельно',
  monthly: 'ежемесячно',
  quarterly: 'ежеквартально',
  annual: 'ежегодно',
  yearly: 'ежегодно',
};

function freqLabel(freq) {
  return FREQ_LABEL[freq] || freq || '';
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
    const [code, rep] = pair.split(':');
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
      category: 'Регионы',
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
function ComboSelect({ groups, value, onChange, placeholder, searchPlaceholder, ariaLabel, disabled, trackContext }) {
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
            aria-label="Очистить"
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
            <div className="px-4 py-3 text-sm text-text-tertiary">Ничего не найдено</div>
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
function AddRegionSeries({ selected, onAdd, atCap, capHint }) {
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
      items: s.indicators.map((i) => ({ value: i.code, label: i.name })),
    }));
  }, [catalog.data]);

  const code = regionSlug && indCode ? `r:${regionSlug}:${indCode}` : null;
  const already = code && selected.includes(code);
  const canAdd = code && !already && !atCap;

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
        title="Добавить региональный индикатор"
        hint="Регион + показатель — например, зарплата в вашем регионе"
      />
      <div className="flex flex-col gap-2">
        <ComboSelect
          groups={regionGroups}
          value={regionSlug}
          onChange={setRegionSlug}
          ariaLabel="Регион"
          placeholder="Выберите или найдите регион…"
          searchPlaceholder="Название региона…"
          disabled={atCap}
          trackContext="compare-region"
        />
        <ComboSelect
          groups={indicatorGroups}
          value={indCode}
          onChange={setIndCode}
          ariaLabel="Показатель региона"
          placeholder="Выберите или найдите показатель…"
          searchPlaceholder="Название показателя…"
          disabled={atCap || !regionSlug}
          trackContext="compare-region-indicator"
        />
        <button
          type="button"
          disabled={!canAdd}
          onClick={handleAdd}
          title={atCap ? capHint : (already ? 'Этот ряд уже добавлен' : undefined)}
          className={cn(
            'inline-flex items-center justify-center gap-1.5 rounded-lg px-3 py-2 text-sm font-medium transition-colors',
            canAdd
              ? 'bg-champagne/15 text-champagne hover:bg-champagne/25'
              : 'bg-obsidian-lighter text-text-tertiary cursor-not-allowed',
          )}
        >
          <Plus className="h-3.5 w-3.5" />
          {already ? 'Уже добавлен' : 'Добавить региональный ряд'}
        </button>
      </div>
    </div>
  );
}

function AddIndicator({ indicators, selected, onAdd, atCap, capHint }) {
  const [query, setQuery] = useState('');
  const [openList, setOpenList] = useState(false);
  // Директория сравнения: показываем ВСЕ показатели (минус уже выбранные),
  // список скроллится (`max-h-80 overflow-auto`). Жёсткого «топ-8» нет —
  // листать можно весь каталог (звонок 2026-06-25). Любой новый индикатор
  // приходит из API и попадает сюда автоматически. Поиск идёт и по
  // seo_keywords (синонимы/корни), как в основном поиске.
  const results = useMemo(() => {
    const q = query.trim().toLowerCase();
    const pool = (indicators || []).filter((i) => !selected.includes(i.code));
    if (!q) return pool;
    return pool.filter((i) => {
      const hay = `${i.name || ''} ${i.name_en || ''} ${i.category || ''} ${i.code || ''} ${i.seo_keywords || ''}`.toLowerCase();
      return hay.includes(q);
    });
  }, [indicators, selected, query]);

  // Спрос-аналитика поиска сравнения (как в основном поиске): фиксируем
  // введённый запрос с числом результатов через debounce. Запрос с 0
  // результатов = карта пробелов каталога. Сырые keystroke'и не шлём.
  const resultsCount = results.length;
  useEffect(() => {
    const q = query.trim();
    if (q.length < 2) return undefined;
    const t = setTimeout(() => {
      track(events.COMPARE_SEARCH, { q: q.slice(0, 40), results: resultsCount });
    }, 900);
    return () => clearTimeout(t);
  }, [query, resultsCount]);

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
          placeholder={atCap ? capHint : 'Найдите или выберите макроиндикатор…'}
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

function UpsellModal({ open, onClose }) {
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
            <h2 className="text-lg font-display font-bold text-text-primary">Сравнивайте до 10 показателей</h2>
          </div>
          <button type="button" onClick={onClose} className="rounded-md p-1 text-text-tertiary hover:text-text-primary" aria-label="Закрыть">
            <X className="w-5 h-5" />
          </button>
        </div>
        <p className="text-sm text-text-secondary leading-relaxed mb-5">
          Гость может сравнить до двух показателей. Зарегистрируйтесь бесплатно —
          добавляйте до 10 рядов на один график, включая региональные, и скачивайте
          данные и изображения без ограничений.
        </p>
        <div className="flex items-center gap-3">
          <Link to="/register" onClick={onClose} className="flex-1 text-center rounded-xl bg-champagne text-white text-sm font-semibold py-2.5 hover:bg-champagne-muted transition-colors">
            Зарегистрироваться
          </Link>
          <Link to="/login" onClick={onClose} className="flex-1 text-center rounded-xl border border-border-subtle text-text-primary text-sm font-medium py-2.5 hover:border-champagne/40 transition-colors">
            Войти
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
  const [searchParams, setSearchParams] = useSearchParams();
  const [range, setRange] = useState('5y');
  const [scale, setScale] = useState('values');
  const [step, setStep] = useState('auto');
  // Панорама окна: сдвиг в точках от правого края ряда («кружочек» как на
  // карточке индикатора — созвон «На правки 13»).
  const [panOffset, setPanOffset] = useState(0);
  const [upsellOpen, setUpsellOpen] = useState(false);
  const [isDragging, setIsDragging] = useState(false);
  const exportRef = useRef(null);
  const chartAreaRef = useRef(null);
  const dragRef = useRef(null);

  const { isAuthed } = useAuth();
  const cap = isAuthed ? USER_MAX : GUEST_MAX;
  // Гость никогда не рендерит/экспортирует больше двух рядов — даже если коды
  // переданы напрямую в URL.
  const allCodes = useMemo(() => parseCodes(searchParams), [searchParams]);
  const codes = useMemo(
    () => (isAuthed ? allCodes : allCodes.slice(0, GUEST_MAX)),
    [allCodes, isAuthed],
  );

  useDocumentMeta({
    title: 'Сравнение индикаторов',
    description: 'Сравнивайте макроэкономические индикаторы России на одном графике — до 10 рядов.',
    path: '/compare',
  });

  useEffect(() => {
    track(events.COMPARE_OPEN, { count: codes.length, codes: codes.join(',') || null });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useScrollDepth({ key: 'compare', page: 'compare' });

  // Смена набора рядов → окно к свежим данным.
  useEffect(() => { setPanOffset(0); }, [codes]);

  const { data: indicators } = useIndicators();

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
      const kept = rawRep.split(',').filter((pair) => next.includes(pair.split(':')[0]));
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
    // Региональный ряд (`r:{slug}:{code}`): годовой уровень без представлений —
    // метаданные приходят вместе с данными (__regionMeta), резолвер не нужен.
    if (isRegionCode(code)) {
      return {
        code, ind: null, repId: REP_LEVEL, repLabel: 'Значение',
        fetchCode: code, transform: null, unit: null, isRegion: true,
      };
    }
    const ind = indicators?.find((x) => x.code === code);
    const repId = repByCode[code] || REP_LEVEL;
    const spec = resolveCompareSeries(ind || { code }, repId)
      || { code, transform: null, unit: ind?.unit, repId: REP_LEVEL, label: 'Значение' };
    return {
      code, ind, repId: spec.repId, repLabel: spec.label,
      fetchCode: spec.code, transform: spec.transform, unit: spec.unit,
    };
  }), [codes, indicators, repByCode]);

  const results = useQueries({
    queries: resolved.map((r) => ({
      queryKey: ['indicator-data', r.fetchCode, undefined],
      queryFn: ({ signal }) => (r.isRegion
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
    ind: r.isRegion ? results[i]?.data?.__regionMeta : r.ind,
    rep: r.repId,
    repLabel: r.repLabel,
    unit: r.isRegion ? results[i]?.data?.__regionMeta?.unit : r.unit,
    transform: r.transform,
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
      const pts = aggregateToStep(applyCompareTransform(raw, s.transform), step);
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
    // ряды (сальдо, счёт текущих операций, дефицит) и %-приросты (могут пересекать
    // ноль) к базе-100 не приводятся: деление на ~0 → выброс, отрицательная база →
    // переворот знака. Такие ряды в режиме общей базы исключаем и подписываем, а не
    // рисуем мусором.
    const indexable = series.map((_, i) => isIndexableBase(base[i]));
    const nonIndexableNames = indexed
      ? series.filter((_, i) => !indexable[i]).map((s) => s.ind?.name || s.code)
      : [];
    const nonIndexableKeys = new Set(
      indexed ? series.filter((_, i) => !indexable[i]).map((s) => s.key) : [],
    );
    const idxUnit = 'пунктов (старт = 100)';

    const rows = dates.map((d) => {
      const row = { date: d };
      maps.forEach((m, i) => {
        if (m.has(d)) last[i] = m.get(d);
        if (last[i] == null) return;
        const s = series[i];
        if (indexed) {
          if (indexable[i]) { row[s.key] = rebaseToHundred(last[i], base[i]); row[`${s.key}_unit`] = idxUnit; }
        } else {
          row[s.key] = last[i];
          row[`${s.key}_unit`] = s.unit || '%';
        }
      });
      return row;
    });
    return { rows, nonIndexableNames, nonIndexableKeys, maxPan };
  }, [series, range, indexed, step, panOffset]);

  const chartRows = chartData.rows;
  const { nonIndexableNames, nonIndexableKeys, maxPan } = chartData;
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

  // Равномерные подписи оси X (включая первую и последнюю дату) — без
  // «разрыва» перед последним тиком (созвон «На правки 13»).
  const xTicks = useMemo(
    () => pickChartAxisTicks(chartRows, 7),
    [chartRows],
  );

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

  const handleExport = async () => {
    if (!hasData) return;
    // Водяной знак «forecasteconomy.com» — на всех выгрузках, для гостей и
    // зарегистрированных (решение владельца 2026-07-02).
    const ok = await exportNodeToPng(exportRef.current, {
      filename: `compare_${codes.join('-').replace(/:/g, '_') || 'chart'}.png`,
      watermark: true,
    }).catch(() => false);
    if (ok) {
      track(events.COMPARE_IMAGE_DOWNLOAD, { count: codes.length, watermark: true, authed: isAuthed });
    } else {
      track(events.COMPARE_IMAGE_BLOCKED, { count: codes.length });
    }
  };

  const atCap = codes.length >= cap;
  const capHint = isAuthed
    ? `Максимум ${USER_MAX} показателей`
    : 'Хотите сравнить больше двух индикаторов — зарегистрируйтесь';
  const title = series.length
    ? `Сравнение: ${series.map((s) => s.ind?.name || s.code).join(' — ')}`
    : 'Сравнение показателей';

  return (
    <div className="max-w-7xl mx-auto px-4 md:px-8 pt-24 md:pt-28 pb-24 md:pb-28">
      <UpsellModal open={upsellOpen} onClose={() => setUpsellOpen(false)} />

      <div className="mb-10 md:mb-12 max-w-4xl">
        <Link
          to="/"
          className="inline-flex items-center gap-2 text-xs font-mono uppercase tracking-widest text-text-tertiary hover:text-champagne transition-colors mb-8 lift-hover group"
        >
          <ArrowLeft className="w-4 h-4 group-hover:-translate-x-1 transition-transform" />
          Главная
        </Link>

        <div className="flex items-center gap-3 mb-4">
          <span className="px-3 py-1 rounded-full border border-border-subtle bg-obsidian-light text-[10px] font-mono uppercase tracking-widest text-text-secondary flex items-center gap-2">
            <GitCompare className="w-3 h-3 text-champagne" />
            Сравнение
          </span>
        </div>

        <h1 className="text-4xl md:text-5xl lg:text-6xl font-display font-bold tracking-tight mb-4 leading-tight">
          Сравнение показателей
        </h1>
        <p className="text-sm md:text-base text-text-tertiary max-w-2xl">
          На один график можно вывести и макроэкономические индикаторы страны, и
          показатели отдельных регионов — например, сопоставить зарплату в своём
          регионе с инфляцией по России. У каждого ряда выбирается представление
          (значение, к прошлому периоду, к году), а если единицы измерения
          различаются, режим «Общая база» приводит все ряды к единой точке
          отсчёта — сто в начале периода, на графике остаётся только динамика.
        </p>
      </div>

      <section data-block="compare-add" className="mb-6">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 items-start">
          {/* Макроиндикатор: поиск-по-всей-стране, добавление по клику. */}
          <div className="rounded-xl border border-border-subtle bg-surface p-3">
            <AddCardHeader
              icon={Landmark}
              title="Добавить макроиндикатор"
              hint="По стране — инфляция, ВВП, ключевая ставка, безработица…"
            />
            <AddIndicator
              indicators={indicators}
              selected={codes}
              onAdd={addCode}
              atCap={atCap}
              capHint={capHint}
            />
          </div>

          {/* Региональный индикатор: регион + показатель. Тот же визуальный язык. */}
          <AddRegionSeries selected={codes} onAdd={addCode} atCap={atCap} capHint={capHint} />
        </div>

        <div className="mt-3 flex items-center text-xs text-text-tertiary">
          {isAuthed
            ? `Выбрано ${codes.length} из ${USER_MAX}.`
            : `Выбрано ${codes.length} из ${GUEST_MAX} (гость). `}
          {!isAuthed && (
            <button type="button" onClick={() => { setUpsellOpen(true); track(events.REGISTER_NUDGE_EXPAND, { from: 'compare' }); }} className="ml-1 text-champagne hover:underline">
              Хотите больше двух — зарегистрируйтесь →
            </button>
          )}
        </div>

        {codes.length > 0 && (
          <div className="mt-4 flex flex-col gap-2">
            {series.map((s) => {
              const reps = compareRepresentationsFor(s.ind || { code: s.code });
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
                  <button type="button" onClick={() => removeCode(s.code)} className="ml-auto text-text-tertiary hover:text-text-primary" aria-label="Убрать">
                    <X className="w-4 h-4" />
                  </button>
                </div>
              );
            })}
          </div>
        )}
      </section>

      {hasError && (
        <div className="mb-6 rounded-2xl border border-champagne/35 bg-warn-surface px-4 py-4 text-sm shadow-md" role="alert">
          <p className="text-text-primary">
            <span className="font-semibold">Не удалось загрузить часть данных.</span>{' '}
            Попробуйте выбрать другие показатели или обновите страницу.
          </p>
        </div>
      )}

      <section data-block="compare-chart" className="mb-8">
        <div className="flex items-center gap-4 border-b border-border-subtle pb-4 mb-6 flex-wrap">
          <Activity className="w-4 h-4 text-champagne" />
          <span className="text-[11px] font-mono uppercase tracking-widest text-text-tertiary">Период</span>
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
                {opt.label}
              </button>
            ))}
          </div>

          <span
            className="text-[11px] font-mono uppercase tracking-widest text-text-tertiary md:ml-4"
            title="Приведение рядов к общему шагу времени: значения усредняются за месяц, квартал или год"
          >
            Шаг
          </span>
          <div className="flex gap-1 p-1 rounded-xl bg-obsidian-lighter border border-border-subtle">
            {STEP_OPTIONS.map((opt) => (
              <button
                key={opt.key}
                onClick={() => { setStep(opt.key); setPanOffset(0); track(events.COMPARE_RANGE, { step: opt.key }); }}
                className={cn(
                  'px-3 py-1.5 text-xs font-medium rounded-lg transition-all duration-200',
                  step === opt.key ? 'bg-champagne/15 text-champagne' : 'text-text-tertiary hover:text-text-secondary',
                )}
              >
                {opt.label}
              </button>
            ))}
          </div>

          <span className="text-[11px] font-mono uppercase tracking-widest text-text-tertiary md:ml-4">Шкала</span>
          <div className="flex gap-1 p-1 rounded-xl bg-obsidian-lighter border border-border-subtle">
            {SCALE_OPTIONS.map((opt) => {
              const disabled = forceIndex && opt.key === 'values';
              return (
                <button
                  key={opt.key}
                  disabled={disabled}
                  onClick={() => { setScale(opt.key); track(events.COMPARE_RANGE, { scale: opt.key }); }}
                  title={disabled ? 'При 3+ разных единицах доступна только общая база' : undefined}
                  className={cn(
                    'px-3 py-1.5 text-xs font-medium rounded-lg transition-all duration-200',
                    (indexed ? opt.key === 'index' : range && scale === opt.key && !forceIndex)
                      ? 'bg-champagne/15 text-champagne' : 'text-text-tertiary hover:text-text-secondary',
                    disabled && 'opacity-40 cursor-not-allowed',
                  )}
                >
                  {opt.label}
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
            title="Скачать график картинкой"
          >
            <ImageDown className="w-3.5 h-3.5" />
            Картинка
          </button>
        </div>

        {forceIndex && (
          <p className="-mt-3 mb-6 text-xs text-text-tertiary">
            Выбрано 3+ разных единиц измерения — график доступен только в режиме
            «Общая база». Чтобы вернуть исходные значения на общую ось, приведите
            ряды к одному представлению (например, «К году» — тогда все они станут
            процентами).
          </p>
        )}

        {loading ? (
          <ChartSkeleton />
        ) : !hasData ? (
          <div className="h-96 rounded-[2rem] bg-surface border border-border-subtle border-dashed flex flex-col items-center justify-center text-text-tertiary p-8">
            <GitCompare className="w-10 h-10 mb-4 opacity-20" />
            <p className="text-sm text-center max-w-md">
              {codes.length === 0
                ? 'Найдите и добавьте показатели для построения графика.'
                : 'Данные загружаются или отсутствуют для выбранных показателей.'}
            </p>
          </div>
        ) : (
          <div ref={exportRef} className="rounded-[2rem] bg-surface border border-border-subtle p-4 md:p-6">
            <h2 className="text-center text-lg md:text-xl font-display font-bold text-text-primary mb-1">
              {title}
            </h2>
            <p className="text-center text-xs text-text-tertiary mb-4">
              {indexed
                ? 'Приведение к общей базе — 100 в начале периода, единая шкала.'
                : 'Значения в исходных единицах, у каждого ряда своя ось.'}
              {` Период: ${RANGE_OPTIONS.find((r) => r.key === range)?.label.toLowerCase()}`}
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
                        ? ', не приводится к базе'
                        : indexed
                          ? ', старт = 100'
                          : `, ${unitSuffix(s.unit)}${s.ind?.frequency ? `, ${freqLabel(s.ind.frequency)}` : ''}, ${axisFor(i) === 'left' ? 'левая ось' : 'правая ось'}`})
                    </span>
                  </span>
                );
              })}
            </div>

            {nonIndexableNames.length > 0 && (
              <p className="mb-4 -mt-1 text-center text-[11px] text-text-tertiary">
                К общей базе не приводятся знакопеременные и процентные ряды
                ({nonIndexableNames.join(', ')}). Выберите для них представление
                «Значение» либо переключите шкалу на «Исходные значения».
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
              {/* Водяной знак — всегда на экране (как на карточке индикатора):
                  каждый скриншот несёт бренд. Экспорт добавляет ещё тайловый
                  знак из canvas — см. handleExport. */}
              <div
                aria-hidden="true"
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
                    label={{ value: 'Период', position: 'insideBottom', offset: -2, fill: 'rgba(0,0,0,0.5)', fontSize: 11, fontFamily: 'monospace' }}
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
                  aria-label="Позиция окна по времени"
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
                    перетащите график мышью или двигайте ползунок
                  </span>
                  <span>{chartRows.length ? formatDate(chartRows[chartRows.length - 1].date, compareDateFmt) : ''}</span>
                </div>
              </div>
            )}
          </div>
        )}
      </section>
    </div>
  );
}
