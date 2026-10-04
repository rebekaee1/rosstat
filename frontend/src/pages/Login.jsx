import { useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import useDocumentMeta from '../lib/useMeta';
import { useAuth } from '../context/authContext';
import { loginUser } from '../lib/api';
import { apiErrorMessage } from '../lib/apiErrorMessage';
import OAuthButtons from '../components/OAuthButtons';
import PasswordField from '../components/PasswordField';
import { track, events } from '../lib/track';
import { useT } from '../i18n';
import { safeReturnTo, authLink } from '../lib/authReturn';
import { cn } from '../lib/format';
import Button from '../components/Button';
import '../styles/w5-pages.css';

export default function Login() {
  const t = useT();
  useDocumentMeta({ title: t('auth.login.metaTitle'), path: '/login', robots: 'noindex, nofollow' });
  const navigate = useNavigate();
  const { setUser } = useAuth();
  const [params] = useSearchParams();
  const next = safeReturnTo(params.get('next'));
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [busy, setBusy] = useState(false);
  const oauthErrors = {
    oauth_failed: t('auth.login.oauthFailed'),
    oauth_state: t('auth.login.oauthState'),
    oauth_denied: t('auth.login.oauthDenied'),
    oauth_disabled: t('auth.login.oauthDisabled'),
    consent_required: t('auth.register.consentRequired'),
  };
  const oauthError = oauthErrors[params.get('error')] || (params.get('error') ? t('auth.login.errorGeneric') : null);
  const [error, setError] = useState(oauthError);

  const submit = async (e) => {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const user = await loginUser({ email, password });
      setUser(user);
      track(events.AUTH_LOGIN, { method: 'email' });
      navigate(next, { replace: true });
    } catch (err) {
      setError(apiErrorMessage(err, t, 'auth.login.errorCredentials'));
    } finally {
      setBusy(false);
    }
  };

  const credentialsInvalid = error === t('auth.login.errorCredentials');
  const fieldClass = (invalid) => cn(
    'fe-input w-full px-3.5 py-2.5 rounded-xl bg-obsidian-lighter/50 border text-text-primary focus:outline-none',
    invalid ? 'border-negative focus:border-negative' : 'border-border-subtle focus:border-champagne/50',
  );

  return (
    <div className="fe-data-page max-w-md mx-auto px-4 pt-28 pb-24">
      <div className="fe-panel fe-auth-card fe-reveal p-5 sm:p-8">
      <h1 className="text-2xl font-display font-bold text-text-primary mb-1 text-center">{t('auth.login.title')}</h1>
      <p className="text-sm text-text-secondary mb-6 text-center">{t('auth.login.subtitle')}</p>

      <OAuthButtons next={next} intent="login" dividerLabel={t('auth.oauth.divider')} />

      <form onSubmit={submit} className="space-y-4">
        <div>
          <label className="block text-sm text-text-secondary mb-1.5" htmlFor="email">{t('common.email')}</label>
          <input
            id="email" name="email" type="email" required value={email} onChange={(e) => setEmail(e.target.value)}
            autoComplete="email"
            inputMode="email"
            placeholder={t('w5.auth.emailPlaceholder')}
            aria-invalid={credentialsInvalid || undefined}
            aria-describedby={error ? 'login-error' : undefined}
            className={fieldClass(credentialsInvalid)}
          />
        </div>
        <PasswordField
          label={t('common.password')}
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          autoComplete="current-password"
          placeholder={t('w5.auth.passwordPlaceholder')}
          invalid={credentialsInvalid}
          describedBy={error ? 'login-error' : undefined}
          className={fieldClass(credentialsInvalid)}
        />

        <div id="login-error" role="alert" className="w5-auth-error">{error}</div>
        <span role="status" className="sr-only">{busy ? t('auth.login.busy') : ''}</span>

        <Button type="submit" loading={busy} className="w-full font-semibold">
          {busy ? t('auth.login.busy') : t('auth.login.submit')}
        </Button>
      </form>

      <div className="w5-auth-alt">
        <p className="w5-auth-note">{t('w5.auth.noAccount')}</p>
        <Button as={Link} to={authLink('/register', next)} variant="secondary" className="w-full">
          {t('auth.login.createAccount')}
        </Button>
        <p className="w5-auth-note">{t('w5.auth.forgotSoon')}</p>
      </div>
      </div>
    </div>
  );
}
