import { useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import useDocumentMeta from '../lib/useMeta';
import { useAuth } from '../context/authContext';
import { registerUser } from '../lib/api';
import { apiErrorMessage } from '../lib/apiErrorMessage';
import OAuthButtons from '../components/OAuthButtons';
import { track, events } from '../lib/track';
import { useT } from '../i18n';
import { safeReturnTo, authLink } from '../lib/authReturn';
import { cn } from '../lib/format';
import Button from '../components/Button';

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
  const [newsletter, setNewsletter] = useState(true);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

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
      navigate(next, { replace: true });
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

  return (
    <div className="fe-data-page max-w-md mx-auto px-4 pt-28 pb-24">
      <div className="fe-panel fe-auth-card p-5 sm:p-8">
      <h1 className="text-2xl font-display font-bold text-text-primary mb-1 text-center">{t('auth.register.title')}</h1>
      <p className="text-sm text-text-secondary mb-6 text-center">
        {t('auth.register.subtitle')}
      </p>

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
            id="email" type="email" required value={email} onChange={(e) => setEmail(e.target.value)}
            autoComplete="email"
            aria-invalid={emailInvalid || undefined}
            aria-describedby={emailInvalid ? describedBy : undefined}
            className={fieldClass(emailInvalid)}
          />
        </div>
        <div>
          <label className="block text-sm text-text-secondary mb-1.5" htmlFor="password">{t('common.password')}</label>
          <input
            id="password" type="password" required minLength={8} value={password} onChange={(e) => setPassword(e.target.value)}
            autoComplete="new-password"
            aria-invalid={passwordInvalid || undefined}
            aria-describedby={passwordInvalid ? describedBy : undefined}
            className={fieldClass(passwordInvalid)}
          />
          <p className="text-xs text-text-tertiary mt-1">{t('auth.register.passwordHint')}</p>
        </div>
        <label className="flex items-start gap-2.5 text-sm text-text-secondary cursor-pointer">
          <input
            type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)}
            aria-invalid={consentInvalid || undefined}
            aria-describedby={consentInvalid ? describedBy : undefined}
            className={cn('mt-0.5 accent-champagne', consentInvalid && 'outline-2 outline-offset-2 outline-negative')}
          />
          <span>
            {t('auth.oauth.policyBefore')}{' '}
            <Link to="/terms" className="fe-link">{t('auth.oauth.terms')}</Link>{' '}
            {t('auth.oauth.policyMid')}{' '}
            <Link to="/privacy" className="fe-link">{t('auth.oauth.privacy')}</Link>
            {t('auth.oauth.policyAfter')}
          </span>
        </label>
        <label className="flex items-start gap-2.5 text-sm text-text-secondary cursor-pointer">
          <input type="checkbox" checked={newsletter} onChange={(e) => setNewsletter(e.target.checked)} className="mt-0.5 accent-champagne" />
          <span>{t('auth.oauth.newsletter')}</span>
        </label>

        <div id="register-error" role="alert" className="text-sm text-negative empty:hidden">{error}</div>
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
