import { useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import useDocumentMeta from '../lib/useMeta';
import { useAuth } from '../context/authContext';
import { loginUser } from '../lib/api';
import { apiErrorMessage } from '../lib/apiErrorMessage';
import OAuthButtons from '../components/OAuthButtons';
import { track, events } from '../lib/track';
import { useT } from '../i18n';

export default function Login() {
  const t = useT();
  useDocumentMeta({ title: t('auth.login.metaTitle'), path: '/login', robots: 'noindex, nofollow' });
  const navigate = useNavigate();
  const { setUser } = useAuth();
  const [params] = useSearchParams();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [busy, setBusy] = useState(false);
  const oauthErrors = {
    oauth_failed: t('auth.login.oauthFailed'),
    oauth_state: t('auth.login.oauthState'),
    oauth_denied: t('auth.login.oauthDenied'),
    oauth_disabled: t('auth.login.oauthDisabled'),
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
      navigate('/account');
    } catch (err) {
      setError(apiErrorMessage(err, t, 'auth.login.errorCredentials'));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="max-w-md mx-auto px-4 pt-28 pb-24">
      <div className="rounded-2xl border border-border-subtle bg-surface p-6 sm:p-8 shadow-md ring-1 ring-black/[0.04]">
      <h1 className="text-2xl font-display font-bold text-text-primary mb-1 text-center">{t('auth.login.title')}</h1>
      <p className="text-sm text-text-secondary mb-6 text-center">{t('auth.login.subtitle')}</p>

      <OAuthButtons intent="login" dividerLabel={t('auth.oauth.divider')} />

      <form onSubmit={submit} className="space-y-4">
        <div>
          <label className="block text-sm text-text-secondary mb-1.5" htmlFor="email">{t('common.email')}</label>
          <input
            id="email" type="email" required value={email} onChange={(e) => setEmail(e.target.value)}
            autoComplete="email"
            className="w-full px-3.5 py-2.5 rounded-xl bg-obsidian-lighter/50 border border-border-subtle text-text-primary focus:outline-none focus:border-champagne/50"
          />
        </div>
        <div>
          <label className="block text-sm text-text-secondary mb-1.5" htmlFor="password">{t('common.password')}</label>
          <input
            id="password" type="password" required value={password} onChange={(e) => setPassword(e.target.value)}
            autoComplete="current-password"
            className="w-full px-3.5 py-2.5 rounded-xl bg-obsidian-lighter/50 border border-border-subtle text-text-primary focus:outline-none focus:border-champagne/50"
          />
        </div>

        {error && <div className="text-sm text-negative">{error}</div>}

        <button
          type="submit" disabled={busy}
          className="w-full py-2.5 rounded-xl bg-champagne/15 text-champagne font-medium hover:bg-champagne/25 transition-colors disabled:opacity-50"
        >
          {busy ? t('auth.login.busy') : t('auth.login.submit')}
        </button>
      </form>

      <div className="flex items-center justify-between mt-6 text-sm">
        <Link to="/register" className="text-champagne hover:underline">{t('auth.login.createAccount')}</Link>
        <span className="text-text-tertiary cursor-not-allowed" title={t('auth.login.forgotSoon')}>{t('auth.login.forgot')}</span>
      </div>
      </div>
    </div>
  );
}
