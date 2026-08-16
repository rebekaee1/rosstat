import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import useDocumentMeta from '../lib/useMeta';
import { useAuth } from '../context/authContext';
import { registerUser } from '../lib/api';
import { apiErrorMessage } from '../lib/apiErrorMessage';
import OAuthButtons from '../components/OAuthButtons';
import { track, events } from '../lib/track';
import { useT } from '../i18n';

export default function Register() {
  const t = useT();
  useDocumentMeta({ title: t('auth.register.metaTitle'), path: '/register', robots: 'noindex, nofollow' });
  const navigate = useNavigate();
  const { setUser } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [consent, setConsent] = useState(false);
  const [newsletter, setNewsletter] = useState(true);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

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
      navigate('/account');
    } catch (err) {
      setError(apiErrorMessage(err, t, 'auth.register.error'));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="max-w-md mx-auto px-4 pt-28 pb-24">
      <div className="rounded-2xl border border-border-subtle bg-surface p-6 sm:p-8 shadow-md ring-1 ring-black/[0.04]">
      <h1 className="text-2xl font-display font-bold text-text-primary mb-1 text-center">{t('auth.register.title')}</h1>
      <p className="text-sm text-text-secondary mb-6 text-center">
        {t('auth.register.subtitle')}
      </p>

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
            id="password" type="password" required minLength={8} value={password} onChange={(e) => setPassword(e.target.value)}
            autoComplete="new-password"
            className="w-full px-3.5 py-2.5 rounded-xl bg-obsidian-lighter/50 border border-border-subtle text-text-primary focus:outline-none focus:border-champagne/50"
          />
          <p className="text-xs text-text-tertiary mt-1">{t('auth.register.passwordHint')}</p>
        </div>
        <label className="flex items-start gap-2.5 text-sm text-text-secondary cursor-pointer">
          <input type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)} className="mt-0.5 accent-[#B8942F]" />
          <span>
            {t('auth.oauth.policyBefore')}{' '}
            <Link to="/terms" className="text-champagne hover:underline">{t('auth.oauth.terms')}</Link>{' '}
            {t('auth.oauth.policyMid')}{' '}
            <Link to="/privacy" className="text-champagne hover:underline">{t('auth.oauth.privacy')}</Link>
            {t('auth.oauth.policyAfter')}
          </span>
        </label>
        <label className="flex items-start gap-2.5 text-sm text-text-secondary cursor-pointer">
          <input type="checkbox" checked={newsletter} onChange={(e) => setNewsletter(e.target.checked)} className="mt-0.5 accent-[#B8942F]" />
          <span>{t('auth.oauth.newsletter')}</span>
        </label>

        {error && <div className="text-sm text-negative">{error}</div>}

        <button
          type="submit" disabled={busy}
          className="w-full py-2.5 rounded-xl bg-champagne/15 text-champagne font-medium hover:bg-champagne/25 transition-colors disabled:opacity-50"
        >
          {busy ? t('auth.register.busy') : t('auth.register.submitAlt')}
        </button>
      </form>

      <p className="text-sm text-text-secondary mt-6 text-center">
        {t('auth.register.haveAccount')} <Link to="/login" className="text-champagne hover:underline">{t('common.login')}</Link>
      </p>
      </div>
    </div>
  );
}
