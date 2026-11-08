// Конвертер валют: на странице «Курсы валют» (все пары) и компактный на карточке курса (одна пара).
// Порядок блоков под телефон: сумма, быстрые суммы, РЕЗУЛЬТАТ, потом «Из ⇄ В» и популярные валюты. Результат виден сразу после ввода.
import { useId, useMemo, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { ArrowRightLeft } from 'lucide-react';
import CurrencySelect, { CoinBadge } from './CurrencySelect';
import { useIndicator, useIndicatorData } from '../lib/hooks';
import { cn, formatDate, formatValue } from '../lib/format';
import {
  TRAVEL_UNITS, amountPresets, buildEdges, convert, convertibleUnits, currencySearchText, describeRate, formatConverted,
  parseAmountInput, parsePair, rateBasis, unitMeta, unitWord,
} from '../lib/currencyRates';
import { coinOf, unitName } from '../lib/currencyChart';
import { chartPairFor } from '../lib/currencyMarket';
import Z3PastCompare from './Z3PastCompare';
import { track, events } from '../lib/track';
import { useGlintOnChange } from '../lib/calcGlint';
import { useLocale, useT } from '../i18n';
import '../styles/z8-tools.css';
import '../styles/k8-tools.css';
import '../styles/c8-currency.css';
import '../styles/z3-cur.css';

/** Сумма в поле одним видом с кнопками «1 000», «10 000»: тысячи отделены пробелом, дробь сохраняется. */
function groupedAmount(amount, locale) {
  if (!Number.isFinite(amount)) return '';
  const digits = Number.isInteger(amount) ? 0 : Math.min(8, (String(amount).split('.')[1] || '').length);
  return formatValue(amount, digits, locale);
}

/** Сумма и быстрые суммы под валюту «Из»: пока человек сам не вводил, подставляется разумная (для сума миллион, а не сто). */
function useAmount(from, edges, locale) {
  const presets = useMemo(() => amountPresets(from, edges), [from, edges]);
  const [typed, setTyped] = useState(null);
  const text = typed ?? groupedAmount(presets.initial, locale);
  return { text, setText: setTyped, amount: parseAmountInput(text, locale), presets };
}

/** Единица рядом с цифрой результата: «1 121 сомони», «1 457 726 сумов»; без готового слова — полное название. */
function shortUnit(unit, value, locale) {
  if (locale === 'en') return unitName(unit, locale);
  const word = unitWord(Math.floor(Math.abs(value)) || 1, unit, 'ru');
  return word === unit ? unitName(unit, locale) : word;
}

/** Результат конвертера: «камень» с золотой цифрой; блик проходит заново, когда число изменилось. */
function ConverterOut({ result, rate, safeTo, basisKey }) {
  const t = useT();
  const { locale } = useLocale();
  const ref = useRef(null);
  useGlintOnChange(ref, result ? result.value : null);
  const crypto = Boolean(unitMeta(safeTo)?.crypto);
  return (
    <div ref={ref} className="fe-z8-conv__out fe-glint z3-out" aria-live="polite" data-testid="converter-result">
      {result ? (
        <>
          <p className="fe-z8-conv__sum">
            <span className="fe-z8-conv__num">{formatConverted(result.value, locale, { money: !crypto })}</span>
            <span className="fe-z8-conv__unit">{shortUnit(safeTo, result.value, locale)}</span>
          </p>
          {rate?.lines.map((line) => (
            <p key={line} className="fe-z8-conv__rate">{line}</p>
          ))}
          {result.date && (
            <p className="fe-z8-conv__note">
              {t(basisKey, { date: formatDate(result.date, 'day', locale) })}
            </p>
          )}
        </>
      ) : (
        <p className="fe-z8-conv__note">{t('w6g.cur.badAmount')}</p>
      )}
    </div>
  );
}

function AmountField({ id, amount, text, setText, locale, label }) {
  return (
    <label className="fe-z8-field fe-z8-conv__amount z3-amount" htmlFor={id}>
      <span className="fe-z8-select__label">{label}</span>
      <input
        id={id}
        type="text"
        inputMode="decimal"
        autoComplete="off"
        value={text}
        onChange={(event) => setText(event.target.value)}
        onFocus={(event) => { const node = event.target; window.setTimeout(() => { if (document.activeElement === node) node.select(); }, 0); }}
        onBlur={() => { if (amount != null && text.trim() !== '') setText(groupedAmount(amount, locale)); }}
        aria-invalid={amount == null ? 'true' : undefined}
        className="fe-z8-input"
      />
    </label>
  );
}

function QuickAmounts({ presets, amount, setText, locale }) {
  const t = useT();
  return (
    <div className="fe-z8-quick z3-quick" role="group" aria-label={t('z8.cur.quickAria')}>
      {presets.list.map((value) => (
        <button
          key={value}
          type="button"
          className={cn('fe-z8-quick__btn fe-press', amount === value && 'is-active')}
          onClick={() => setText(groupedAmount(value, locale))}
        >
          {formatValue(value, 0, locale)}
        </button>
      ))}
    </div>
  );
}

/** Название валюты на кнопке: «Сум», «Тенге»; без готового слова код. */
function chipName(unit, locale) {
  if (locale === 'en') return unit;
  const word = unitWord(1, unit, 'ru');
  return word === unit ? unit : word.charAt(0).toUpperCase() + word.slice(1);
}

export function Converter({ edges, from, to, onFrom, onTo }) {
  const t = useT();
  const { locale } = useLocale();
  const id = useId();
  const units = useMemo(() => convertibleUnits(edges), [edges]);
  // Каждое нажатие на «⇄» поворачивает стрелки ещё на 180° (k8-tools: --k8-turn).
  const [turns, setTurns] = useState(0);
  const safeFrom = units.includes(from) ? from : units[0];
  const safeTo = units.includes(to) && to !== safeFrom ? to : units.find((u) => u !== safeFrom);
  const { text, setText, amount, presets } = useAmount(safeFrom, edges, locale);
  // Выпадающий список: привычные валюты, затем «в дорогу», затем остальные.
  const ordered = useMemo(() => {
    const head = ['RUB', 'USD', 'EUR', 'CNY', 'GBP'];
    const travel = TRAVEL_UNITS.filter((u) => units.includes(u));
    return [...units.filter((u) => head.includes(u)), ...travel, ...units.filter((u) => !head.includes(u) && !travel.includes(u))];
  }, [units]);
  if (units.length < 2) return null;

  const result = amount != null ? convert(amount, safeFrom, safeTo, edges) : null;
  const rate = describeRate(safeFrom, safeTo, edges, locale);
  const pastPair = chartPairFor(edges, safeFrom, safeTo);
  const bases = result ? new Set(result.path.map((code) => rateBasis(code)).filter(Boolean)) : new Set();
  const basisKey = bases.size === 1 ? `w6g.cur.basis.${[...bases][0]}` : 'w6g.cur.basis.mix';
  const swap = () => {
    onFrom(safeTo);
    onTo(safeFrom);
    setTurns((n) => n + 1);
    track(events.COMPARE_CHANGE, { converter: 'swap' });
  };
  const optionOf = (unit) => ({
    value: unit,
    name: unitName(unit, locale),
    ...coinOf(unit),
    search: currencySearchText(unit),
  });
  const fromOptions = ordered.map(optionOf);
  const toOptions = ordered.filter((unit) => unit !== safeFrom).map(optionOf);
  const travel = TRAVEL_UNITS.filter((u) => units.includes(u));
  const pickTravel = (unit) => {
    track(events.COMPARE_CHANGE, { converter: 'travel-chip', unit });
    // Рубли в руках у всех: нажатие на валюту всегда считает «рубли → эта валюта» (отправить семье, поменять в дорогу).
    onFrom('RUB');
    onTo(unit);
  };

  return (
    <section className="fe-panel fe-z8-conv z3-conv" data-block="currency-converter" aria-label={t('w6g.cur.converterTitle')}>
      <h2 className="fe-z8-conv__title">{t('w6g.cur.converterTitle')}</h2>
      <AmountField id={`${id}-amount`} amount={amount} text={text} setText={setText} locale={locale} label={`${t('w6g.cur.amount')}, ${unitMeta(safeFrom)?.symbol || safeFrom}`} />
      <QuickAmounts presets={presets} amount={amount} setText={setText} locale={locale} />
      <ConverterOut result={result} rate={rate} safeTo={safeTo} basisKey={basisKey} />
      <Z3PastCompare pair={pastPair} from={safeFrom} to={safeTo} amount={amount} nowRate={amount > 0 && result ? result.value / amount : 0} />
      <div className="fe-z8-conv__row z3-pair">
        <CurrencySelect
          label={t('w6g.cur.from')}
          value={safeFrom}
          options={fromOptions}
          onChange={onFrom}
          searchPlaceholder={t('z3.cur.searchHint')}
          emptyText={t('z3.cur.nothing')}
          className="fe-z8-conv__from"
        />
        <button
          type="button"
          className="fe-z8-swap fe-press"
          style={{ '--k8-turn': `${turns * 180}deg` }}
          onClick={swap}
          aria-label={t('w6g.cur.swap')}
          title={t('w6g.cur.swap')}
        >
          <ArrowRightLeft size={18} aria-hidden="true" />
        </button>
        <CurrencySelect
          label={t('w6g.cur.to')}
          value={safeTo}
          options={toOptions}
          onChange={onTo}
          searchPlaceholder={t('z3.cur.searchHint')}
          emptyText={t('z3.cur.nothing')}
          className="fe-z8-conv__to"
        />
      </div>
      {travel.length > 0 && (
        <div className="z3-pop">
          <p className="z3-pop__label">{t('z3.cur.popular')}</p>
          <div className="z3-pop__row" role="group" aria-label={t('z3.cur.popular')}>
            {travel.map((unit) => {
              const meta = coinOf(unit);
              return (
                <button
                  key={unit}
                  type="button"
                  className={cn('fe-z8-quick__btn fe-press z3-pop__btn', (unit === safeFrom || unit === safeTo) && 'is-active')}
                  aria-pressed={unit === safeFrom || unit === safeTo}
                  onClick={() => pickTravel(unit)}
                >
                  <CoinBadge className="z3-pop__coin" flag={meta.flag} symbol={meta.symbol} />
                  {chipName(unit, locale)}
                </button>
              );
            })}
          </div>
        </div>
      )}
    </section>
  );
}

/**
 * Конвертер на карточке курса: одна пара (например сум и рубль), сумма уже подставлена по валюте.
 * Подключается к странице курса одной строкой: `<CurrencyCardConverter code={code} />`.
 */
export function CurrencyCardConverter({ code }) {
  const t = useT();
  const { locale } = useLocale();
  const id = useId();
  const pair = parsePair(code);
  const { data: indicator } = useIndicator(pair ? code : null);
  const { data: series } = useIndicatorData(pair ? code : null, { limit: 5 });
  const edges = useMemo(() => {
    if (!pair) return [];
    const rows = (series?.data || []).filter((row) => Number.isFinite(Number(row?.value)));
    const lastRow = rows.length ? rows[rows.length - 1] : null;
    const value = Number(indicator?.current_value);
    return buildEdges([{
      code,
      unit: indicator?.unit,
      current_value: Number.isFinite(value) && value > 0 ? value : lastRow?.value,
      current_date: indicator?.current_date || lastRow?.date || null,
    }]);
  }, [pair, code, indicator, series]);
  // Валюты, в которые рубли отправляют и меняют в дорогу (сомони, сум, сом…): карточка открывается на «рубли → валюта».
  const [reversed, setReversed] = useState(Boolean(pair && pair.quote === 'RUB' && TRAVEL_UNITS.includes(pair.base)));
  const [turns, setTurns] = useState(0);
  const from = pair ? (reversed ? pair.quote : pair.base) : null;
  const to = pair ? (reversed ? pair.base : pair.quote) : null;
  const { text, setText, amount, presets } = useAmount(from, edges, locale);
  if (!pair || !edges.length || pair.base === pair.quote) return null;
  if (unitMeta(pair.base)?.crypto) return null;

  const result = amount != null ? convert(amount, from, to, edges) : null;
  const rate = describeRate(from, to, edges, locale);
  const pastPair = chartPairFor(edges, from, to);
  const basis = rateBasis(code);
  return (
    <section className="fe-panel z3-card-conv" data-block="currency-card-converter" aria-label={t('z3.cur.cardTitle')}>
      <div className="z3-card-conv__head">
        <h2 className="fe-z8-conv__title">{t('z3.cur.cardTitle')}</h2>
        <button
          type="button"
          className="fe-z8-swap fe-press"
          style={{ '--k8-turn': `${turns * 180}deg` }}
          onClick={() => { setReversed((v) => !v); setTurns((n) => n + 1); }}
          aria-label={t('w6g.cur.swap')}
          title={t('w6g.cur.swap')}
        >
          <ArrowRightLeft size={18} aria-hidden="true" />
        </button>
      </div>
      <p className="z3-card-conv__dir">{`${unitName(from, locale)} → ${unitName(to, locale)}`}</p>
      <AmountField id={`${id}-amount`} amount={amount} text={text} setText={setText} locale={locale} label={`${t('w6g.cur.amount')}, ${unitMeta(from)?.symbol || from}`} />
      <QuickAmounts presets={presets} amount={amount} setText={setText} locale={locale} />
      <ConverterOut result={result} rate={rate} safeTo={to} basisKey={basis ? `w6g.cur.basis.${basis}` : 'w6g.cur.basis.mix'} />
      <Z3PastCompare pair={pastPair} from={from} to={to} amount={amount} nowRate={amount > 0 && result ? result.value / amount : 0} />
      <p className="z3-card-conv__more">
        <Link to="/currencies" className="z3-card-conv__link">{t('z3.cur.otherPair')}</Link>
      </p>
    </section>
  );
}

export default Converter;
