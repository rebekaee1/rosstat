/* eslint-disable no-irregular-whitespace -- неразрывные пробелы в «₽» и «%» намеренные */
/* eslint-disable react-refresh/only-export-components -- рядом с компонентами лежат малые чистые помощники */
// R10-B: ответ семье за один экран. Сколько стоит переезд, что дороже, что дешевле, хватит ли зарплаты.
// Все цифры считаются из ответа цен пары, поэтому работает и со старым сервером.
import { useEffect, useState } from 'react';
import { ChevronRight } from 'lucide-react';
import { formatPrice, splitShortName } from './RegionPrices';
import '../../styles/r10b-compare.css';

export const KEY_GROUPS = ['Продукты', 'ЖКХ', 'Жильё', 'Топливо', 'Лекарства', 'Транспорт'];

const loc = (locale) => (locale === 'en' ? 'en-US' : 'ru-RU');
const pctText = (n, locale) => Number(n).toLocaleString(loc(locale), { maximumFractionDigits: 0 });

export function rub(value, locale) {
  const n = Number(value);
  return Number.isFinite(n) ? `${formatPrice(Math.round(n), locale)} ₽` : '—';
}

/** На сколько процентов дешевле дешёвая сторона (от дорогой): 60 из 100 и 40 из 100 дают 60, а не 150. */
export function lessPct(x, y, digits = 0) {
  const hi = Math.max(Number(x), Number(y));
  const lo = Math.min(Number(x), Number(y));
  if (!(hi > 0)) return 0;
  const k = 10 ** digits;
  return Math.round(((hi - lo) / hi) * 100 * k) / k;
}

/** Переезд из первого региона во второй: на сколько меняется набор семьи. */
export function moveSummary(data) {
  const basket = data?.basket;
  if (!basket || !(basket.total_a > 0)) return null;
  const delta = basket.total_b - basket.total_a;
  return {
    delta,
    year: delta * 12,
    pct: (delta / basket.total_a) * 100,
    dir: Math.abs(delta) < 1 ? 0 : (delta > 0 ? 1 : -1),
  };
}

function median(list) {
  const s = [...list].sort((x, y) => x - y);
  const m = Math.floor(s.length / 2);
  return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2;
}

/** Типичная разница по группам: медиана (цена во втором регионе / цена в первом - 1) в процентах. */
export function categorySummary(items) {
  const out = [];
  KEY_GROUPS.forEach((g) => {
    const rows = (items || []).filter((i) => i.group === g && i.a > 0 && i.b > 0);
    if (rows.length < 2) return;
    const pct = median(rows.map((i) => (i.b / i.a - 1) * 100));
    out.push({ group: g, label: rows[0].group_label || g, n: rows.length, pct, dir: Math.abs(pct) < 1 ? 0 : (pct > 0 ? 1 : -1) });
  });
  return out;
}

/** Товары с самой большой разницей между регионами. */
export function biggestGaps(items, limit = 5) {
  return (items || [])
    .filter((i) => i.a > 0 && i.b > 0 && i.cheaper_slug && Number.isFinite(i.diff_pct) && i.diff_pct >= 10)
    .sort((x, y) => y.diff_pct - x.diff_pct)
    .slice(0, limit);
}

export function R10bAnswer({ data, locale, t }) {
  const { region_a: a, region_b: b, basket, wage } = data;
  const mv = moveSummary(data);
  if (!mv) return null;
  const sum = rub(Math.abs(mv.delta), locale);
  const key = mv.dir > 0 ? 'r10b.ans.dearer' : mv.dir < 0 ? 'r10b.ans.cheaper' : 'r10b.ans.same';
  const word = mv.dir > 0 ? 'r10b.cats.more' : 'r10b.cats.less';
  const need = wage && mv.dir !== 0 ? wage.a * (basket.total_b / basket.total_a) : null;
  const num = (v) => Number(v).toLocaleString(loc(locale), { maximumFractionDigits: 1 });
  return (
    <section className="r10b-answer fe-panel" data-testid="r10b-answer">
      <h2 className="r10b-answer__head">{t(key, { to: b.name, from: a.name, rub: sum })}</h2>
      {mv.dir !== 0 && (
        <p className="r10b-answer__sub">
          {t('r10b.ans.sub', {
            from: a.name, n: basket.items.length, month: data.period_label,
            pct: t(word, { pct: pctText(Math.abs(mv.pct), locale) }), year: rub(Math.abs(mv.year), locale),
          })}
        </p>
      )}
      {wage && (
        <p className="r10b-answer__wage" data-testid="r10b-answer-wage">
          {t('r10b.ans.wage', {
            from: a.name, to: b.name, wa: rub(wage.a, locale), wb: rub(wage.b, locale), ka: num(wage.baskets_a), kb: num(wage.baskets_b),
          })}
        </p>
      )}
      {need != null && (
        <p className="r10b-answer__need" data-testid="r10b-answer-need">
          {t('r10b.ans.need', { from: a.name, to: b.name, need: rub(need, locale) })}
        </p>
      )}
    </section>
  );
}

