import { useEffect, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import useDocumentMeta from '../lib/useMeta';
import { useAuth } from '../context/authContext';
import { registerUser } from '../lib/api';
import { apiErrorMessage } from '../lib/apiErrorMessage';
import OAuthButtons from '../components/OAuthButtons';
import PasswordField from '../components/PasswordField';
import { track, events } from '../lib/track';
import { useT } from '../i18n';
import { safeReturnTo, authLink } from '../lib/authReturn';
import { cn } from '../lib/format';
import Button from '../components/Button';
import { usePrefersReducedMotion } from '../lib/chartHooks';
import '../styles/w5-pages.css';

export default function Register() {
  const t = useT();
  useDocumentMeta({ title: t('auth.register.metaTitle'), path: '/register', robots: 'noindex, nofollow' });
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const { setUser } = useAuth();
  const next = safeReturnTo(params.get('next'));
  const googleUnavailable = params.get('google_unavailable') === '1';
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [consent, setConsent] = useState(false);
  // Рассылка — только по явному согласию: заранее отмеченная галочка вызывает недоверие.
  const [newsletter, setNewsletter] = useState(false);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  const [welcome, setWelcome] = useState(false);
  const reduced = usePrefersReducedMotion();

  // После регистрации — короткая радость (галочка «рисуется»), затем автоматически дальше.
  useEffect(() => {
    if (!welcome) return undefined;
    const timer = setTimeout(() => navigate(next, { replace: true }), reduced ? 900 : 1800);
    return () => clearTimeout(timer);
  }, [welcome, reduced, navigate, next]);

  const useEmailRegistration = () => {
    const query = new URLSearchParams();
    const requestedNext = params.get('next');
    if (requestedNext) query.set('next', requestedNext);
    query.set('google_unavailable', '1');
    navigate(`/register?${query.toString()}#email`, { replace: true });
    const emailField = document.getElementById('email');
    emailField?.focus();
    emailField?.scrollIntoView?.({ behavior: 'smooth', block: 'center' });
  };

  const submit = async (e) => {
    e.preventDefault();
    setError(null);
    if (!consent) {
      setError(t('auth.register.consentRequired'));
      return;
    }
    setBusy(true);
    try {
      const user = await registerUser({ email, password, consent, newsletter });
      setUser(user);
      track(events.AUTH_SIGNUP, { method: 'email', newsletter: newsletter ? 1 : 0 });
      if (newsletter) track(events.NEWSLETTER_OPT_IN, { channel: 'email' });
      setWelcome(true);
    } catch (err) {
      setError(apiErrorMessage(err, t, 'auth.register.error'));
    } finally {
      setBusy(false);
    }
  };

  // Какое поле подсветить: по тексту ошибки (сообщения приходят уже переведёнными).
  const emailInvalid = [
    'auth.register.emailExists', 'auth.validation.email', 'auth.validation.emailTaken', 'auth.validation.emailRequired',
  ].some((key) => error === t(key));
  const passwordInvalid = ['auth.validation.passwordShort', 'auth.validation.passwordLong'].some((key) => error === t(key));
  const consentInvalid = error === t('auth.register.consentRequired');
  const fieldClass = (invalid) => cn(
    'fe-input w-full px-3.5 py-2.5 rounded-xl bg-obsidian-lighter/50 border text-text-primary focus:outline-none',
    invalid ? 'border-negative focus:border-negative' : 'border-border-subtle focus:border-champagne/50',
  );
  const describedBy = error ? 'register-error' : undefined;

  if (welcome) {
    return (
      <div className="fe-data-page max-w-md mx-auto px-4 pt-28 pb-24">
        <div className="fe-panel fe-auth-card p-5 sm:p-8" role="status">
          <div className="w5-success">
            <svg className="w5-success__svg" viewBox="0 0 64 64" aria-hidden="true" focusable="false">
              <circle className="w5-success__ring" cx="32" cy="32" r="28" />
              <path className="w5-success__tick" d="M19 33l9 9 17-19" />
            </svg>
            <h1 className="text-2xl font-display font-bold text-text-primary">{t('w5.auth.welcomeTitle')}</h1>
            <p className="text-text-secondary">{t('w5.auth.welcomeBody')}</p>
            <Button className="mt-2 w-full" onClick={() => navigate(next, { replace: true })}>
              {t('w5.auth.welcomeContinue')}
            </Button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="fe-data-page max-w-md mx-auto px-4 pt-28 pb-24">
      <div className="fe-panel fe-auth-card fe-reveal p-5 sm:p-8">
      <h1 className="text-2xl font-display font-bold text-text-primary mb-1 text-center">{t('auth.register.title')}</h1>
      <ul className="fe-w7p-benefits" aria-label={t('w7p.reg.benefitsAria')}>
        <li>{t('w7p.reg.b1')}</li>
        <li>{t('w7p.reg.b2')}</li>
        <li>{t('w7p.reg.b3')}</li>
      </ul>

      <OAuthButtons
        next={next}
        intent="login"
        dividerLabel={t('auth.oauth.divider')}
        showGoogleEmailFallback
        onGoogleEmailFallback={useEmailRegistration}
      />

      {googleUnavailable && (
        <div role="status" className="rounded-xl border border-champagne/30 bg-champagne/10 px-3.5 py-3 text-sm text-text-secondary mb-4">
          {t('auth.register.googleUnavailable')}
        </div>
      )}

      <form onSubmit={submit} className="space-y-4">
        <div>
          <label className="block text-sm text-text-secondary mb-1.5" htmlFor="email">{t('common.email')}</label>
          <input
            id="email" name="email" type="email" required value={email} onChange={(e) => setEmail(e.target.value)}
            autoComplete="email"
            inputMode="email"
            placeholder={t('w5.auth.emailPlaceholder')}
            aria-invalid={emailInvalid || undefined}
            aria-describedby={emailInvalid ? describedBy : undefined}
            className={fieldClass(emailInvalid)}
          />
        </div>
        <div>
          <PasswordField
            label={t('common.password')}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="new-password"
            minLength={8}
            placeholder={t('w5.auth.newPasswordPlaceholder')}
            invalid={passwordInvalid}
            describedBy={passwordInvalid ? describedBy : undefined}
            className={fieldClass(passwordInvalid)}
          />
          <p className="w5-field-hint">{t('auth.register.passwordHint')}</p>
        </div>
        <label className="w5-consent">
          <input
            type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)}
            aria-invalid={consentInvalid || undefined}
            aria-describedby={consentInvalid ? describedBy : undefined}
          />
          <span>
            {t('w7p.reg.legalBefore')}{' '}
            <Link to="/terms" className="fe-link">{t('w7p.reg.legalTerms')}</Link>{' '}
            {t('w7p.reg.legalMid')}{' '}
            <Link to="/privacy" className="fe-link">{t('w7p.reg.legalPrivacy')}</Link>
            {t('w7p.reg.legalAfter')}
          </span>
        </label>
        <label className="w5-consent">
          <input type="checkbox" checked={newsletter} onChange={(e) => setNewsletter(e.target.checked)} />
          <span>{t('auth.oauth.newsletter')}</span>
        </label>

        <div id="register-error" role="alert" className="w5-auth-error">{error}</div>
        <span role="status" className="sr-only">{busy ? t('auth.register.busy') : ''}</span>

        <Button type="submit" loading={busy} className="w-full font-semibold">
          {busy ? t('auth.register.busy') : t('auth.register.submitAlt')}
        </Button>
      </form>

      <p className="text-sm text-text-secondary mt-6 text-center">
        {t('auth.register.haveAccount')} <Link to={authLink('/login', next)} className="fe-link inline-flex items-center pointer-coarse:min-h-11">{t('common.login')}</Link>
      </p>
      </div>
    </div>
  );
}
