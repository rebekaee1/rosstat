/* eslint-disable react-refresh/only-export-components -- рядом с компонентами лежат малые чистые помощники, их проверяет RegionPrices.test.jsx */
// Цены ЕМИСС на странице региона: блок «Цены в регионе» на первом экране и раздел «Цены и тарифы»,
// сгруппированный по смыслу (продукты, ЖКХ, транспорт …). Живые позиции — первыми, снятые Росстатом — в конце группы.
import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { ArrowRight } from 'lucide-react';
import DeltaBadge from '../DeltaBadge';
import { yearDelta } from '../../lib/regionsApi';
import { formatDeltaPercent } from '../../lib/regionUi';
import { RegionIndicatorRow, RegionSectionHeading } from './RegionParts';
import { useLocale } from '../../i18n';
import '../../styles/z1-prices.css';

const FIRST_ROWS = 10;
const NBSP = ' ';

/** Позиции с ценой (есть группа от сервера). */
export function collectPriceItems(sections) {
  const out = [];
  (sections || []).forEach((s) => (s.indicators || []).forEach((i) => { if (i.price_group) out.push(i); }));
  return out;
}

/** «Яйца куриные, 10 шт.» → { title: 'Яйца куриные', per: '10 шт.' }. */
export function splitShortName(shortName) {
  const text = String(shortName || '');
  const at = text.lastIndexOf(', ');
  if (at < 3) return { title: text, per: '' };
  const per = text.slice(at + 2);
  if (per.length > 26) return { title: text, per: '' };
  return { title: text.slice(0, at), per };
}

export function formatPrice(value, locale = 'ru') {
  const n = Number(value);
  if (!Number.isFinite(n)) return '—';
  const digits = Math.abs(n) < 100 ? 2 : Math.abs(n) < 1000 ? 1 : 0;
  return n.toLocaleString(locale === 'en' ? 'en-US' : 'ru-RU', { minimumFractionDigits: 0, maximumFractionDigits: digits });
}

/** Самый частый месяц среди ходовых цен: его показываем один раз над сеткой, а не на каждой карточке. */
export function commonPeriod(items) {
  const count = new Map();
  items.forEach((i) => { if (i.period_label) count.set(i.period_label, (count.get(i.period_label) || 0) + 1); });
  let best = '';
  let n = 0;
  count.forEach((v, k) => { if (v > n) { best = k; n = v; } });
  return best;
}

function PriceCard({ item, to, locale, common, index = 0 }) {
  const { t } = useLocale();
  const { title, per } = splitShortName(item.short_name || item.name);
  const d = yearDelta(item.value, item.prev_value);
  const signed = d ? (d.pct < 0 ? -Math.abs(d.pct) : Math.abs(d.pct)) : null;
  return (
    <Link
      to={to}
      className="z1p-card fe-panel fe-summary-card fe-press fe-float fe-reveal"
      style={{ '--fe-delay': `${Math.min(index, 7) * 0.04}s`, '--fe-rise': '8px' }}
      data-testid="region-price-card"
    >
      <span className="z1p-card__name">{title}</span>
      <span className="z1p-card__value fe-num">
        {formatPrice(item.value, locale)}{NBSP}₽
        {per ? <span className="z1p-card__per">{NBSP}/ {per}</span> : null}
      </span>
      <span className="z1p-card__foot">
        {item.period_label && item.period_label !== common ? <span className="z1p-card__month">{item.period_label}</span> : null}
        {signed != null && (Math.abs(signed) < 0.05
          ? <span className="z1p-card__flat">{t('r2z1.prices.flat')}</span>
          : (
            <DeltaBadge delta={signed} polarity="up-bad" className="text-xs">
              {formatDeltaPercent(signed, locale)}
            </DeltaBadge>
          ))}
      </span>
    </Link>
  );
}

/** Первый экран: ходовые цены региона и вход во все цены. */
export function RegionPricesBlock({ slug, sections, headlineCodes, total, onOpenAll, pathFor }) {
  const { t, locale } = useLocale();
  const picks = useMemo(() => {
    const byCode = new Map(collectPriceItems(sections).map((i) => [i.code, i]));
    return (headlineCodes || []).map((c) => byCode.get(c)).filter((i) => i && !i.is_discontinued).slice(0, 12);
  }, [sections, headlineCodes]);
  const common = useMemo(() => commonPeriod(picks), [picks]);
  if (picks.length === 0) return null;
  return (
    <section className="z1p-block fe-reveal" data-testid="region-prices-block" aria-labelledby={`z1p-title-${slug}`}>
      <div className="z1p-block__head">
        <div className="z1p-block__top">
          <h2 id={`z1p-title-${slug}`} className="min-w-0 font-display text-xl font-bold leading-snug text-text-primary sm:text-2xl">
            {t('z1.prices.title')}
          </h2>
          <button type="button" className="fe-chip fe-press z1p-all gap-1.5 text-champagne-ink" onClick={onOpenAll} data-testid="region-prices-all">
            {t('z1.prices.all', { n: total })}
            <ArrowRight size={14} aria-hidden="true" />
          </button>
        </div>
        <p className="mt-1 text-sm text-text-secondary">{common ? t('r2z1.prices.leadMonth', { month: common }) : t('z1.prices.lead')}</p>
      </div>
      <div className="z1p-grid">
        {picks.map((item, i) => <PriceCard key={item.code} item={item} to={pathFor(item.code)} locale={locale} common={common} index={i} />)}
      </div>
    </section>
  );
}

