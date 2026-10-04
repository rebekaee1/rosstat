import { useEffect, useRef, useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { MessageSquare, CheckCircle2 } from 'lucide-react';
import useDocumentMeta from '../lib/useMeta';
import { useAuth } from '../context/authContext';
import { track, events } from '../lib/track';
import {
  logoutUser, logoutAll, deleteAccount, submitFeedback, updateNewsletter, updateProfile,
} from '../lib/api';
import { apiErrorMessage } from '../lib/apiErrorMessage';
import { useT } from '../i18n';
import { cn } from '../lib/format';
import Button from '../components/Button';
import Spinner from '../components/Spinner';
import '../styles/w5-pages.css';

export default function Account() {
  const t = useT();
  useDocumentMeta({ title: t('account.metaTitle'), path: '/account', robots: 'noindex, nofollow' });
  const navigate = useNavigate();
  const location = useLocation();
  const { user, isLoading, isAuthed, setUser, refetch } = useAuth();
  const [busy, setBusy] = useState(false);
  const [busyKey, setBusyKey] = useState(null);
  const [msg, setMsg] = useState(null);
  const [err, setErr] = useState(null);
  const [nlBusy, setNlBusy] = useState(false);
  const [editName, setEditName] = useState(false);
  const [nameVal, setNameVal] = useState('');
  const [nameBusy, setNameBusy] = useState(false);
  const [nameErr, setNameErr] = useState(null);
  const [fbText, setFbText] = useState('');
  const [fbBusy, setFbBusy] = useState(false);
  const [fbSent, setFbSent] = useState(false);
  const [fbErr, setFbErr] = useState(null);
  const feedbackRef = useRef(null);

  useEffect(() => {
    if (!isLoading && !isAuthed) navigate('/login', { replace: true });
  }, [isLoading, isAuthed, navigate]);

  // Переход по «Оставить отзыв» (#feedback) — плавно проматываем к форме.
  useEffect(() => {
    if (isLoading || !isAuthed) return;
    if (location.hash === '#feedback' && feedbackRef.current) {
      feedbackRef.current.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  }, [location.hash, isLoading, isAuthed]);

  if (isLoading) {
    return (
      <div role="status" className="fe-data-page max-w-2xl mx-auto px-4 pt-28 pb-24 flex items-center gap-3 text-text-secondary">
        <Spinner size={18} />
        {t('common.loading')}
      </div>
    );
  }
  if (!user) return null;

  const run = async (fn, okMsg, refresh = true, key = null) => {
    setBusy(true); setBusyKey(key); setErr(null); setMsg(null);
    try {
      await fn();
      if (okMsg) setMsg(okMsg);
      if (refresh) await refetch();
      return true;
    } catch (e) {
      setErr(apiErrorMessage(e, t, 'account.errorGeneric'));
      return false;
    } finally {
      setBusy(false); setBusyKey(null);
    }
  };

  const doLogout = async () => {
    if (!await run(() => logoutUser(), null, false, 'logout')) return;
    setUser(null);
    navigate('/');
  };

  const doDelete = async () => {
    if (!window.confirm(t('account.deleteConfirm'))) return;
    if (!await run(() => deleteAccount(), null, false, 'delete')) return;
    setUser(null);
    navigate('/');
  };

  const startEditName = () => {
    setNameVal(user.display_name || '');
    setNameErr(null);
    setEditName(true);
  };

  const saveName = async () => {
    setNameBusy(true); setNameErr(null);
    try {
      const updated = await updateProfile(nameVal.trim());
      setUser(updated);
      setEditName(false);
    } catch (e) {
      setNameErr(apiErrorMessage(e, t, 'account.errorName'));
    } finally {
      setNameBusy(false);
    }
  };

  const toggleNewsletter = async () => {
    const subscribe = !user.newsletter;
    setNlBusy(true); setErr(null);
    try {
      const updated = await updateNewsletter(subscribe);
      setUser(updated);
      track(subscribe ? events.NEWSLETTER_OPT_IN : events.NEWSLETTER_OPT_OUT, { channel: 'account' });
    } catch (e) {
      setErr(apiErrorMessage(e, t, 'account.errorNewsletter'));
    } finally {
      setNlBusy(false);
    }
  };

  const sendFeedback = async () => {
    const text = fbText.trim();
    if (text.length < 5) { setFbErr(t('account.feedbackTooShort')); return; }
    setFbBusy(true); setFbErr(null);
    try {
      await submitFeedback({ message: text });
      track(events.FEEDBACK_SUBMIT);
      setFbSent(true);
      setFbText('');
    } catch (e) {
      setFbErr(apiErrorMessage(e, t, 'account.feedbackError'));
    } finally {
      setFbBusy(false);
    }
  };

  const empty = t('account.empty');
  const fieldRow = (label, value) => (
    <div className="flex justify-between gap-4">
      <dt className="text-text-secondary">{label}</dt>
      <dd className="text-text-primary text-right">{value || empty}</dd>
    </div>
  );

  return (
    <div className="fe-data-page max-w-2xl mx-auto px-4 pt-28 pb-24">
      <header className="fe-reveal mb-6 flex items-center gap-4">
        <span className="w5-avatar" aria-hidden="true">
          {(user.display_name || user.email || '?').trim().charAt(0).toUpperCase()}
        </span>
        <div className="min-w-0">
          <h1 className="font-display text-2xl font-bold text-text-primary">{t('account.title')}</h1>
          <p className="truncate text-sm text-text-secondary">{t('w5.account.signedInAs')} {user.email}</p>
        </div>
      </header>
      <p className="mb-6 text-sm text-text-secondary">
        {t('account.intro')}
      </p>

      <section className="fe-panel fe-reveal rounded-3xl bg-surface border border-border-subtle p-5 mb-5 shadow-sm">
        <h2 className="text-base font-semibold text-text-primary mb-3">{t('account.profile')}</h2>
        <dl className="text-sm space-y-1.5">
          <div className="flex justify-between items-center gap-4 min-h-[28px]">
            <dt className="text-text-secondary shrink-0">{t('account.name')}</dt>
            <dd className="text-text-primary text-right flex-1 min-w-0">
              {editName ? (
                <div className="flex items-center gap-2 justify-end">
                  <input
                    value={nameVal}
                    onChange={(e) => setNameVal(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') { e.preventDefault(); saveName(); }
                      if (e.key === 'Escape') setEditName(false);
                    }}
                    maxLength={120}
                    autoFocus
                    placeholder={t('account.namePlaceholder')}
                    aria-label={t('account.nameAria')}
                    aria-invalid={nameErr ? true : undefined}
                    aria-describedby={nameErr ? 'account-name-error' : undefined}
                    className={cn(
                      'min-w-0 flex-1 max-w-[16rem] px-2.5 py-1 rounded-lg bg-obsidian-lighter/50 border text-text-primary focus:outline-none pointer-coarse:min-h-11',
                      nameErr ? 'border-negative focus:border-negative' : 'border-border-subtle focus:border-champagne/50',
                    )}
                  />
                  <Button variant="ghost" size="sm" onClick={saveName} loading={nameBusy} className="shrink-0 px-2">
                    {t('common.save')}
                  </Button>
                  <Button variant="ghost" size="sm" onClick={() => setEditName(false)} disabled={nameBusy} className="shrink-0 px-2 text-text-tertiary!">
                    {t('common.cancel')}
                  </Button>
                </div>
              ) : (
                <span className="inline-flex items-center gap-2 justify-end">
                  <span className="truncate">{user.display_name || empty}</span>
                  <Button variant="ghost" size="sm" onClick={startEditName} className="shrink-0 px-2">
                    {t('account.edit')}
                  </Button>
                </span>
              )}
            </dd>
          </div>
          <div id="account-name-error" role="alert" className="text-xs text-negative text-right empty:hidden">{nameErr}</div>
          {fieldRow(t('common.email'), user.email)}
          {user.phone && fieldRow(t('account.phone'), user.phone)}
        </dl>
      </section>

      <section
        ref={feedbackRef}
        id="feedback"
        className="fe-panel fe-reveal rounded-3xl bg-surface border border-border-subtle p-5 mb-5 shadow-sm scroll-mt-28"
      >
        <h2 className="flex items-center gap-2 text-base font-semibold text-text-primary mb-2">
          <MessageSquare className="w-4 h-4 text-champagne" />
          {t('account.feedback')}
        </h2>
        {fbSent ? (
          <div role="status" className="flex items-start gap-2.5 rounded-xl bg-positive/10 border border-positive/30 px-4 py-3 text-sm text-text-primary">
            <CheckCircle2 className="w-5 h-5 text-positive shrink-0 mt-0.5" aria-hidden="true" />
            <div>
              <p className="font-medium">{t('account.feedbackSentTitle')}</p>
              <p className="text-text-secondary mt-0.5">{t('account.feedbackSentBody')}</p>
              <Button variant="ghost" size="sm" onClick={() => setFbSent(false)} className="mt-2 -ml-3">
                {t('account.feedbackAgain')}
              </Button>
            </div>
          </div>
        ) : (
          <>
            <p className="text-sm text-text-tertiary mb-3">
              {t('account.feedbackIntro')}
            </p>
            <textarea
              value={fbText}
              onChange={(e) => setFbText(e.target.value)}
              rows={4}
              maxLength={4000}
              placeholder={t('account.feedbackPlaceholder')}
              aria-label={t('account.feedback')}
              aria-invalid={fbErr ? true : undefined}
              aria-describedby={fbErr ? 'account-feedback-error' : undefined}
              className={cn(
                'w-full px-3.5 py-2.5 rounded-xl bg-obsidian-lighter/50 border text-text-primary focus:outline-none resize-y',
                fbErr ? 'border-negative focus:border-negative' : 'border-border-subtle focus:border-champagne/50',
              )}
            />
            <div className="flex items-center justify-between gap-3 mt-2">
              <span className="text-xs text-text-tertiary">{t('account.feedbackReplyNote')}</span>
              <Button
                onClick={sendFeedback}
                disabled={fbText.trim().length < 5}
                loading={fbBusy}
                className="shrink-0"
              >
                {fbBusy ? t('account.feedbackSending') : t('account.feedbackSend')}
              </Button>
            </div>
            <div id="account-feedback-error" role="alert" className="text-sm text-negative mt-2 empty:hidden">{fbErr}</div>
          </>
        )}
        <p className="text-xs text-text-tertiary mt-4 pt-3 border-t border-border-subtle/70">
          {user.newsletter ? t('account.newsletterOn') : t('account.newsletterOff')}
          <Button variant="ghost" size="sm" onClick={toggleNewsletter} loading={nlBusy} className="ml-1 px-2">
            {user.newsletter ? t('account.unsubscribe') : t('account.subscribe')}
          </Button>
        </p>
      </section>

      {user.is_admin && (
        <section className="fe-panel rounded-3xl bg-surface border border-border-champagne p-5 mb-5 shadow-sm">
          <h2 className="text-base font-semibold text-text-primary mb-2">{t('account.admin')}</h2>
          <p className="text-sm text-text-secondary mb-3">
            {t('account.adminBody')}
          </p>
          <Button as={Link} to="/admin/bi">
            {t('account.adminCta')}
          </Button>
        </section>
      )}

      <div role="status" className="empty:hidden mb-4">
        {msg && (
          <div className="flex items-start gap-2 rounded-xl border border-positive/30 bg-positive/10 px-3.5 py-2.5 text-sm text-text-primary">
            <CheckCircle2 className="w-4 h-4 text-positive shrink-0 mt-0.5" aria-hidden="true" />
            {msg}
          </div>
        )}
      </div>
      <div role="alert" className="empty:hidden mb-4">
        {err && <div className="rounded-xl border border-negative/40 px-3.5 py-2.5 text-sm text-negative">{err}</div>}
      </div>

      <div className="flex flex-wrap gap-3">
        <Button variant="secondary" onClick={doLogout} disabled={busy} loading={busyKey === 'logout'}>{t('account.logout')}</Button>
        <Button
          variant="secondary"
          onClick={() => run(() => logoutAll(), t('account.logoutAllOk'), true, 'logoutAll')}
          disabled={busy}
          loading={busyKey === 'logoutAll'}
          title={t('account.logoutAllTitle')}
          className="text-text-secondary!"
        >
          {t('account.logoutAll')}
        </Button>
        <Button
          variant="secondary"
          onClick={doDelete}
          disabled={busy}
          loading={busyKey === 'delete'}
          className="ml-auto text-negative! border-negative/40! hover:bg-negative/10!"
        >
          {t('account.delete')}
        </Button>
      </div>
    </div>
  );
}
