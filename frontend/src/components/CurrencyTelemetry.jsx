// Верх страницы курса: что люди хотят знать про валюту: сколько сейчас, как изменился за неделю,
// месяц и год, между чем и чем колебался за последний год. Вместо «среднего за 28 лет» и «исторического максимума».
import { useMemo } from 'react';
import DeltaBadge from './DeltaBadge';
import { SkeletonBox } from './Skeleton';
import { useIndicatorData } from '../lib/hooks';
import { indicatorPolarity } from '../lib/deltaTone';
import { currencyWindows, parsePair, rateBasis, unitMeta } from '../lib/currencyRates';
import { formatDate, formatValue } from '../lib/format';
import { useLocale, useT } from '../i18n';
import '../styles/indicator-russia.css';
import '../styles/x2-indicator.css';
import '../styles/w6-g.css';

const WINDOW_PARAMS = { limit: 420 };
const NBSP = String.fromCharCode(160);

function signedPercent(value, locale) {
  const n = Number(value);
  if (!Number.isFinite(n)) return '—';
  if (Math.abs(n) < 0.005) return `0${locale === 'en' ? '.00' : ',00'}`;
  const body = formatValue(Math.abs(n), 2, locale);
  return `${n > 0 ? '+' : '−'}${body}`;
}

function Tile({ label, children, foot, delay = 0 }) {
  return (
    <div
      style={{ '--i': delay, '--fe-delay': `${delay * 40}ms`, '--fe-duration': '0.4s', '--fe-rise': '12px' }}
      className="fe-reveal fe-reveal--free fe-tele"
    >
      <p className="fe-tele__label">{label}</p>
      <p className="fe-tele__value">{children}</p>
      {foot ? <div className="fe-tele__foot">{foot}</div> : null}
    </div>
  );
}

export default function CurrencyTelemetry({ code, loading = false, fallback = null }) {
  const t = useT();
  const { locale } = useLocale();
  const { data, isLoading, isError } = useIndicatorData(code, WINDOW_PARAMS);
  const windows = useMemo(() => currencyWindows(data?.data), [data]);

  if (loading || isLoading) {
    return (
      <section className="fe-tele-section" aria-busy="true">
        <div className="fe-tele-grid" aria-hidden="true">
          {[...Array(4)].map((_, i) => <SkeletonBox key={i} className="fe-tele-skeleton" />)}
        </div>
      </section>
    );
  }
  if (isError || !windows) return fallback;

  const pair = parsePair(code);
  const symbol = pair ? unitMeta(pair.quote).symbol : '';
  const digits = Math.abs(windows.last.value) >= 1000 ? 0 : 2;
  const money = (value) => `${formatValue(value, digits, locale)}${NBSP}${symbol}`.trim();

  // Для тех, кто отправляет рубли: если сомони в рублях подешевел, за те же рубли получается больше сомони.
  const sendParts = pair && pair.quote === 'RUB' && !unitMeta(pair.base)?.crypto
    ? [['week', windows.week], ['month', windows.month], ['year', windows.year]].filter(([, v]) => v != null).map(([id, v]) => {
      const gain = ((1 / (1 + v / 100)) - 1) * 100;
      const abs = Math.abs(gain);
      const how = abs < 0.1 ? t('r2z3.tele.same') : t(gain > 0 ? 'r2z3.tele.more' : 'r2z3.tele.less', { pct: formatValue(abs, abs < 10 ? 1 : 0, locale) });
      return `${t(`r2z3.tele.in.${id}`)} ${how}`;
    })
    : [];
  const periods = [
    { id: 'week', label: t('w6g.cur.tele.week'), value: windows.week },
    { id: 'month', label: t('w6g.cur.tele.month'), value: windows.month },
    { id: 'year', label: t('w6g.cur.tele.year'), value: windows.year },
  ].filter((item) => item.value != null);

  return (
    <section className="fe-tele-section" data-block="currency-telemetry">
      <div className="fe-tele-grid">
        <Tile label={t('w6g.cur.tele.now')} delay={0} foot={<p className="fe-tele__meta">{formatDate(windows.last.date, 'day', locale)}</p>}>
          <span className="fe-tele__num">{formatValue(windows.last.value, digits, locale)}</span>
          {symbol ? <span className="fe-tele__unit">{symbol}</span> : null}
        </Tile>
        {periods.map((item, index) => (
          <Tile
            key={item.id}
            label={item.label}
            delay={index + 1}
            foot={(
              <p className="fe-tele__delta">
                <DeltaBadge delta={Math.abs(item.value) < 0.005 ? 0 : item.value} polarity={indicatorPolarity(code)}>
                  {t(Math.abs(item.value) < 0.005 ? 'w6g.cur.tele.flat' : item.value > 0 ? 'r2z3.tele.up' : 'r2z3.tele.down')}
                </DeltaBadge>
              </p>
            )}
          >
            <span className="fe-tele__num">{signedPercent(item.value, locale)}</span>
            <span className="fe-tele__unit">%</span>
          </Tile>
        ))}
      </div>
      {sendParts.length > 0 && pair && (
        <p className="fe-w6g-range z3-send" data-testid="currency-send">
          {t('r2z3.tele.send', { parts: sendParts.join(', ') })}
        </p>
      )}
      {rateBasis(code) && (
        <p className="fe-w6g-range" data-testid="currency-basis">
          {t(rateBasis(code) === 'cb' ? 'r2z3.tele.basis.cb' : `w6g.cur.tele.basis.${rateBasis(code)}`, { date: formatDate(windows.last.date, 'day', locale) })}
        </p>
      )}
      {windows.min && windows.max && windows.min.date !== windows.max.date && (
        <p className="fe-w6g-range" data-testid="currency-range">
          {t('w6g.cur.tele.range', {
            min: money(windows.min.value),
            minDate: formatDate(windows.min.date, 'day', locale),
            max: money(windows.max.value),
            maxDate: formatDate(windows.max.date, 'day', locale),
          })}
        </p>
      )}
    </section>
  );
}
