// Круг 5, R5-C: инструменты предпринимателя на странице курсов: «Курс ЦБ на дату», «Скопировать для документа», таблица курсов с выгрузкой.
import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { Check, Copy, Download } from 'lucide-react';
import { CoinBadge } from './CurrencySelect';
import { useIndicatorData } from '../lib/hooks';
import { cn, formatDate, formatValue } from '../lib/format';
import { formatConverted, unitWord } from '../lib/currencyRates';
import { coinOf, unitName } from '../lib/currencyChart';
import { russiaIndicatorPath } from '../lib/sitePaths';
import { copyText, dateShortcuts, downloadText, rateOnDate, rateTableRows, ratesCsv } from '../lib/r5cExport';
import { track, events } from '../lib/track';
import { useLocale, useT } from '../i18n';
import '../styles/r5c-tools.css';

/** Сумма со словом: «100 $», «8 214 ₽», «1 000 юаней». */
function money(value, unit, locale) {
  return `${formatConverted(value, locale, { money: true })}\u00a0${unitWord(value, unit, locale)}`;
}

/** Кнопка «Скопировать для документа»: строка вида «100 $ = 8 214 ₽ по курсу Банка России на 7 ноября 2026». */
export function CopyResult({ from, to, amount, value, date }) {
  const t = useT();
  const { locale } = useLocale();
  const [done, setDone] = useState(false);
  if (!(amount > 0) || !(value > 0)) return null;
  const onCopy = async () => {
    const tail = date ? t('r5c.copy.tail', { date: formatDate(date, 'day', locale) }) : '';
    const ok = await copyText(`${money(amount, from, locale)} = ${money(value, to, locale)}${tail}`);
    if (ok) {
      setDone(true);
      track(events.COMPARE_CHANGE, { converter: 'copy' });
      window.setTimeout(() => setDone(false), 2200);
    }
  };
  return (
    <button type="button" className={cn('r5c-copy fe-press', done && 'is-done')} onClick={onCopy} aria-live="polite">
      {done ? <Check size={16} aria-hidden="true" /> : <Copy size={16} aria-hidden="true" />}
      {done ? t('r5c.copy.done') : t('r5c.copy.btn')}
    </button>
  );
}

/** «Курс ЦБ на дату»: для договора, акта, таможни. Кнопки быстрых дат и своя дата; под ними сумма по тому дню. */
export function DateRate({ pair, from, to, amount, nowRate }) {
  const t = useT();
  const { locale } = useLocale();
  const [picked, setPicked] = useState('');
  const usable = Boolean(pair && pair.base === from && pair.quote === to);
  const { data } = useIndicatorData(usable ? pair.code : null, { limit: 800 });
  const rows = data?.data;
  const span = useMemo(() => {
    if (!rows || !rows.length) return null;
    const dates = rows.map((r) => String(r.date || '').slice(0, 10)).filter(Boolean).sort();
    return dates.length ? { first: dates[0], last: dates[dates.length - 1] } : null;
  }, [rows]);
  const found = useMemo(
    () => (usable && picked ? rateOnDate(rows, picked, { invert: pair.invert, units: pair.units }) : null),
    [usable, picked, rows, pair],
  );
  if (!usable || !span) return null;
  const shortcuts = dateShortcuts(span.last).filter((s, i, all) => s.iso >= span.first && all.findIndex((o) => o.iso === s.iso) === i);
  const out = found && amount > 0 ? amount * found.rate : null;
  const pct = found && nowRate > 0 ? ((nowRate / found.rate) - 1) * 100 : null;
  return (
    <div className="r5c-date" data-testid="converter-date">
      <p className="r5c-date__title">{t('r5c.date.title')}</p>
      <div className="r5c-date__chips" role="group" aria-label={t('r5c.date.title')}>
        {shortcuts.map((s) => (
          <button
            key={s.key}
            type="button"
            className={cn('fe-z8-quick__btn fe-press', picked === s.iso && 'is-active')}
            aria-pressed={picked === s.iso}
            onClick={() => { setPicked(picked === s.iso ? '' : s.iso); track(events.COMPARE_CHANGE, { converter: 'date-chip', key: s.key }); }}
          >
            {t(`r5c.date.${s.key}`)}
          </button>
        ))}
        <label className={cn('r5c-date__own fe-z8-quick__btn fe-press', picked && !shortcuts.some((s) => s.iso === picked) && 'is-active')}>
          <span aria-hidden="true">{picked && !shortcuts.some((s) => s.iso === picked) ? formatDate(picked, 'day', locale) : t('r5c.date.own')}</span>
          <input
            type="date"
            className="r5c-date__input"
            value={picked}
            min={span.first}
            max={span.last}
            onChange={(event) => setPicked(event.target.value)}
            aria-label={t('r5c.date.own')}
          />
        </label>
      </div>
      {picked && !found && <p className="r5c-date__note" role="status">{t('r5c.date.none', { first: formatDate(span.first, 'day', locale) })}</p>}
      {found && out != null && (
        <div className="r5c-date__res" role="status">
          <p className="r5c-date__sum">{money(out, to, locale)}</p>
          <p className="r5c-date__note">
            {t('r5c.date.asOf', { date: formatDate(found.date, 'day', locale) })}
            {pct != null && Math.abs(pct) >= 0.1 ? `, ${t(pct > 0 ? 'r2z3.past.more' : 'r2z3.past.less', { pct: formatValue(Math.abs(pct), Math.abs(pct) < 10 ? 1 : 0, locale) })}` : ''}.
          </p>
          <CopyResult from={from} to={to} amount={amount} value={out} date={found.date} />
        </div>
      )}
    </div>
  );
}

