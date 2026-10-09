import { useEffect, useState } from 'react';
import { CalendarPlus, Copy } from 'lucide-react';
import { useT } from '../../i18n';
import { createCalendarFeed, calendarFeedLinks, deleteCalendarFeed, fetchCalendarFeed } from '../../lib/cabinetApi';
import { cabinetErrorCode, cabinetErrorKey } from '../../lib/cabinetItems';
import Button from '../Button';

/**
 * Личный календарь выходов: ссылка, которую календарь телефона подписывает сам и показывает даты выхода
 * новых значений по отслеживаемым федеральным показателям. Ссылка показывается один раз (на сервере только хэш);
 * новая ссылка гасит старую.
 */
export default function CalendarFeed() {
  const t = useT();
  const [active, setActive] = useState(null);
  const [links, setLinks] = useState(null);
  const [busy, setBusy] = useState(null);
  const [error, setError] = useState(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    let alive = true;
    Promise.resolve()
      .then(() => fetchCalendarFeed())
      .then((res) => { if (alive) setActive(Boolean(res?.active)); })
      .catch(() => { if (alive) setActive(false); });
    return () => { alive = false; };
  }, []);

  const issue = async () => {
    setBusy('issue'); setError(null); setCopied(false);
    try {
      const res = await createCalendarFeed();
      setLinks(calendarFeedLinks(res?.path));
      setActive(true);
    } catch (err) {
      setError(t(cabinetErrorKey(cabinetErrorCode(err))));
    } finally {
      setBusy(null);
    }
  };

  const revoke = async () => {
    setBusy('revoke'); setError(null);
    try {
      await deleteCalendarFeed();
      setActive(false);
      setLinks(null);
    } catch (err) {
      setError(t(cabinetErrorKey(cabinetErrorCode(err))));
    } finally {
      setBusy(null);
    }
  };

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(links.https);
      setCopied(true);
    } catch {
      setError(t('c11b.cal.copyFailed'));
    }
  };

  return (
    <section className="c11b-group c11b-cal" aria-label={t('c11b.cal.title')}>
      <h3 className="c11b-group__title">{t('c11b.cal.title')}</h3>
      <p className="c11b-hint">{t('c11b.cal.intro')}</p>
      {links?.https ? (
        <div className="c11b-cal__link">
          <input readOnly value={links.https} onFocus={(e) => e.target.select()} aria-label={t('c11b.cal.linkAria')} className="fe-k8-well c11b-row__input" />
          <Button variant="secondary" size="sm" onClick={copy} className="gap-1.5">
            <Copy size={14} aria-hidden="true" />
            {copied ? t('c11b.cal.copied') : t('c11b.cal.copy')}
          </Button>
          <Button as="a" href={links.webcal} variant="primary" size="sm" className="gap-1.5">
            <CalendarPlus size={14} aria-hidden="true" />
            {t('c11b.cal.open')}
          </Button>
        </div>
      ) : null}
      {links?.https ? <p className="c11b-hint">{t('c11b.cal.once')}</p> : null}
      <div className="c11b-cal__actions">
        <Button variant={active ? 'secondary' : 'primary'} size="sm" onClick={issue} loading={busy === 'issue'} disabled={active === null || busy === 'revoke'}>
          {active ? t('c11b.cal.renew') : t('c11b.cal.enable')}
        </Button>
        {active ? (
          <Button variant="ghost" size="sm" onClick={revoke} loading={busy === 'revoke'} disabled={busy === 'issue'}>
            {t('c11b.cal.disable')}
          </Button>
        ) : null}
      </div>
      {active && !links ? <p className="c11b-hint">{t('c11b.cal.active')}</p> : null}
      <p role="alert" className="c11b-row__err empty:hidden">{error}</p>
    </section>
  );
}
