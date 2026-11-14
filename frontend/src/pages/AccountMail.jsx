/**
 * Страницы ссылок из писем (ADR-0032): «Забыли пароль?», новый пароль, подтверждение адреса,
 * отписка от рассылки. Все под `/account/…` (nginx отдаёт оболочку и noindex, как у входа).
 * Вид — тот же, что у входа и регистрации: одна плита `fe-panel fe-auth-card` на сцене сайта.
 * Ссылка из письма открывается и без входа на сайт: полномочие — подписанный токен `t`.
 */
import { useEffect, useRef, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import useDocumentMeta from '../lib/useMeta';
import { useT } from '../i18n';
import {
  requestPasswordReset, resetPassword, resubscribeByLink,
  unsubscribeByLink, verifyEmail,
} from '../lib/api';
import { apiErrorMessage } from '../lib/apiErrorMessage';
import PasswordField from '../components/PasswordField';
import Button from '../components/Button';
import { cn } from '../lib/format';
import '../styles/w5-pages.css';
import '../styles/k8-tools.css';

const inputClass = (invalid) => cn(
  'fe-input w-full px-3.5 py-2.5 rounded-xl text-text-primary focus:outline-none',
  invalid && 'is-invalid',
);

function Card({ title, subtitle, children }) {
  return (
    <div className="fe-data-page max-w-md mx-auto px-4 pt-28 pb-24">
      <div className="fe-panel fe-auth-card fe-reveal p-5 sm:p-8">
        <h1 className="text-2xl font-display font-bold text-text-primary mb-1 text-center">{title}</h1>
        {subtitle && <p className="text-sm text-text-secondary mb-6 text-center">{subtitle}</p>}
        {children}
      </div>
    </div>
  );
}

function Note({ children, testId }) {
  return (
    <div role="status" data-testid={testId}
      className="rounded-xl bg-champagne/10 px-3.5 py-3 text-sm text-text-secondary mb-4 fe-shadow-2">
      {children}
    </div>
  );
}

/**
 * Токен из ссылки письма читается один раз и сразу убирается из адресной строки:
 * так он не попадает в историю браузера, события аналитики (полный URL) и Referer.
 */
function useLinkToken() {
  const [params] = useSearchParams();
  const [token] = useState(() => params.get('t') || '');
  useEffect(() => {
    if (typeof window === 'undefined' || !window.location.search.includes('t=')) return;
    window.history.replaceState(window.history.state, '', window.location.pathname);
  }, []);
  return token;
}

export function ForgotPassword() {
  const t = useT();
  useDocumentMeta({ title: t('mail.forgot.title'), path: '/account/forgot-password', robots: 'noindex, nofollow' });
  const [email, setEmail] = useState('');
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState(null);

  const submit = async (e) => {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await requestPasswordReset(email.trim());
      setDone(true);
    } catch (err) {
      setError(apiErrorMessage(err, t));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card title={t('mail.forgot.title')} subtitle={done ? null : t('mail.forgot.subtitle')}>
      {done ? (
        <>
          <Note testId="forgot-sent">{t('mail.forgot.sent')}</Note>
          <Button as={Link} to="/login" variant="secondary" className="w-full">{t('mail.backToLogin')}</Button>
        </>
      ) : (
        <form onSubmit={submit} className="space-y-4" data-track="forgot-password">
          <div>
            <label className="block text-sm text-text-secondary mb-1.5" htmlFor="forgot-email">{t('common.email')}</label>
            <input id="forgot-email" name="email" type="email" required autoComplete="email" inputMode="email"
              value={email} onChange={(e) => setEmail(e.target.value)}
              placeholder={t('w5.auth.emailPlaceholder')} className={inputClass(Boolean(error))}
              aria-describedby={error ? 'forgot-error' : undefined} />
          </div>
          <div id="forgot-error" role="alert" className="w5-auth-error">{error}</div>
          <Button type="submit" loading={busy} className="w-full font-semibold">{t('mail.forgot.submit')}</Button>
          <div className="w5-auth-alt">
            <Button as={Link} to="/login" variant="secondary" className="w-full">{t('mail.backToLogin')}</Button>
          </div>
        </form>
      )}
    </Card>
  );
}

export function ResetPassword() {
  const t = useT();
  useDocumentMeta({ title: t('mail.reset.title'), path: '/account/reset-password', robots: 'noindex, nofollow' });
  const token = useLinkToken();
  const navigate = useNavigate();
  const [password, setPassword] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(token ? null : t('mail.linkBroken'));
  const [done, setDone] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setError(null);
    if (password.length < 8) {
      setError(t('auth.validation.passwordShort'));
      return;
    }
    setBusy(true);
    try {
      await resetPassword(token, password);
      setDone(true);
    } catch (err) {
      setError(apiErrorMessage(err, t));
    } finally {
      setBusy(false);
    }
  };

  if (done) {
    return (
      <Card title={t('mail.reset.doneTitle')}>
        <Note testId="reset-done">{t('mail.reset.done')}</Note>
        <Button className="w-full font-semibold" onClick={() => navigate('/login', { replace: true })}>
          {t('auth.login.submit')}
        </Button>
      </Card>
    );
  }
  return (
    <Card title={t('mail.reset.title')} subtitle={t('mail.reset.subtitle')}>
      <form onSubmit={submit} className="space-y-4" data-track="reset-password">
        <PasswordField label={t('mail.reset.newPassword')} value={password}
          onChange={(e) => setPassword(e.target.value)} autoComplete="new-password"
          placeholder={t('w5.auth.passwordPlaceholder')} invalid={Boolean(error)}
          describedBy={error ? 'reset-error' : undefined} className={inputClass(Boolean(error))} />
        <div id="reset-error" role="alert" className="w5-auth-error">{error}</div>
        <Button type="submit" loading={busy} disabled={!token} className="w-full font-semibold">
          {t('mail.reset.submit')}
        </Button>
        <div className="w5-auth-alt">
          <Button as={Link} to="/account/forgot-password" variant="secondary" className="w-full">
            {t('mail.reset.again')}
          </Button>
        </div>
      </form>
    </Card>
  );
}

