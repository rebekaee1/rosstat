// Нефть Brent: биржевая котировка рядом со спотом EIA (круг 13, R-BRENT).
// Блок рисуется только когда сервер отдал снимок `brent` из биржевого источника (флаг на сервере включают после договора
// с Мосбиржей); пока флаг выключен, в ленте спот EIA, снимок биржевым не считается, и страница прежняя.
// Подпись обязательна: что это за цена (ближайший фьючерс), с какой задержкой и что график ниже — другой, недельный ряд.
import { useLiveQuote } from '../lib/tickerLive';
import { tickerSourceKind } from '../lib/tickerFormat';
import { useLocale, useT } from '../i18n';
import '../styles/c13d-fresh-note.css';

function money(value, locale) {
  const tag = locale === 'en' ? 'en-US' : 'ru-RU';
  const body = Number(value).toLocaleString(tag, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  return locale === 'en' ? `$${body}` : `${body}\u00a0$`;
}

export default function BrentLiveNote({ code, className = '' }) {
  const t = useT();
  const { locale } = useLocale();
  const snap = useLiveQuote(code === 'brent' ? 'brent' : null);
  if (!snap || tickerSourceKind(snap.source) !== 'market' || !(Number(snap.price) > 0) || snap.stale === true) return null;

  const contract = snap.contract || 'BR';
  const price = money(snap.price, locale);
  let text;
  if (snap.market_open) {
    const when = snap.as_of ? new Date(snap.as_of) : null;
    const time = when && !Number.isNaN(when.getTime())
      ? when.toLocaleTimeString(locale === 'en' ? 'en-GB' : 'ru-RU', { hour: '2-digit', minute: '2-digit', timeZone: 'Europe/Moscow' })
      : '';
    text = t('c13b.brentLive.body', { contract, price, minutes: snap.delay_minutes || 15, time });
  } else {
    const day = snap.as_of_day || snap.as_of_date;
    const date = day
      ? new Date(`${day}T12:00:00Z`).toLocaleDateString(locale === 'en' ? 'en-US' : 'ru-RU', { day: 'numeric', month: 'long', timeZone: 'UTC' })
      : '';
    text = t('c13b.brentLive.bodyClosed', { contract, price, date });
  }

  return (
    <section
      className={`c13d-note rounded-3xl fe-glass-lite${className ? ` ${className}` : ''}`}
      aria-labelledby="c13b-brent-live-title"
      data-testid="brent-live-note"
    >
      <span className="c13d-note__mark" aria-hidden="true" />
      <div className="c13d-note__body">
        <h2 id="c13b-brent-live-title" className="c13d-note__title">{t('c13b.brentLive.title')}</h2>
        <p className="c13d-note__lead">{text}</p>
        <p className="c13d-note__meta">{t('c13b.brentLive.tail')}</p>
      </div>
    </section>
  );
}
