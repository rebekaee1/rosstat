import { useEffect, useRef, useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { MessageSquare, CheckCircle2 } from 'lucide-react';
import { useAuth } from '../../context/authContext';
import { track, events } from '../../lib/track';
import {
  logoutUser, logoutAll, deleteAccount, submitFeedback, updateNewsletter, updateProfile,
} from '../../lib/api';
import { apiErrorMessage } from '../../lib/apiErrorMessage';
import { useT } from '../../i18n';
import { cn } from '../../lib/format';
import Button from '../Button';

/**
 * Профиль, обратная связь, рассылка, служебное и блок «Аккаунт» (выход и удаление).
 * Раньше это была вся страница `/account`; логика прежняя, изменилось оформление:
 * рассылка переключателем, подсказка у неактивной «Отправить», блок «Аккаунт» отдельной плитой,
 * удаление требует ввести слово.
 */
export default function ProfilePanel() {
  const t = useT();
  const navigate = useNavigate();
  const location = useLocation();
  const { user, setUser, refetch } = useAuth();
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
  const [delOpen, setDelOpen] = useState(false);
  const [delWord, setDelWord] = useState('');
  const feedbackRef = useRef(null);

  // Переход по «Оставить отзыв» (#feedback): плавно проматываем к форме.
  useEffect(() => {
    if (location.hash === '#feedback' && feedbackRef.current) {
      feedbackRef.current.scrollIntoView?.({ behavior: 'smooth', block: 'center' });
    }
  }, [location.hash]);

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

  const deleteWord = t('c11b.account.deleteWord');
  const deleteReady = delWord.trim().toLowerCase() === deleteWord.toLowerCase();
  const doDelete = async () => {
    if (!deleteReady) return;
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
  const fbShort = fbText.trim().length < 5;

  return (
    <>
      <section className="fe-panel fe-reveal rounded-3xl p-5 mb-5 shadow-sm">
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
                      'min-w-0 flex-1 max-w-[16rem] px-2.5 py-1 rounded-lg text-text-primary focus:outline-none pointer-coarse:min-h-11 fe-k8-well',
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
        className="fe-panel fe-reveal rounded-3xl p-5 mb-5 shadow-sm scroll-mt-28"
      >
        <h2 className="flex items-center gap-2 text-base font-semibold text-text-primary mb-2">
          <MessageSquare className="w-4 h-4 text-champagne" />
          {t('account.feedback')}
        </h2>
        {fbSent ? (
          <div role="status" className="flex items-start gap-2.5 rounded-xl bg-positive/10 px-4 py-3 text-sm text-text-primary fe-shadow-2">
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
              aria-describedby={fbErr ? 'account-feedback-error' : 'account-feedback-hint'}
              className={cn(
                'w-full px-3.5 py-2.5 rounded-xl text-text-primary focus:outline-none resize-y fe-k8-well',
                fbErr && 'is-invalid',
              )}
            />
            <div className="flex items-center justify-between gap-3 mt-2">
              <span id="account-feedback-hint" className="text-xs text-text-tertiary">
                {fbShort ? t('c11b.account.feedbackHint') : t('account.feedbackReplyNote')}
              </span>
              <Button
                onClick={sendFeedback}
                disabled={fbShort}
                loading={fbBusy}
                className="shrink-0"
                title={fbShort ? t('c11b.account.feedbackHint') : undefined}
              >
                {fbBusy ? t('account.feedbackSending') : t('account.feedbackSend')}
              </Button>
            </div>
            <div id="account-feedback-error" role="alert" className="text-sm text-negative mt-2 empty:hidden">{fbErr}</div>
          </>
        )}
      </section>

      <section className="fe-glass-lite fe-reveal rounded-3xl p-5 mb-5">
        <div className="c11b-switch-row">
          <div className="min-w-0">
            <h2 id="account-newsletter-label" className="text-base font-semibold text-text-primary">{t('c11b.account.newsletter')}</h2>
            <p className="text-sm text-text-secondary mt-1">
              {user.newsletter ? t('account.newsletterOn') : t('account.newsletterOff')}
            </p>
          </div>
          <button
            type="button"
            role="switch"
            aria-checked={Boolean(user.newsletter)}
            aria-labelledby="account-newsletter-label"
            aria-busy={nlBusy || undefined}
            disabled={nlBusy}
            onClick={toggleNewsletter}
            className="c11b-switch"
          >
            <span className="c11b-switch__knob" aria-hidden="true" />
          </button>
        </div>
      </section>

      {user.is_admin && (
        <section className="fe-glass-lite rounded-3xl p-5 mb-5">
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
          <div className="flex items-start gap-2 rounded-xl bg-positive/10 px-3.5 py-2.5 text-sm text-text-primary fe-shadow-2">
            <CheckCircle2 className="w-4 h-4 text-positive shrink-0 mt-0.5" aria-hidden="true" />
            {msg}
          </div>
        )}
      </div>
      <div role="alert" className="empty:hidden mb-4">
        {err && <div className="rounded-xl px-3.5 py-2.5 text-sm text-negative fe-glass-2">{err}</div>}
      </div>

      <section className="fe-glass-lite rounded-3xl p-5 mb-5" aria-labelledby="account-actions-title">
        <h2 id="account-actions-title" className="text-base font-semibold text-text-primary mb-3">{t('c11b.account.title')}</h2>
        <div className="c11b-account-actions">
          <Button variant="secondary" onClick={doLogout} disabled={busy} loading={busyKey === 'logout'}>{t('account.logout')}</Button>
          <Button
            variant="secondary"
            onClick={() => run(() => logoutAll(), t('account.logoutAllOk'), true, 'logoutAll')}
            disabled={busy}
            loading={busyKey === 'logoutAll'}
            title={t('account.logoutAllTitle')}
          >
            {t('account.logoutAll')}
          </Button>
        </div>
        <p className="text-xs text-text-tertiary mt-2">{t('account.logoutAllTitle')}</p>

        <div className="c11b-danger">
          {delOpen ? (
            <>
              <p className="text-sm text-text-secondary">{t('account.deleteConfirm')}</p>
              <label className="c11b-field__label" htmlFor="account-delete-word">
                {t('c11b.account.deleteType', { word: deleteWord })}
              </label>
              <div className="c11b-danger__row">
                <input
                  id="account-delete-word"
                  value={delWord}
                  onChange={(e) => setDelWord(e.target.value)}
                  autoComplete="off"
                  autoCapitalize="off"
                  spellCheck={false}
                  className="fe-k8-well c11b-row__input"
                  placeholder={deleteWord}
                />
                <Button
                  variant="secondary"
                  onClick={doDelete}
                  disabled={busy || !deleteReady}
                  loading={busyKey === 'delete'}
                  className="text-negative! hover:bg-negative/10!"
                >
                  {t('c11b.account.deleteCta')}
                </Button>
                <Button variant="ghost" onClick={() => { setDelOpen(false); setDelWord(''); }} disabled={busy}>
                  {t('common.cancel')}
                </Button>
              </div>
            </>
          ) : (
            <Button variant="ghost" onClick={() => setDelOpen(true)} disabled={busy} className="text-negative! hover:bg-negative/10!">
              {t('account.delete')}
            </Button>
          )}
        </div>
      </section>
    </>
  );
}