export function VerifyEmail() {
  const t = useT();
  useDocumentMeta({ title: t('mail.verify.title'), path: '/account/verify-email', robots: 'noindex, nofollow' });
  const token = useLinkToken();
  const [state, setState] = useState(token ? 'pending' : 'error');
  const [error, setError] = useState(token ? null : t('mail.linkBroken'));
  // Запрос при открытии ровно один раз (StrictMode вызывает эффект дважды).
  const ran = useRef(false);
  useEffect(() => {
    if (ran.current || !token) return;
    ran.current = true;
    verifyEmail(token)
      .then(() => setState('done'))
      .catch((err) => { setError(apiErrorMessage(err, t)); setState('error'); });
  }, [token, t]);

  return (
    <Card title={t('mail.verify.title')}>
      {state === 'pending' && <Note testId="verify-pending">{t('mail.verify.pending')}</Note>}
      {state === 'done' && <Note testId="verify-done">{t('mail.verify.done')}</Note>}
      {state === 'error' && <div role="alert" className="w5-auth-error mb-4" data-testid="verify-error">{error}</div>}
      <Button as={Link} to="/account" variant="secondary" className="w-full">{t('mail.toAccount')}</Button>
    </Card>
  );
}

export function Unsubscribe() {
  const t = useT();
  useDocumentMeta({ title: t('mail.unsub.title'), path: '/account/unsubscribe', robots: 'noindex, nofollow' });
  const token = useLinkToken();
  const [info, setInfo] = useState(null); // { subscribed, email }
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(token ? null : t('mail.linkBroken'));
  // Ссылка «Отписаться» в письме отписывает сразу, без второго нажатия (так ждут люди и
  // почтовые сервисы). Сканеры ссылок JavaScript не выполняют, поэтому сами не отпишут.
  const ran = useRef(false);
  useEffect(() => {
    if (ran.current || !token) return;
    ran.current = true;
    unsubscribeByLink(token).then(setInfo).catch((err) => setError(apiErrorMessage(err, t)));
  }, [token, t]);

  const toggle = async () => {
    setBusy(true);
    setError(null);
    try {
      setInfo(info?.subscribed ? await unsubscribeByLink(token) : await resubscribeByLink(token));
    } catch (err) {
      setError(apiErrorMessage(err, t));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card title={t('mail.unsub.title')}>
      {!info && !error && <Note testId="unsub-pending">{t('mail.unsub.pending')}</Note>}
      {info && (
        <Note testId={info.subscribed ? 'unsub-subscribed' : 'unsub-done'}>
          {info.subscribed ? t('mail.unsub.resubscribed') : t(info.list === 'watch' ? 'mail.unsub.doneWatch' : 'mail.unsub.done')}
          {info.email ? <span className="block mt-1 text-text-tertiary">{info.email}</span> : null}
        </Note>
      )}
      <div role="alert" className="w5-auth-error mb-4">{error}</div>
      {info && (
        <Button onClick={toggle} loading={busy} variant="secondary" className="w-full mb-3"
          data-testid="unsub-toggle">
          {info.subscribed ? t('mail.unsub.again') : t('mail.unsub.resubscribe')}
        </Button>
      )}
      <Button as={Link} to="/" variant="secondary" className="w-full">{t('mail.toSite')}</Button>
    </Card>
  );
}

export default ForgotPassword;
