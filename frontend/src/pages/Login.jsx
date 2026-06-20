import { useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import useDocumentMeta from '../lib/useMeta';
import { useAuth } from '../context/authContext';
import { loginUser } from '../lib/api';
import OAuthButtons from '../components/OAuthButtons';
import { track, events } from '../lib/track';

const OAUTH_ERRORS = {
  oauth_failed: 'Не удалось войти через провайдера. Попробуйте ещё раз.',
  oauth_state: 'Сессия входа истекла. Попробуйте ещё раз.',
  oauth_denied: 'Доступ не предоставлен.',
  oauth_disabled: 'Этот способ входа сейчас недоступен.',
};

export default function Login() {
  useDocumentMeta({ title: 'Вход — Forecast Economy', path: '/login', robots: 'noindex, nofollow' });
  const navigate = useNavigate();
  const { setUser } = useAuth();
  const [params] = useSearchParams();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [busy, setBusy] = useState(false);
  const oauthError = OAUTH_ERRORS[params.get('error')] || (params.get('error') ? 'Ошибка входа.' : null);
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
      const status = err?.response?.status;
      if (status === 423) setError('Слишком много попыток. Повторите позже.');
      else setError(err?.response?.data?.detail || 'Неверный email или пароль');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="max-w-md mx-auto px-4 pt-28 pb-24">
      <div className="rounded-2xl border border-border-subtle bg-surface p-6 sm:p-8 shadow-md ring-1 ring-black/[0.04]">
      <h1 className="text-2xl font-display font-bold text-text-primary mb-1 text-center">Вход</h1>
      <p className="text-sm text-text-secondary mb-6 text-center">Войдите, чтобы скачивать данные без ограничений.</p>

      <OAuthButtons intent="login" dividerLabel="или по email" />

      <form onSubmit={submit} className="space-y-4">
        <div>
          <label className="block text-sm text-text-secondary mb-1.5" htmlFor="email">Email</label>
          <input
            id="email" type="email" required value={email} onChange={(e) => setEmail(e.target.value)}
            autoComplete="email"
            className="w-full px-3.5 py-2.5 rounded-xl bg-obsidian-lighter/50 border border-border-subtle text-text-primary focus:outline-none focus:border-champagne/50"
          />
        </div>
        <div>
          <label className="block text-sm text-text-secondary mb-1.5" htmlFor="password">Пароль</label>
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
          {busy ? 'Входим…' : 'Войти'}
        </button>
      </form>

      <div className="flex items-center justify-between mt-6 text-sm">
        <Link to="/register" className="text-champagne hover:underline">Создать аккаунт</Link>
        <span className="text-text-tertiary cursor-not-allowed" title="Будет доступно позже">Забыли пароль?</span>
      </div>
      </div>
    </div>
  );
}
