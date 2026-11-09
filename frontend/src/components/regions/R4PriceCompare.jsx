/* eslint-disable no-irregular-whitespace -- неразрывные пробелы в «₽» и «%» намеренные */
/* eslint-disable react-refresh/only-export-components -- рядом с компонентами лежат малые чистые помощники */
// R4-A: цены двух регионов рядом — корзина семьи, зарплата в корзинах и таблица по группам.
// Только сравнение значений: без мест в рейтинге и без диапазонов.
import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { ChevronDown, Wallet, ShoppingBasket, Copy, Check } from 'lucide-react';
import api from '../../lib/api';
import { regionIndicatorPath } from '../../lib/sitePaths';
import { formatPrice, splitShortName } from './RegionPrices';
import { useLocale } from '../../i18n';
import { resolveBrowserLocale } from '../../i18n/locale';
import '../../styles/r4a-compare-prices.css';

export function useRegionPriceCompare(slugA, slugB) {
  return useQuery({
    queryKey: ['region-compare-prices', slugA, slugB, resolveBrowserLocale()],
    queryFn: ({ signal }) =>
      api.get(`/regions/vs/${slugA}/${slugB}/prices`, { signal }).then((r) => r.data),
    enabled: !!slugA && !!slugB,
    staleTime: 10 * 60 * 1000,
    retry: false,
  });
}

/** Группы цен в порядке прихода от сервера. */
export function groupPriceItems(items) {
  const out = [];
  (items || []).forEach((it) => {
    let g = out.find((x) => x.group === it.group);
    if (!g) { g = { group: it.group, label: it.group_label, items: [] }; out.push(g); }
    g.items.push(it);
  });
  return out;
}

export function formatRub(value, locale) {
  const n = Number(value);
  return Number.isFinite(n) ? `${formatPrice(Math.round(n), locale)} ₽` : '—';
}

function Duel({ a, b, valueA, valueB, cheaperSlug, format, testId }) {
  const peak = Math.max(valueA, valueB, 1e-9);
  const cell = (r, v) => (
    <div className={`r4a-duel__cell${cheaperSlug === r.slug ? ' is-better' : ''}`}>
      <span className="r4a-duel__name">{r.name}</span>
      <span className="fe-num r4a-duel__value">{format(v)}</span>
      <span className="r4a-duel__bar" aria-hidden="true"><span style={{ width: `${Math.max(4, (v / peak) * 100)}%` }} /></span>
    </div>
  );
  return <div className="r4a-duel" data-testid={testId}>{cell(a, valueA)}{cell(b, valueB)}</div>;
}

