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

export default function Account() {
  const t = useT();
  useDocumentMeta({ title: t('account.metaTitle'), path: '/account', robots: 'noindex, nofollow' });
  const navigate = useNavigate();
  const location = useLocation();
  const { user, isLoading, isAuthed, setUser, refetch } = useAuth();
  const [busy, setBusy] = useState(false);
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
    return <div className="max-w-2xl mx-auto px-4 pt-28 pb-24 text-text-secondary">{t('common.loading')}</div>;
  }
  if (!user) return null;

  const run = async (fn, okMsg) => {
    setBusy(true); setErr(null); setMsg(null);
    try {
      await fn();
      if (okMsg) setMsg(okMsg);
      await refetch();
    } catch (e) {
      setErr(apiErrorMessage(e, t, 'account.errorGeneric'));
    } finally {
      setBusy(false);
    }
  };

  const doLogout = async () => {
    await run(() => logoutUser());
    setUser(null);
    navigate('/');
  };

  const doDelete = async () => {
    if (!window.confirm(t('account.deleteConfirm'))) return;
    await run(() => deleteAccount());
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
      <dt className="text-text-tertiary">{label}</dt>
      <dd className="text-text-primary text-right">{value || empty}</dd>
    </div>
  );

  return (
    <div className="max-w-2xl mx-auto px-4 pt-28 pb-24">
      <h1 className="text-2xl font-display font-bold text-text-primary mb-2">{t('account.title')}</h1>
      <p className="text-sm text-text-secondary mb-6">
        {t('account.intro')}
      </p>

      <section className="rounded-2xl bg-surface border border-border-subtle p-5 mb-5 shadow-sm">
        <h2 className="text-sm font-semibold text-text-secondary mb-3">{t('account.profile')}</h2>
        <dl className="text-sm space-y-1.5">
          <div className="flex justify-between items-center gap-4 min-h-[28px]">
            <dt className="text-text-tertiary shrink-0">{t('account.name')}</dt>
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
                    className="min-w-0 flex-1 max-w-[16rem] px-2.5 py-1 rounded-lg bg-obsidian-lighter/50 border border-border-subtle text-text-primary focus:outline-none focus:border-champagne/50"
                  />
                  <button onClick={saveName} disabled={nameBusy} className="shrink-0 text-champagne text-xs font-medium hover:underline disabled:opacity-50">
                    {nameBusy ? '…' : t('common.save')}
                  </button>
                  <button onClick={() => setEditName(false)} disabled={nameBusy} className="shrink-0 text-text-tertiary text-xs hover:text-text-primary disabled:opacity-50">
                    {t('common.cancel')}
                  </button>
                </div>
              ) : (
                <span className="inline-flex items-center gap-2 justify-end">
                  <span className="truncate">{user.display_name || empty}</span>
                  <button onClick={startEditName} className="shrink-0 text-champagne text-xs hover:underline">
                    {t('account.edit')}
                  </button>
                </span>
              )}
            </dd>
          </div>
          {nameErr && <div className="text-xs text-negative text-right">{nameErr}</div>}
          {fieldRow(t('common.email'), user.email)}
          {user.phone && fieldRow(t('account.phone'), user.phone)}
        </dl>
      </section>

      <section
        ref={feedbackRef}
        id="feedback"
        className="rounded-2xl bg-surface border border-border-subtle p-5 mb-5 shadow-sm scroll-mt-28"
      >
        <h2 className="flex items-center gap-2 text-sm font-semibold text-text-secondary mb-2">
          <MessageSquare className="w-4 h-4 text-champagne" />
          {t('account.feedback')}
        </h2>
        {fbSent ? (
          <div className="flex items-start gap-2.5 rounded-xl bg-positive/10 border border-positive/30 px-4 py-3 text-sm text-text-primary">
            <CheckCircle2 className="w-5 h-5 text-positive shrink-0 mt-0.5" />
            <div>
              <p className="font-medium">{t('account.feedbackSentTitle')}</p>
              <p className="text-text-secondary mt-0.5">{t('account.feedbackSentBody')}</p>
              <button onClick={() => setFbSent(false)} className="mt-2 text-xs text-champagne hover:underline">
                {t('account.feedbackAgain')}
              </button>
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
              className="w-full px-3.5 py-2.5 rounded-xl bg-obsidian-lighter/50 border border-border-subtle text-text-primary focus:outline-none focus:border-champagne/50 resize-y"
            />
            <div className="flex items-center justify-between gap-3 mt-2">
              <span className="text-xs text-text-tertiary">{t('account.feedbackReplyNote')}</span>
              <button
                onClick={sendFeedback}
                disabled={fbBusy || fbText.trim().length < 5}
                className="px-4 py-2 rounded-xl bg-champagne text-white text-sm font-medium hover:bg-champagne-muted disabled:opacity-50"
              >
                {fbBusy ? t('account.feedbackSending') : t('account.feedbackSend')}
              </button>
            </div>
            {fbErr && <div className="text-sm text-negative mt-2">{fbErr}</div>}
          </>
        )}
        <p className="text-xs text-text-tertiary mt-4 pt-3 border-t border-border-subtle/70">
          {user.newsletter ? t('account.newsletterOn') : t('account.newsletterOff')}
          <button
            onClick={toggleNewsletter}
            disabled={nlBusy}
            className="text-champagne hover:underline disabled:opacity-50"
          >
            {user.newsletter ? t('account.unsubscribe') : t('account.subscribe')}
          </button>
        </p>
      </section>

      {user.is_admin && (
        <section className="rounded-2xl bg-surface border border-border-champagne p-5 mb-5 shadow-sm">
          <h2 className="text-sm font-semibold text-text-secondary mb-2">{t('account.admin')}</h2>
          <p className="text-sm text-text-secondary mb-3">
            {t('account.adminBody')}
          </p>
          <Link
            to="/admin/bi"
            className="inline-block px-4 py-2 rounded-xl bg-champagne text-white text-sm font-medium"
          >
            {t('account.adminCta')}
          </Link>
        </section>
      )}

      {msg && <div className="text-sm text-positive mb-4">{msg}</div>}
      {err && <div className="text-sm text-negative mb-4">{err}</div>}

      <div className="flex flex-wrap gap-3">
        <button onClick={doLogout} disabled={busy} className="px-4 py-2.5 rounded-xl bg-obsidian-lighter/50 border border-border-subtle text-text-primary hover:border-champagne/40 disabled:opacity-50">{t('account.logout')}</button>
        <button onClick={() => run(() => logoutAll(), t('account.logoutAllOk'))} disabled={busy} className="px-4 py-2.5 rounded-xl bg-obsidian-lighter/50 border border-border-subtle text-text-secondary hover:border-champagne/40 disabled:opacity-50" title={t('account.logoutAllTitle')}>{t('account.logoutAll')}</button>
        <button onClick={doDelete} disabled={busy} className="px-4 py-2.5 rounded-xl border border-negative/40 text-negative hover:bg-negative/10 disabled:opacity-50 ml-auto">{t('account.delete')}</button>
      </div>
    </div>
  );
}
