import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { ArrowRight, TrendingDown, TrendingUp, Minus } from 'lucide-react';
import api from '../lib/api';
import { formatValue } from '../lib/format';
import { regionPath, regionIndicatorPath, russiaCategoryPath } from '../lib/sitePaths';
import { useRegionsLanding } from '../lib/regionsApi';
import { resolveBrowserLocale } from '../i18n/locale';
import { track, events } from '../lib/track';
import { useLocale, useT } from '../i18n';
import Sparkline from './Sparkline';
import '../styles/r7d-prices.css';

const STORE_KEY = 'fe_r7d_region';

/** Сводка цен: лёгкий эндпоинт; если выпуск бэкенда ещё не доехал, берём профиль России и достаём ходовые позиции. */
async function loadSummary(signal) {
  try {
    return (await api.get('/regions/russia/prices-summary', { signal })).data;
  } catch (e) {
    if (e?.response?.status !== 404) throw e;
    const prof = (await api.get('/regions/russia', { signal })).data;
    const codes = prof.price_headline_codes || [];
    const byCode = {};
    for (const s of prof.sections || []) {
      for (const i of s.indicators || []) if (codes.includes(i.code)) byCode[i.code] = i;
    }
    const items = codes.map((c) => byCode[c]).filter(Boolean).map((i) => ({ ...i, spark: null, yoy_pct: null }));
    return { items, groups: [], total: 0 };
  }
}

function useRussiaPrices() {
  return useQuery({
    queryKey: ['r7d-russia-prices', resolveBrowserLocale()],
    queryFn: ({ signal }) => loadSummary(signal),
    staleTime: 10 * 60 * 1000,
  });
}

/** «рублей за литр» -> { sign: '₽', per: 'за литр' } */
function splitPriceUnit(unit) {
  const u = String(unit || '');
  const m = u.match(/^(?:рублей|рубля|рубль|roubles|rubles)\s*(.*)$/i);
  if (!m) return { sign: '', per: u };
  const per = m[1]
    .replace(/килограмм(?![\p{L}])/iu, 'кг')
    .replace(/штук(?![\p{L}])/iu, 'шт.')
    .replace(/литр(?![\p{L}])/iu, 'л');
  return { sign: '₽', per };
}

function pctChange(a, b) {
  if (a == null || b == null || !b) return null;
  return (a / b - 1) * 100;
}

function signed(p, locale) {
  const s = formatValue(Math.abs(p), Math.abs(p) < 10 ? 1 : 0, locale);
  return `${p > 0 ? '+' : p < 0 ? '−' : ''}${s}\u00a0%`;
}

function Trend({ pct, locale, label }) {
  if (pct == null) return null;
  const flat = Math.abs(pct) < 0.05;
  const Icon = flat ? Minus : pct > 0 ? TrendingUp : TrendingDown;
  return (
    <span className={`r7d-trend${flat ? '' : pct > 0 ? ' r7d-trend--up' : ' r7d-trend--down'}`}>
      <Icon size={13} aria-hidden="true" />
      <span className="r7d-trend__v">{flat ? '0\u00a0%' : signed(pct, locale)}</span>
      <span className="r7d-trend__l">{label}</span>
    </span>
  );
}

function readRegion() {
  if (typeof window === 'undefined') return '';
  try { return window.localStorage.getItem(STORE_KEY) || ''; } catch { return ''; }
}