function BasketCard({ data, locale, t }) {
  const [open, setOpen] = useState(false);
  const { basket, wage, region_a: a, region_b: b } = data;
  if (!basket) return null;
  const nameOf = (slug) => (slug === a.slug ? a.name : b.name);
  const fmtTimes = (n) => `${Number(n).toLocaleString(locale === 'en' ? 'en-US' : 'ru-RU', { maximumFractionDigits: 1 })}×`;
  return (
    <section className="fe-panel r4a-card" data-testid="r4a-basket">
      <h2 className="r4a-card__title"><ShoppingBasket size={17} aria-hidden="true" />{t('r4a.basket.title')}</h2>
      <p className="r4a-card__lead">{t('r4a.basket.lead', { n: basket.items.length, month: data.period_label })}</p>
      <Duel
        a={a} b={b} valueA={basket.total_a} valueB={basket.total_b}
        cheaperSlug={basket.cheaper_slug} format={(v) => formatRub(v, locale)} testId="r4a-basket-duel"
      />
      <p className="r4a-card__verdict">
        {basket.cheaper_slug && basket.diff_pct != null
          ? t('r4a.basket.verdict', { name: nameOf(basket.cheaper_slug), pct: String(basket.diff_pct).replace('.', locale === 'en' ? '.' : ',') })
          : t('r4a.basket.same')}
        {basket.cheaper_slug && Math.abs(basket.total_a - basket.total_b) >= 1 && (
          <> {t('r5d.diffRub', { sum: formatRub(Math.abs(basket.total_a - basket.total_b), locale) })}</>
        )}
      </p>
      {wage && (
        <div className="r4a-wage" data-testid="r4a-wage">
          <h3 className="r4a-wage__title"><Wallet size={16} aria-hidden="true" />{t('r4a.wage.title')}</h3>
          <Duel
            a={a} b={b} valueA={wage.baskets_a} valueB={wage.baskets_b}
            cheaperSlug={wage.better_slug} format={fmtTimes} testId="r4a-wage-duel"
          />
          <p className="r4a-card__verdict">
            {wage.better_slug
              ? t('r4a.wage.verdict', { name: nameOf(wage.better_slug), year: wage.year })
              : t('r4a.wage.same', { year: wage.year })}
          </p>
        </div>
      )}
      <button type="button" className="r4a-more fe-press" aria-expanded={open} onClick={() => setOpen((v) => !v)}>
        {t('r4a.basket.what')}
        <ChevronDown size={16} aria-hidden="true" className={open ? 'is-open' : ''} />
      </button>
      {open && (
        <ul className="r4a-list" data-testid="r4a-basket-items">
          {basket.items.map((it) => (
            <li key={it.code} className="r4a-list__row">
              <span className="r4a-list__name">{splitShortName(it.name).title}<span className="r4a-list__qty">{` × ${it.qty}`}</span></span>
              <span className={`fe-num r4a-list__val${it.cheaper_slug === a.slug ? ' is-better' : ''}`}>{formatRub(it.a, locale)}</span>
              <span className={`fe-num r4a-list__val${it.cheaper_slug === b.slug ? ' is-better' : ''}`}>{formatRub(it.b, locale)}</span>
            </li>
          ))}
        </ul>
      )}
      <p className="r4a-card__note">{t('r4a.basket.note')}</p>
      <p className="r4a-card__note r5d-source" data-testid="r5d-source">
        {wage
          ? t('r5d.src', { month: data.period_label, year: wage.year, n: basket.items.length })
          : t('r5d.src.noWage', { month: data.period_label, n: basket.items.length })}
      </p>
    </section>
  );
}

function GroupTable({ group, data, locale, t, forceOpen, defaultOpen }) {
  const [own, setOwn] = useState(!!defaultOpen);
  const open = own || forceOpen;
  const { region_a: a, region_b: b } = data;
  const cheaperA = group.items.filter((i) => i.cheaper_slug === a.slug).length;
  const cheaperB = group.items.filter((i) => i.cheaper_slug === b.slug).length;
  return (
    <section className="r4a-group">
      <button type="button" className="r4a-group__head fe-press" aria-expanded={open} onClick={() => setOwn((v) => !v)}>
        <span className="r4a-group__label">{group.label}</span>
        <span className="r4a-group__tally">{t('r4a.group.tally', { a: cheaperA, b: cheaperB })}</span>
        <ChevronDown size={16} aria-hidden="true" className={open ? 'is-open' : ''} />
      </button>
      {open && (
        <div className="r4a-table" role="table">
          <div className="r4a-table__row r4a-table__row--head" role="row">
            <span role="columnheader" className="r4a-table__name">{t('r4a.table.good')}</span>
            <span role="columnheader" className="r4a-table__val">{a.name}</span>
            <span role="columnheader" className="r4a-table__val">{b.name}</span>
          </div>
          {group.items.map((it) => {
            const { title, per } = splitShortName(it.name);
            return (
              <div className="r4a-table__row" role="row" key={it.code}>
                <span role="cell" className="r4a-table__name">
                  <Link to={regionIndicatorPath(a.slug, it.code)} className="r4a-table__link">{title}</Link>
                  {per && <span className="r4a-table__per">{per}</span>}
                </span>
                {[a, b].map((r, k) => (
                  <span role="cell" key={r.slug} className={`fe-num r4a-table__val${it.cheaper_slug === r.slug ? ' is-better' : ''}`}>
                    {formatPrice(k === 0 ? it.a : it.b, locale)}
                    {it.cheaper_slug === r.slug && it.diff_pct != null && it.diff_pct >= 1 && (
                      <span className="r4a-table__diff">{`−${Math.round(it.diff_pct)} %`}</span>
                    )}
                  </span>
                ))}
              </div>
            );
          })}
        </div>
      )}
    </section>
  );
}