export function R10bCategories({ data, locale, t, onPick }) {
  const cats = categorySummary(data.items);
  if (cats.length < 2) return null;
  const { region_a: a, region_b: b } = data;
  const peak = Math.max(10, ...cats.map((c) => Math.abs(c.pct)));
  return (
    <section className="r10b-cats fe-panel" data-testid="r10b-cats">
      <h2 className="r10b-h">{t('r10b.cats.title')}</h2>
      <p className="r10b-lead">{t('r10b.cats.lead', { to: b.name, from: a.name })}</p>
      <ul className="r10b-cats__list">
        {cats.map((c) => (
          <li key={c.group}>
            <button type="button" className={`r10b-cat fe-press${c.dir > 0 ? ' is-up' : c.dir < 0 ? ' is-down' : ''}`} onClick={() => onPick(c.group)}>
              <span className="r10b-cat__label">{c.label}</span>
              <span className="r10b-cat__bar" aria-hidden="true"><span style={{ width: `${Math.max(6, (Math.abs(c.pct) / peak) * 100)}%` }} /></span>
              <span className="fe-num r10b-cat__val">
                {c.dir === 0 ? t('r10b.cats.same') : t(c.dir > 0 ? 'r10b.cats.more' : 'r10b.cats.less', { pct: pctText(Math.abs(c.pct), locale) })}
              </span>
              <ChevronRight size={15} aria-hidden="true" />
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}

export function R10bGaps({ data, locale, t }) {
  const gaps = biggestGaps(data.items);
  if (gaps.length < 2) return null;
  const { region_a: a, region_b: b } = data;
  return (
    <section className="r10b-gaps fe-panel" data-testid="r10b-gaps">
      <h2 className="r10b-h">{t('r10b.gap.title')}</h2>
      <ul className="r10b-gaps__list">
        {gaps.map((g) => {
          const pricier = g.cheaper_slug === a.slug ? b : a;
          const { title, per } = splitShortName(g.name);
          return (
            <li key={g.code} className="r10b-gap">
              <span className="r10b-gap__name">{title}{per ? <span className="r10b-gap__per">{`, ${per}`}</span> : null}</span>
              <span className="r10b-gap__why">{t('r10b.gap.row', { pct: pctText(g.diff_pct, locale), name: pricier.name })}</span>
              <span className="fe-num r10b-gap__prices">
                {t('r10b.gap.prices', { pa: rub(g.a, locale), pb: rub(g.b, locale) })}
              </span>
            </li>
          );
        })}
      </ul>
    </section>
  );
}

/** Скелет пока считаются цены; через 4 секунды объясняет, почему так долго. */
export function R10bWait({ t }) {
  const [slow, setSlow] = useState(false);
  useEffect(() => {
    const id = setTimeout(() => setSlow(true), 4000);
    return () => clearTimeout(id);
  }, []);
  return slow ? <p className="r10b-wait" role="status" data-testid="r10b-wait">{t('r10b.slow')}</p> : null;
}

export function R10bError({ t, onRetry, busy }) {
  return (
    <div className="r10b-err fe-panel" role="alert" data-testid="r10b-err">
      <p>{t('r10b.err')}</p>
      <button type="button" className="r4a-more fe-press" onClick={onRetry} disabled={busy}>{t('r10b.err.retry')}</button>
    </div>
  );
}