function PriceRow({ item, to }) {
  return <RegionIndicatorRow item={item} to={to} title={item.short_name} />;
}

/** Раздел «Цены и тарифы»: годовые ряды раздела (если есть) сверху, затем цены по группам. */
export function RegionPriceSection({ section, groupOrder, pathFor, searching, eyebrow }) {
  const { t } = useLocale();
  const [group, setGroup] = useState('');
  const [open, setOpen] = useState(() => new Set());
  const [indexesOpen, setIndexesOpen] = useState(false);

  const { plain, groups } = useMemo(() => {
    const plainRows = [];
    const map = new Map();
    section.indicators.forEach((item) => {
      if (!item.price_group) { plainRows.push(item); return; }
      if (!map.has(item.price_group)) map.set(item.price_group, { key: item.price_group, label: item.price_group_label || item.price_group, items: [] });
      map.get(item.price_group).items.push(item);
    });
    plainRows.sort((a, b) => (Number(b.year) || 0) - (Number(a.year) || 0));
    const rank = (k) => { const i = (groupOrder || []).indexOf(k); return i < 0 ? 99 : i; };
    const list = [...map.values()].sort((a, b) => rank(a.key) - rank(b.key));
    list.forEach((g) => {
      // Сначала живые в порядке справочника, затем снятые Росстатом.
      g.items = [...g.items.filter((i) => !i.is_discontinued), ...g.items.filter((i) => i.is_discontinued)];
    });
    return { plain: plainRows, groups: list };
  }, [section.indicators, groupOrder]);

  const totalPrices = groups.reduce((n, g) => n + g.items.length, 0);
  const activeGroup = groups.some((g) => g.key === group) ? group : '';
  const shownGroups = activeGroup ? groups.filter((g) => g.key === activeGroup) : groups;

  const toggle = (key) => setOpen((prev) => {
    const next = new Set(prev);
    if (next.has(key)) next.delete(key); else next.add(key);
    return next;
  });

  return (
    <section data-block={`region-section-${section.num}`} className="z1p-section">
      <RegionSectionHeading eyebrow={eyebrow} title={section.name} count={section.indicators.length} />
      {groups.length > 0 && !searching && (
        <div className="z1p-chips fe-chip-row" role="group" aria-label={t('z1.prices.groupsAria')}>
          <button type="button" aria-pressed={!activeGroup} className={`fe-chip fe-press ${!activeGroup ? 'is-active' : ''}`} onClick={() => setGroup('')}>
            {t('z1.prices.groupAll')}
            <span className="z1p-chips__n">{totalPrices}</span>
          </button>
          {groups.map((g) => (
            <button key={g.key} type="button" aria-pressed={activeGroup === g.key} className={`fe-chip fe-press ${activeGroup === g.key ? 'is-active' : ''}`} onClick={() => setGroup(g.key)}>
              {g.label}
              <span className="z1p-chips__n">{g.items.length}</span>
            </button>
          ))}
        </div>
      )}
      {shownGroups.map((g) => {
        const expanded = searching || !!activeGroup || open.has(g.key);
        const rows = expanded ? g.items : g.items.slice(0, FIRST_ROWS);
        return (
          <div key={g.key} className="z1p-group" data-testid={`price-group-${g.key}`}>
            {!searching && (
              <h3 className="z1p-group__title">
                {g.label}
                <span className="z1p-group__n">{g.items.length}</span>
              </h3>
            )}
            <div className="grid grid-cols-1 gap-2 sm:gap-2.5 xl:grid-cols-2">
              {rows.map((item) => <PriceRow key={item.code} item={item} to={pathFor(item.code)} />)}
            </div>
            {!expanded && g.items.length > FIRST_ROWS && (
              <button type="button" className="fe-chip fe-press z1p-more" onClick={() => toggle(g.key)}>
                {t('z1.prices.showMore', { n: g.items.length })}
              </button>
            )}
            {!searching && !activeGroup && expanded && g.items.length > FIRST_ROWS && (
              <button type="button" className="fe-chip fe-press z1p-more" onClick={() => toggle(g.key)}>
                {t('z1.prices.collapse')}
              </button>
            )}
          </div>
        );
      })}
      {plain.length > 0 && (
        <div className="z1p-group z1p-indexes" data-testid="price-indexes">
          {!searching && groups.length > 0 && (
            <h3 className="z1p-group__title">
              {t('r2z1.prices.indexes')}
              <span className="z1p-group__n">{plain.length}</span>
            </h3>
          )}
          <div className="grid grid-cols-1 gap-2 sm:gap-2.5 xl:grid-cols-2">
            {(searching || indexesOpen || groups.length === 0 ? plain : plain.slice(0, 4)).map((item) => <RegionIndicatorRow key={item.code} item={item} to={pathFor(item.code)} />)}
          </div>
          {!searching && groups.length > 0 && plain.length > 4 && (
            <button type="button" className="fe-chip fe-press z1p-more" onClick={() => setIndexesOpen((v) => !v)}>
              {indexesOpen ? t('z1.prices.collapse') : t('z1.prices.showMore', { n: plain.length })}
            </button>
          )}
        </div>
      )}
    </section>
  );
}
