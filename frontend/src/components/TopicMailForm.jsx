import { useId, useState } from 'react';
import { Link } from 'react-router-dom';
import { Mail } from 'lucide-react';
import { useT } from '../i18n';
import { useAuth } from '../context/authContext';
import { subscribeTopicMail } from '../lib/api';
import { useTopicMailEnabled } from '../lib/topicMail';
import { apiErrorMessage } from '../lib/apiErrorMessage';
import { track, events } from '../lib/track';
import { cn } from '../lib/format';
import Button from './Button';
import '../styles/acq-mail.css';

/**
 * «Присылать новые значения на почту» (совет 19.11.2026): почтовая часть строки «присылать» под числом
 * и предложения после скачивания. Без пароля: гость вводит адрес и даёт согласие → письмо «подтвердите»;
 * вошедший нажимает одну кнопку. Письмо о новом значении уходит сводкой «колокольчика» (не чаще раза в день).
 *
 *     <TopicMailForm code="fuel-diesel" topic="diesel" source="line" />
 *
 * Свойства:
 *  - `code`    код федерального показателя (тот же, что у колокольчика `WatchButton`)
 *  - `topic`   ключ темы строки «присылать» (для событий; у бота те же ключи), необязательно
 *  - `source`  'line' (строка под числом) | 'download' (после скачивания) — в событиях
 *  - `compact` без подписи над полем (строка под числом)
 * Флаг сервера выключен — компонент ничего не рисует.
 */

function useAuthSafe() {
  try { return useAuth(); } catch { return { isAuthed: false, isLoading: false }; }
}

function pagePath() {
  try { return String(window.location.pathname || '/').slice(0, 200); } catch { return null; }
}

export default function TopicMailForm({ code, topic, source = 'line', compact = false, className, onDone }) {
  const t = useT();
  const enabled = useTopicMailEnabled();
  const { isAuthed, isLoading } = useAuthSafe();
  const ids = useId();
  const [email, setEmail] = useState('');
  const [consent, setConsent] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [done, setDone] = useState(null); // { key, email? }

  if (!enabled || !code || isLoading) return null;

  const submit = async (e) => {
    e?.preventDefault?.();
    setError(null);
    if (!isAuthed && !consent) {
      setError(t('topicMail.consentRequired'));
      return;
    }
    track(events.SUBSCRIBE_LINE_CLICK, { topic: topic || code, channel: 'email', source, path: pagePath() });
    setBusy(true);
    try {
      const res = await subscribeTopicMail(isAuthed
        ? { code }
        : { code, email: email.trim(), consent: true, page: pagePath() });
      const key = {
        confirm_sent: 'topicMail.doneGuest',
        subscribed: 'topicMail.doneSubscribed',
        confirm_email: 'topicMail.doneConfirmEmail',
        no_email: 'topicMail.doneNoEmail',
      }[res?.status] || 'topicMail.doneSubscribed';
      setDone({ key, email: res?.email || email.trim() });
      track(events.TOPIC_MAIL_DONE, { topic: topic || code, status: res?.status || 'unknown', source });
      onDone?.(res);
    } catch (err) {
      setError(apiErrorMessage(err, t));
    } finally {
      setBusy(false);
    }
  };

  if (done) {
    return (
      <p role="status" className={cn('acq-mail-done text-sm text-text-secondary', className)} data-testid="topic-mail-done">
        {t(done.key, { email: done.email })}
        {done.key === 'topicMail.doneNoEmail' ? (
          <> <Link to="/account" className="acq-mail-link">{t('topicMail.toAccount')}</Link></>
        ) : null}
      </p>
    );
  }

  if (isAuthed) {
    return (
      <div className={cn('acq-mail', className)} data-no-export="true">
        <Button type="button" variant="secondary" size="sm" loading={busy} onClick={submit}
          className="acq-mail-btn" data-testid="topic-mail-one-click">
          <Mail size={16} aria-hidden="true" />
          <span>{t('topicMail.sendToMail')}</span>
        </Button>
        {error ? <p role="alert" className="acq-mail-error mt-2">{error}</p> : null}
      </div>
    );
  }

  return (
    <form onSubmit={submit} className={cn('acq-mail', className)} data-no-export="true" data-track="topic-mail" noValidate>
      {!compact ? <p className="acq-mail-lead text-sm text-text-secondary mb-2">{t('topicMail.lead')}</p> : null}
      <div className="acq-mail-row">
        <label htmlFor={`${ids}-email`} className="sr-only">{t('common.email')}</label>
        <input id={`${ids}-email`} type="email" name="email" required autoComplete="email" inputMode="email"
          value={email} onChange={(e) => setEmail(e.target.value)} placeholder={t('w5.auth.emailPlaceholder')}
          className={cn('fe-input acq-mail-input px-3 py-2 rounded-xl text-text-primary focus:outline-none', error && 'is-invalid')}
          aria-describedby={error ? `${ids}-err` : undefined} />
        <Button type="submit" size="sm" loading={busy} className="acq-mail-btn font-semibold">
          {t('topicMail.submit')}
        </Button>
      </div>
      <label className="acq-mail-consent text-xs text-text-secondary">
        <input type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)} />
        <span>
          {t('topicMail.consentBefore')}{' '}
          <Link to="/privacy" target="_blank" rel="noopener" className="acq-mail-link">{t('topicMail.consentLink')}</Link>
        </span>
      </label>
      <p id={`${ids}-err`} role="alert" className="acq-mail-error">{error}</p>
    </form>
  );
}