export default function R7PricesBlock({ limit = 12, surface = 'category', headingLevel = 2 }) {
  const t = useT();
  const { locale } = useLocale();
  const { data, isLoading, isError } = useRussiaPrices();
  const landing = useRegionsLanding();
  const [region, setRegion] = useState(readRegion);
  const [expanded, setExpanded] = useState(false);

  const regions = useMemo(() => {
    const out = [];
    for (const d of landing.data?.districts || []) {
      for (const r of d.regions || []) out.push({ slug: r.slug, name: r.name });
    }
    return out.sort((a, b) => a.name.localeCompare(b.name, locale === 'en' ? 'en' : 'ru'));
  }, [landing.data, locale]);
  const regionName = regions.find((r) => r.slug === region)?.name || '';

  const onRegion = (e) => {
    const v = e.target.value;
    setRegion(v);
    try { window.localStorage.setItem(STORE_KEY, v); } catch { /* приватный режим */ }
    track(events.RELATED_LINK_CLICK, { from: 'r7d-prices', to: v || 'none', surface });
  };

  if (isError) return null;
  const all = (data?.items || []).slice(0, limit);
  if (!isLoading && all.length === 0) return null;
  const FOLD = 6;
  const items = expanded ? all : all.slice(0, FOLD);
  const H = `h${headingLevel}`;
  const month = all[0]?.period_label || '';

  return (
    <section data-block="russia-prices" className="r7d-prices" aria-labelledby={`r7d-title-${surface}`}>
      <div className="r7d-prices__head">
        <div className="min-w-0">
          <H id={`r7d-title-${surface}`} className="r7d-prices__title">{t('r7d.title')}</H>
          <p className="r7d-prices__sub">
            {month ? t('r7d.sub', { month }) : t('r7d.subNoMonth')}
            {' '}
            {surface === 'category' && <a className="r7d-jump" href="#category-list">{t('r7d.jump')}</a>}
            {surface !== 'category' && <Link className="r7d-jump" to={russiaCategoryPath('prices')}>{t('r7d.jumpHub')}</Link>}
          </p>
        </div>
        {regions.length > 0 && (
          <label className="r7d-region">
            <span className="r7d-region__l">{t('r7d.yourRegion')}</span>
            <select className="r7d-region__s" value={region} onChange={onRegion}>
              <option value="">{t('r7d.pickRegion')}</option>
              {regions.map((r) => <option key={r.slug} value={r.slug}>{r.name}</option>)}
            </select>
          </label>
        )}
      </div>

      <ul className="r7d-grid" aria-busy={isLoading || undefined}>
        {isLoading && Array.from({ length: 6 }).map((_, i) => (
          <li key={i} className="r7d-card r7d-card--sk" aria-hidden="true" />
        ))}
        {items.map((it) => {
          const { sign, per } = splitPriceUnit(it.unit);
          const mom = pctChange(it.value, it.prev_value);
          const name = it.short_name || it.name;
          const spark = it.spark && it.spark.length >= 2 ? it.spark : null;
          const last = spark ? spark[spark.length - 1] : 0;
          const sparkTrend = !spark ? 'flat' : last > spark[0] ? 'up' : last < spark[0] ? 'down' : 'flat';
          return (
            <li key={it.code} className="r7d-card">
              <Link
                to={regionIndicatorPath('russia', it.code)}
                className="r7d-card__main fe-press"
                onClick={() => track(events.RELATED_LINK_CLICK, { from: 'r7d-prices', to: it.code, surface })}
              >
                <span className="r7d-card__name">{name}</span>
                <span className="r7d-card__price">
                  <span className="r7d-card__num">{formatValue(it.value, it.value >= 1000 ? 0 : 2, locale)}</span>
                  {sign && <span className="r7d-card__sign">{'\u00a0'}{sign}</span>}
                </span>
                {per && <span className="r7d-card__per">{per}</span>}
                <span className="r7d-card__trends">
                  <Trend pct={it.yoy_pct} locale={locale} label={t('r7d.yoy')} />
                  <Trend pct={it.yoy_pct == null ? mom : null} locale={locale} label={t('r7d.mom')} />
                </span>
                {spark && (
                  <span className="r7d-card__spark" aria-hidden="true">
                    <Sparkline points={spark} trend={sparkTrend} sentiment="neutral" height={34} />
                  </span>
                )}
              </Link>
              {region && (
                <Link
                  to={regionIndicatorPath(region, it.code)}
                  className="r7d-card__region"
                  onClick={() => track(events.RELATED_LINK_CLICK, { from: 'r7d-prices-region', to: region, surface })}
                >
                  <span className="truncate">{t('r7d.inRegion', { name: regionName })}</span>
                  <ArrowRight size={13} aria-hidden="true" />
                </Link>
              )}
            </li>
          );
        })}
      </ul>

      {all.length > FOLD && (
        <button type="button" className="r7d-more fe-press" aria-expanded={expanded} onClick={() => setExpanded((v) => !v)}>
          {expanded ? t('r7d.less') : t('r7d.more', { n: all.length - FOLD })}
        </button>
      )}

      <div className="r7d-prices__foot">
        {data?.groups?.length > 0 && (
          <ul className="r7d-groups" aria-label={t('r7d.groupsLabel')}>
            {data.groups.map((g) => (
              <li key={g.group}>
                <Link to={regionPath('russia')} className="r7d-group fe-press">
                  {g.label}<span className="r7d-group__n">{g.count}</span>
                </Link>
              </li>
            ))}
          </ul>
        )}
        <Link to={regionPath('russia')} className="r7d-all">
          {data?.total > 0 ? t('r7d.allN', { n: data.total }) : t('r7d.all')}
          <ArrowRight size={14} aria-hidden="true" />
        </Link>
      </div>
    </section>
  );
}
