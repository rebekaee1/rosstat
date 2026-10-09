import { useState } from 'react';
import { Link } from 'react-router-dom';
import { BellOff, Check } from 'lucide-react';
import { useLocale, useT } from '../../i18n';
import { formatPeriodShort, formatValueWithUnit, cn } from '../../lib/format';
import { cabinetErrorKey, watchHref } from '../../lib/cabinetItems';
import { removeWatch } from '../../lib/cabinetStore';
import { useFeed } from '../../lib/useCabinet';
import Button from '../Button';
import Spinner from '../Spinner';
import CalendarFeed from './CalendarFeed';

/** «3,2 % за сентябрь 2026»: последнее значение ряда словами, без кодов. */
function latestText(w, t, locale) {
  if (!w.available) return t('c11b.watch.gone');
  if (!w.latest_date) return t('c11b.watch.noData');
  const period = formatPeriodShort(w.latest_date, w.frequency || 'annual', locale);
  if (w.latest_value == null) return t('c11b.watch.latestDate', { period });
  return t('c11b.watch.latest', { value: formatValueWithUnit(w.latest_value, w.unit || '', undefined, locale), period });
}

function WatchRow({ w, t, locale, onSeen, onStop }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const href = w.available ? watchHref(w) : null;
  const title = w.title || t('c11b.watch.untitled');
  const run = async (fn) => {
    setBusy(true);
    setError(null);
    const res = await fn();
    setBusy(false);
    if (!res.ok) setError(t(cabinetErrorKey(res.reason)));
  };
  const body = (
    <>
      <span className="c11b-row__title">
        {title}
        {w.is_new ? <span className="c11b-pill">{t('c11b.feed.new')}</span> : null}
      </span>
      <span className="c11b-row__sub">
        {[w.country_name, latestText(w, t, locale)].filter(Boolean).join(', ')}
      </span>
    </>
  );
  return (
    <li className={cn('c11b-row', !w.available && 'is-gone')}>
      {href ? <Link to={href} className="c11b-row__main">{body}</Link> : <span className="c11b-row__main">{body}</span>}
      <span className="c11b-row__actions">
        {w.is_new ? (
          <button type="button" className="c11b-icon-btn" disabled={busy} onClick={() => run(() => onSeen([w.id]))} aria-label={t('c11b.feed.seenOne', { name: title })} title={t('c11b.feed.seenOneTitle')}>
            <Check size={15} aria-hidden="true" />
          </button>
        ) : null}
        <button type="button" className="c11b-icon-btn" disabled={busy} onClick={() => run(() => onStop(w))} aria-label={t('c11b.watch.stopAria', { name: title })} title={t('c11b.watch.stop')}>
          <BellOff size={15} aria-hidden="true" />
        </button>
      </span>
      <span role="alert" className="c11b-row__err empty:hidden">{error}</span>
    </li>
  );
}

/**
 * Раздел «Слежу»: что вышло нового с прошлого визита, за чем вы следите и личный календарь выходов.
 * Новое считается при открытии кабинета (последняя дата ряда против той, что вы уже видели), ничего не отправляется.
 */
export default function WatchList() {
  const t = useT();
  const { locale } = useLocale();
  const feed = useFeed();
  const [seenBusy, setSeenBusy] = useState(false);

  if (feed.status === 'idle' || (feed.status === 'loading' && !feed.watches.length)) {
    return <div role="status" className="c11b-empty"><Spinner size={16} /> {t('common.loading')}</div>;
  }
  if (feed.status === 'error' && !feed.watches.length) {
    return (
      <div role="alert" className="c11b-empty">
        <p>{t('c11b.err.generic')}</p>
        <Button variant="secondary" size="sm" onClick={feed.reload}>{t('common.retry')}</Button>
      </div>
    );
  }

  const markAll = async () => {
    setSeenBusy(true);
    await feed.markSeen();
    setSeenBusy(false);
  };
  const stop = (w) => removeWatch(w.subject_kind, w.subject_key);

  return (
    <div>
      {feed.items.length > 0 ? (
        <section className="c11b-group" aria-label={t('c11b.feed.title')}>
          <div className="c11b-group__head">
            <h3 className="c11b-group__title">{t('c11b.feed.title')}</h3>
            <Button variant="secondary" size="sm" onClick={markAll} loading={seenBusy}>{t('c11b.feed.seenAll')}</Button>
          </div>
          <ul className="c11b-list">
            {feed.items.map((w) => <WatchRow key={`n-${w.id}`} w={w} t={t} locale={locale} onSeen={feed.markSeen} onStop={stop} />)}
          </ul>
        </section>
      ) : null}

      <section className="c11b-group" aria-label={t('c11b.watch.title')}>
        <h3 className="c11b-group__title">{t('c11b.watch.title')}</h3>
        {feed.watches.length ? (
          <ul className="c11b-list">
            {feed.watches.map((w) => <WatchRow key={w.id} w={w} t={t} locale={locale} onSeen={feed.markSeen} onStop={stop} />)}
          </ul>
        ) : (
          <div className="c11b-empty">
            <p>{t('c11b.watch.empty')}</p>
            <Button as={Link} to="/russia" variant="secondary" size="sm">{t('c11b.watch.emptyCta')}</Button>
          </div>
        )}
        {feed.watches.length ? <p className="c11b-hint">{t('c11b.watch.count', { n: feed.watches.length, max: feed.limit })}</p> : null}
        <p className="c11b-hint">{t('c11b.watch.noMail')}</p>
      </section>

      <CalendarFeed />
    </div>
  );
}