/** Текст для вставки в таблицу курсовой: товар, цена в первом и втором регионе. */
export function compareAsText(data, locale) {
  const { region_a: a, region_b: b, basket } = data;
  const rows = [['', a.name, b.name]];
  if (basket) rows.push([`${data.period_label}: basket`, formatRub(basket.total_a, locale), formatRub(basket.total_b, locale)]);
  (data.items || []).forEach((it) => rows.push([it.name, String(it.a), String(it.b)]));
  return rows.map((r) => r.join('\t')).join('\n');
}

function CopyNumbers({ data, locale, t }) {
  const [done, setDone] = useState(false);
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(compareAsText(data, locale));
      setDone(true);
      setTimeout(() => setDone(false), 2000);
    } catch { /* буфер недоступен — молча */ }
  };
  return (
    <button type="button" className="r4a-more fe-press r5d-copy" onClick={copy} data-testid="r5d-copy">
      {done ? <Check size={15} aria-hidden="true" /> : <Copy size={15} aria-hidden="true" />}
      {done ? t('r5d.copied') : t('r5d.copy')}
    </button>
  );
}

export function R4PriceVerdict({ data, locale, t }) {
  const { basket, wage, region_a: a, region_b: b } = data;
  if (!basket?.cheaper_slug) return null;
  const nameOf = (slug) => (slug === a.slug ? a.name : b.name);
  const pct = String(basket.diff_pct).replace('.', locale === 'en' ? '.' : ',');
  const wageName = wage?.better_slug ? nameOf(wage.better_slug) : null;
  return (
    <p className="r4a-hero" data-testid="r4a-verdict">
      {t('r4a.hero.cheaper', { name: nameOf(basket.cheaper_slug), pct })}
      {wageName && ` ${wageName === nameOf(basket.cheaper_slug) ? t('r4a.hero.wageSame') : t('r4a.hero.wageOther', { name: wageName })}`}
    </p>
  );
}

export function R4PriceSkeleton() {
  return (
    <div className="r4a-prices" aria-hidden="true">
      <div className="r4a-skel r4a-skel--card" />
      <div className="r4a-skel r4a-skel--row" />
    </div>
  );
}

export default function R4PriceCompare({ data }) {
  const { t, locale } = useLocale();
  const [all, setAll] = useState(false);
  if (!data || !data.items?.length) return null;
  const groups = groupPriceItems(data.items);
  const { cheaper_count: c, region_a: a, region_b: b } = data;
  return (
    <div className="r4a-prices" data-testid="r4a-prices">
      <R4PriceVerdict data={data} locale={locale} t={t} />
      <p className="r4a-tally" data-testid="r4a-cheaper-tally">
        {t('r4a.tally', { a: a.name, na: c.a, b: b.name, nb: c.b, n: c.total })}
      </p>
      <BasketCard data={data} locale={locale} t={t} />
      <div className="r4a-h2row">
        <h2 className="r4a-h2">{t('r4a.table.title', { month: data.period_label })}</h2>
        <CopyNumbers data={data} locale={locale} t={t} />
        <button type="button" className="r4a-more fe-press" onClick={() => setAll((v) => !v)} data-testid="r4a-expand-all">
          {all ? t('r4a.group.collapse') : t('r4a.group.expand')}
        </button>
      </div>
      <div className="r4a-groups">
        {groups.map((g, i) => (
          <GroupTable key={g.group} group={g} data={data} locale={locale} t={t} forceOpen={all} defaultOpen={i === 0} />
        ))}
      </div>
    </div>
  );
}
