// Круг 2, зона R2-Z3: под результатом конвертера — сколько получилось бы месяц и год назад и чем сейчас лучше или хуже.
// Без красного и зелёного: смысл словами («на 0,4 % больше»).
import { useMemo } from 'react';
import { useIndicatorData } from '../lib/hooks';
import { formatConverted, unitWord } from '../lib/currencyRates';
import { comparePast, rateDaysAgo } from '../lib/z3Past';
import { formatDate, formatValue } from '../lib/format';
import { useLocale, useT } from '../i18n';
import '../styles/z3-cur.css';

function verdict(t, pct, locale) {
  const abs = Math.abs(pct);
  if (abs < 0.1) return t('r2z3.past.same');
  const text = formatValue(abs, abs < 10 ? 1 : 0, locale);
  return t(pct > 0 ? 'r2z3.past.more' : 'r2z3.past.less', { pct: text });
}

/** pair: { code, base, quote, invert, units } из chartPairFor; считается, только если ряд идёт ровно от «Из» к «В». */
export default function Z3PastCompare({ pair, from, to, amount, nowRate }) {
  const t = useT();
  const { locale } = useLocale();
  const usable = Boolean(pair && pair.base === from && pair.quote === to && amount > 0 && nowRate > 0);
  const { data } = useIndicatorData(usable ? pair.code : null, { limit: 400 });
  const items = useMemo(() => {
    if (!usable) return [];
    const opts = { invert: pair.invert, units: pair.units };
    return [['month', 30], ['year', 365]].map(([key, days]) => {
      const cmp = comparePast(amount, nowRate, rateDaysAgo(data?.data, days, opts));
      return cmp ? { key, ...cmp } : null;
    }).filter(Boolean);
  }, [usable, data, pair, amount, nowRate]);
  if (usable && !data) return <div className="z3-past z3-past--ghost" aria-hidden="true" />;
  if (!items.length) return null;
  return (
    <div className="z3-past" data-testid="converter-past">
      <p className="z3-past__title">{t('r2z3.past.title')}</p>
      <div className="z3-past__grid">
        {items.map((item) => (
          <div key={item.key} className="z3-past__item">
            <p className="z3-past__when">{t(`r2z3.past.${item.key}`)}</p>
            <p className="z3-past__val">
              {formatConverted(item.value, locale, { money: true })}
              <span className="z3-past__unit">{locale === 'en' ? to : unitWord(item.value, to, 'ru')}</span>
            </p>
            <p className="z3-past__diff">{verdict(t, item.pct, locale)}</p>
            <p className="z3-past__date">{formatDate(item.date, 'day', locale)}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