const DOC_UNITS = ['USD', 'EUR', 'CNY', 'AED', 'TRY'];

/** «Курсы ЦБ для документов»: пять валют закупок с датой и выгрузка всех курсов в таблицу. */
export function DocRates({ edges }) {
  const t = useT();
  const { locale } = useLocale();
  const rows = useMemo(() => rateTableRows(edges, locale), [edges, locale]);
  const main = DOC_UNITS.map((unit) => rows.find((r) => r.code === unit)).filter(Boolean);
  if (main.length < 2) return null;
  const date = main.map((r) => r.date).filter(Boolean).sort().pop() || '';
  const onDownload = () => {
    downloadText(`kursy-cb-${date || 'today'}.csv`, ratesCsv(rows, locale));
    track(events.COMPARE_CHANGE, { converter: 'csv' });
  };
  return (
    <section className="fe-panel r5c-doc" data-block="currency-doc-rates" aria-label={t('r5c.doc.title')}>
      <header className="r5c-doc__head">
        <h2 className="r5c-doc__title">{t('r5c.doc.title')}</h2>
        {date && <p className="r5c-doc__date">{t('r5c.doc.date', { date: formatDate(date, 'day', locale) })}</p>}
      </header>
      <ul className="r5c-doc__list">
        {main.map((r) => {
          const meta = coinOf(r.code);
          return (
            <li key={r.code}>
              <Link to={russiaIndicatorPath(`${r.code.toLowerCase()}-rub`)} className="r5c-doc__row fe-press">
                <CoinBadge className="r5c-doc__coin" flag={meta.flag} symbol={meta.symbol} />
                <span className="r5c-doc__name">{unitName(r.code, locale)}</span>
                <span className="r5c-doc__val">
                  {r.nominal > 1 && <span className="r5c-doc__per">{`${formatValue(r.nominal, 0, locale)}\u00a0${unitWord(r.nominal, r.code, locale)} =`}</span>}
                  <span className="r5c-doc__num">{formatValue(r.value, 2, locale)}</span>
                  <span className="r5c-doc__unit">₽</span>
                </span>
              </Link>
            </li>
          );
        })}
      </ul>
      <button type="button" className="r5c-doc__dl fe-press" onClick={onDownload}>
        <Download size={16} aria-hidden="true" />
        {t('r5c.doc.download', { n: rows.length })}
      </button>
    </section>
  );
}
