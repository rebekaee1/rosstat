import { useState, useMemo, useCallback, useEffect, useRef } from 'react';
import { useSearchParams, Link } from 'react-router-dom';
import { useQueries } from '@tanstack/react-query';
import {
  ResponsiveContainer, ComposedChart, Line, XAxis, YAxis,
  Tooltip, CartesianGrid,
} from 'recharts';
import {
  ArrowLeft, Activity, GitCompare, Search, X, Plus, ImageDown, Sparkles,
} from 'lucide-react';
import { useIndicators } from '../lib/hooks';
import { fetchIndicatorData } from '../lib/api';
import { useAuth } from '../context/authContext';
import {
  formatDate, formatChartAxisDate, formatAxisTick, formatValueWithUnit,
  unitSuffix, unitDigits, cn, isCpiIndex,
} from '../lib/format';
import useDocumentMeta from '../lib/useMeta';
import { ChartSkeleton } from '../components/Skeleton';
import { track, events } from '../lib/track';
import { exportNodeToPng } from '../lib/chartImage';
import useScrollDepth from '../lib/useScrollDepth';

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

const SCALE_OPTIONS = [
  { key: 'values', label: 'Значения' },
  { key: 'index', label: 'Индекс (старт 100)' },
];

const GUEST_MAX = 2;
const USER_MAX = 10;

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
        'flex items-center gap-2 rounded-xl border bg-surface px-3 py-2.5 transition-colors',
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
          placeholder={atCap ? capHint : 'Найти показатель и добавить…'}
          className="flex-1 bg-transparent text-sm text-text-primary outline-none placeholder:text-text-tertiary disabled:cursor-not-allowed"
        />
      </div>
      {openList && !atCap && results.length > 0 && (
        <div className="absolute z-30 mt-2 w-full max-h-80 overflow-auto rounded-xl border border-border-subtle bg-surface shadow-2xl">
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
          Гость может сравнить до двух показателей и скачать картинку с водяным знаком.
          Зарегистрируйтесь бесплатно — добавляйте до 10 показателей на один график
          и скачивайте изображение без водяного знака.
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
  const [upsellOpen, setUpsellOpen] = useState(false);
  const exportRef = useRef(null);

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

  const { data: indicators } = useIndicators();

  const writeCodes = useCallback((next) => {
    const params = new URLSearchParams(searchParams);
    params.delete('a');
    params.delete('b');
    if (next.length) params.set('codes', next.join(','));
    else params.delete('codes');
    setSearchParams(params, { replace: true });
  }, [searchParams, setSearchParams]);

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

  const results = useQueries({
    queries: codes.map((code) => ({
      queryKey: ['indicator-data', code, undefined],
      queryFn: ({ signal }) => fetchIndicatorData(code, undefined, { signal }),
      enabled: !!code,
      staleTime: 60 * 60 * 1000,
      gcTime: 30 * 60 * 1000,
    })),
  });

  const series = useMemo(() => codes.map((code, i) => ({
    code,
    key: `v${i}`,
    color: PALETTE[i % PALETTE.length],
    ind: indicators?.find((x) => x.code === code),
    data: results[i]?.data,
    loading: results[i]?.isLoading,
    error: results[i]?.isError,
  })), [codes, indicators, results]);

  // >2 рядов невозможно корректно показать в исходных единицах (две оси максимум) —
  // принудительно индекс-режим.
  const forceIndex = codes.length > 2;
  const indexed = forceIndex || scale === 'index';

  const chartData = useMemo(() => {
    if (!series.length) return [];
    const maps = series.map((s) => {
      const points = Array.isArray(s.data?.data) ? s.data.data : [];
      const adj = !indexed && isCpiIndex(s.code);
      return new Map(points.map((p) => [p.date, adj ? p.value - 100 : p.value]));
    });

    const allDates = [...new Set(maps.flatMap((m) => [...m.keys()]))].sort();
    if (!allDates.length) return [];

    const rangeOpt = RANGE_OPTIONS.find((r) => r.key === range);
    let dates = allDates;
    const last = series.map(() => null);

    if (rangeOpt?.months) {
      const lastDate = new Date(allDates[allDates.length - 1]);
      const cutoff = new Date(lastDate);
      cutoff.setUTCMonth(cutoff.getUTCMonth() - rangeOpt.months);
      const cutoffStr = cutoff.toISOString().slice(0, 10);
      for (const d of allDates) {
        if (d >= cutoffStr) break;
        maps.forEach((m, i) => { if (m.has(d)) last[i] = m.get(d); });
      }
      dates = allDates.filter((d) => d >= cutoffStr);
    }

    const base = series.map((_, i) => last[i]);
    if (indexed) {
      for (const d of dates) {
        let allSet = true;
        maps.forEach((m, i) => {
          if (base[i] == null && m.has(d)) base[i] = m.get(d);
          if (base[i] == null) allSet = false;
        });
        if (allSet) break;
      }
    }
    const idxUnit = 'пунктов (старт = 100)';

    return dates.map((d) => {
      const row = { date: d };
      maps.forEach((m, i) => {
        if (m.has(d)) last[i] = m.get(d);
        if (last[i] == null) return;
        const s = series[i];
        if (indexed) {
          if (base[i]) { row[s.key] = (last[i] / base[i]) * 100; row[`${s.key}_unit`] = idxUnit; }
        } else {
          row[s.key] = last[i];
          row[`${s.key}_unit`] = s.ind?.unit || '%';
        }
      });
      return row;
    });
  }, [series, range, indexed]);

  const hasData = chartData.length > 0;
  const loading = series.some((s) => s.loading);
  const hasError = series.some((s) => s.error);
  const compareDateFmt = compareDateFormat(series.map((s) => s.ind));

  // Оси: индекс → одна левая; значения с 1 рядом → левая; с 2 → левая+правая.
  const axisFor = (i) => (indexed ? 'left' : (i === 0 ? 'left' : 'right'));

  const handleExport = async () => {
    if (!hasData) return;
    const watermark = !isAuthed; // гость — с watermark, зарегистрированный — без.
    const ok = await exportNodeToPng(exportRef.current, {
      filename: `compare_${codes.join('-') || 'chart'}.png`,
      watermark,
    }).catch(() => false);
    if (ok) {
      track(events.COMPARE_IMAGE_DOWNLOAD, { count: codes.length, watermark, authed: isAuthed });
    } else {
      track(events.COMPARE_IMAGE_BLOCKED, { count: codes.length });
    }
  };

  const atCap = codes.length >= cap;
  const capHint = isAuthed
    ? `Максимум ${USER_MAX} показателей`
    : 'Хотите сравнить больше двух индикаторов — зарегистрируйтесь';
  const title = series.length
    ? `Сравнение: ${series.map((s) => s.ind?.name || s.code).join(' · ')}`
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
          Найдите показатели по названию и добавьте их на один график. Режим «Индекс»
          приводит ряды к общей базе (100 в начале периода) — так сравнивают динамику
          показателей с разными единицами измерения.
        </p>
      </div>

      <section className="mb-6">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <AddIndicator
            indicators={indicators}
            selected={codes}
            onAdd={addCode}
            atCap={atCap}
            capHint={capHint}
          />
          <div className="flex items-center text-xs text-text-tertiary">
            {isAuthed
              ? `Выбрано ${codes.length} из ${USER_MAX}.`
              : `Выбрано ${codes.length} из ${GUEST_MAX} (гость). `}
            {!isAuthed && (
              <button type="button" onClick={() => { setUpsellOpen(true); track(events.REGISTER_NUDGE_EXPAND, { from: 'compare' }); }} className="ml-1 text-champagne hover:underline">
                Хотите больше двух — зарегистрируйтесь →
              </button>
            )}
          </div>
        </div>

        {codes.length > 0 && (
          <div className="mt-4 flex flex-wrap gap-2">
            {series.map((s) => (
              <span
                key={s.code}
                className="inline-flex items-center gap-2 rounded-full border border-border-subtle bg-obsidian-light px-3 py-1.5 text-xs"
                style={{ color: s.color }}
              >
                <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: s.color }} />
                <span className="text-text-primary">{s.ind?.name || s.code}</span>
                <button type="button" onClick={() => removeCode(s.code)} className="text-text-tertiary hover:text-text-primary" aria-label="Убрать">
                  <X className="w-3.5 h-3.5" />
                </button>
              </span>
            ))}
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

      <section className="mb-8">
        <div className="flex items-center gap-4 border-b border-border-subtle pb-4 mb-6 flex-wrap">
          <Activity className="w-4 h-4 text-champagne" />
          <span className="text-[11px] font-mono uppercase tracking-widest text-text-tertiary">Период</span>
          <div className="flex gap-1 p-1 rounded-xl bg-obsidian-lighter border border-border-subtle">
            {RANGE_OPTIONS.map((opt) => (
              <button
                key={opt.key}
                onClick={() => { setRange(opt.key); track(events.COMPARE_RANGE, { range: opt.key }); }}
                className={cn(
                  'px-3 py-1.5 text-xs font-medium rounded-lg transition-all duration-200',
                  range === opt.key ? 'bg-champagne/15 text-champagne' : 'text-text-tertiary hover:text-text-secondary',
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
                  title={disabled ? 'При 3+ показателях доступен только индекс' : undefined}
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
            title={isAuthed ? 'Скачать картинку без водяного знака' : 'Скачать картинку (с водяным знаком). Без знака — после входа'}
          >
            <ImageDown className="w-3.5 h-3.5" />
            Картинка
          </button>
        </div>

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
                ? 'Индекс относительной динамики — 100 в начале периода, общая шкала'
                : 'Значения в исходных единицах, у каждого ряда своя ось'}
              {` · период: ${RANGE_OPTIONS.find((r) => r.key === range)?.label}`}
            </p>

            <div className="mb-4 flex flex-wrap items-center justify-center gap-x-6 gap-y-2 text-xs font-mono border-b border-border-subtle pb-4">
              {series.map((s, i) => (
                <span key={s.code} className="flex items-center gap-2">
                  <span className="w-3 h-0.5 rounded-full" style={{ backgroundColor: s.color }} />
                  <span style={{ color: s.color }}>{s.ind?.name || s.code}</span>
                  <span className="text-text-tertiary">
                    · {indexed
                      ? 'старт = 100'
                      : `${unitSuffix(s.ind?.unit)}${s.ind?.frequency ? `, ${freqLabel(s.ind.frequency)}` : ''} · ${axisFor(i) === 'left' ? 'левая ось' : 'правая ось'}`}
                  </span>
                </span>
              ))}
            </div>

            <div className="relative rounded-2xl">
              {/* Водяной знак — гостевой тизер: показываем на экране только гостю
                  (его же экспорт получает тайловый знак из canvas). У
                  зарегистрированного и экран, и выгрузка чистые. */}
              {!isAuthed && (
                <div
                  aria-hidden="true"
                  data-no-export="true"
                  className="pointer-events-none absolute left-1/2 top-1/2 z-10 -translate-x-1/2 -translate-y-1/2 -rotate-6 select-none whitespace-nowrap text-3xl font-display font-bold tracking-[0.18em] text-text-primary opacity-[0.055] md:text-5xl"
                >
                  Forecast Economy
                </div>
              )}
              <ResponsiveContainer width="100%" height={480}>
                <ComposedChart data={chartData} margin={{ top: 10, right: 20, bottom: 44, left: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" vertical={false} />
                  <XAxis
                    dataKey="date"
                    tickFormatter={(d) => formatChartAxisDate(d, compareDateFmt, { multiYear: true })}
                    tick={{ fill: 'rgba(0,0,0,0.45)', fontSize: 10, fontFamily: 'monospace' }}
                    axisLine={{ stroke: 'rgba(0,0,0,0.12)' }}
                    tickLine={false}
                    interval="preserveStartEnd"
                    minTickGap={48}
                    tickMargin={8}
                    height={36}
                    label={{ value: 'Период', position: 'insideBottom', offset: -2, fill: 'rgba(0,0,0,0.5)', fontSize: 11, fontFamily: 'monospace' }}
                  />
                  <YAxis
                    yAxisId="left"
                    tick={{ fill: indexed ? 'rgba(0,0,0,0.45)' : series[0]?.color, fontSize: 10, fontFamily: 'monospace' }}
                    axisLine={false}
                    tickLine={false}
                    width={60}
                    tickFormatter={(v) => (indexed ? formatAxisTick(v, 0) : formatAxisTick(v, unitDigits(series[0]?.ind?.unit)))}
                  />
                  {!indexed && series.length > 1 && (
                    <YAxis
                      yAxisId="right"
                      orientation="right"
                      tick={{ fill: series[1]?.color, fontSize: 10, fontFamily: 'monospace' }}
                      axisLine={false}
                      tickLine={false}
                      width={60}
                      tickFormatter={(v) => formatAxisTick(v, unitDigits(series[1]?.ind?.unit))}
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
          </div>
        )}
      </section>
    </div>
  );
}
