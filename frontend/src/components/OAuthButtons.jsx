import { useEffect, useState } from 'react';
import { createPortal } from 'react-dom';
import { oauthStartUrl, fetchOAuthProviders } from '../lib/api';
import { track, events } from '../lib/track';
import { cn } from '../lib/format';
import { FOCUS_RING } from '../lib/uiTokens';
import { useLocale } from '../i18n';

const PROVIDER_UI = {
  google: {
    labelKey: 'auth.oauth.google',
    className: 'bg-white hover:bg-[#f5f5f5] text-[#1f1f1f] border border-[#dadce0]',
    logo: (
      <svg viewBox="0 0 24 24" className="w-5 h-5" aria-hidden="true">
        <path fill="#4285F4" d="M21.35 12.21c0-.71-.06-1.42-.18-2.11H12v3.99h5.25a4.5 4.5 0 0 1-1.95 2.95v2.45h3.16c1.85-1.71 2.89-4.23 2.89-7.28Z" />
        <path fill="#34A853" d="M12 21.7c2.64 0 4.86-.87 6.48-2.36l-3.16-2.45c-.87.58-1.99.93-3.32.93-2.55 0-4.71-1.72-5.48-4.03H3.26v2.52A9.8 9.8 0 0 0 12 21.7Z" />
        <path fill="#FBBC05" d="M6.52 13.79A5.9 5.9 0 0 1 6.2 12c0-.62.11-1.23.32-1.79V7.69H3.26a9.8 9.8 0 0 0 0 8.62l3.26-2.52Z" />
        <path fill="#EA4335" d="M12 6.18c1.4 0 2.66.48 3.65 1.43l2.73-2.73A9.3 9.3 0 0 0 12 2.3a9.8 9.8 0 0 0-8.74 5.39l3.26 2.52C7.29 7.9 9.45 6.18 12 6.18Z" />
      </svg>
    ),
  },
  yandex: {
    labelKey: 'auth.oauth.yandex',
    className: 'bg-[#FC3F1D] hover:bg-[#e5380f] text-white',
    logo: (
      <span className="flex items-center justify-center w-5 h-5 rounded-full bg-white text-[#FC3F1D] text-[13px] font-bold leading-none">
        Я
      </span>
    ),
  },
  vk: {
    labelKey: 'auth.oauth.vk',
    className: 'bg-[#0077FF] hover:bg-[#0a6ae0] text-white',
    logo: (
      <svg viewBox="0 0 24 24" className="w-5 h-5 fill-white" aria-hidden="true">
        <path d="M12.8 17.2c-5.5 0-8.9-3.8-9-10.1h2.8c.1 4.6 2.2 6.6 3.8 7V7.1h2.6v3.9c1.6-.2 3.3-2 3.9-3.9h2.6c-.45 2.35-2.2 4.1-3.45 4.85 1.25.6 3.25 2.15 4.05 5.25h-2.9c-.6-1.95-2.15-3.45-4.2-3.7v3.7h-1z" />
      </svg>
    ),
  },
};

const PROVIDER_NAME_KEY = {
  google: 'auth.oauth.provider.google',
  yandex: 'auth.oauth.provider.yandex',
  vk: 'auth.oauth.provider.vk',
};

export default function OAuthButtons({
  intent = 'login', next = '/account', dividerLabel = null,
  showGoogleEmailFallback = false, onGoogleEmailFallback,
}) {
  const { locale, t } = useLocale();
  const [providers, setProviders] = useState(null); // null = ещё грузим
  // Согласие перед редиректом на провайдера. Рассылку можно отключить отдельно.
  const [pending, setPending] = useState(null); // id провайдера, ждущего согласия
  const [policy, setPolicy] = useState(false);
  const [newsletter, setNewsletter] = useState(false);

  useEffect(() => {
    let alive = true;
    fetchOAuthProviders()
      .then((list) => { if (alive) setProviders(list); })
      .catch(() => { if (alive) setProviders([]); });
    return () => { alive = false; };
  }, []);

  useEffect(() => {
    if (!pending) return undefined;
    const onKey = (e) => { if (e.key === 'Escape') setPending(null); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [pending]);

  if (providers === null && !showGoogleEmailFallback) {
    return <div className="space-y-2.5" aria-hidden>
      <div className="h-11 rounded-xl bg-obsidian-lighter/40 animate-pulse" />
      <div className="h-11 rounded-xl bg-obsidian-lighter/40 animate-pulse" />
    </div>;
  }
  const order = locale === 'en' ? ['google', 'yandex', 'vk'] : ['yandex', 'vk', 'google'];
  const available = providers || [];
  // Register can keep the branded Google entry visible while intentionally
  // routing every click to email until Google signup is explicitly enabled.
  const showGoogleFallback = showGoogleEmailFallback;
  const ordered = order.filter((id) => available.includes(id) || (id === 'google' && showGoogleFallback));
  if (ordered.length === 0) return null;

  const openConsent = (id) => {
    setPolicy(false);
    setNewsletter(id === 'google' && intent === 'login');
    setPending(id);
  };

  const proceed = () => {
    if (!policy || !pending) return;
    track(events.OAUTH_START, { provider: pending, intent });
    if (newsletter) track(events.NEWSLETTER_OPT_IN, { channel: pending });
    // Полностраничный редирект: согласие пробрасываем параметром newsletter.
    window.location.href = oauthStartUrl(pending, { intent, next, newsletter, consent: policy });
  };

  return (
    <>
      <div className="space-y-2.5">
        {ordered.map((id) => {
          const ui = PROVIDER_UI[id];
          if (!ui) return null;
          return (
            <button
              key={id}
              type="button"
              onClick={() => {
                if (id === 'google' && showGoogleFallback) {
                  onGoogleEmailFallback?.();
                  return;
                }
                openConsent(id);
              }}
              className={cn(
                FOCUS_RING,
                'flex items-center justify-center gap-2.5 w-full py-2.5 rounded-xl font-medium transition-colors',
                ui.className,
              )}
            >
              {ui.logo}
              {t(id === 'google' && showGoogleEmailFallback ? 'auth.oauth.googleRegister' : ui.labelKey)}
            </button>
          );
        })}
      </div>

      {dividerLabel && (
        <div className="flex items-center gap-3 my-6">
          <div className="flex-1 h-px bg-border-subtle" />
          <span className="text-xs text-text-tertiary uppercase tracking-wider">{dividerLabel}</span>
          <div className="flex-1 h-px bg-border-subtle" />
        </div>
      )}

      {pending && createPortal((
        <div
          className="fixed inset-0 z-[200] flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm"
          onClick={() => setPending(null)}
          role="dialog"
          aria-modal="true"
          aria-label={t('auth.oauth.dialogAria')}
        >
          <div
            className="w-full max-w-md rounded-2xl border border-border-subtle bg-surface shadow-2xl ring-1 ring-black/10 p-6"
            onClick={(e) => e.stopPropagation()}
          >
            <h3 className="text-lg font-display font-bold text-text-primary mb-1">
              {t('auth.oauth.via', { provider: t(PROVIDER_NAME_KEY[pending] || pending) })}
            </h3>
            <p className="text-sm text-text-secondary mb-5">
              {t(pending === 'google' ? 'auth.oauth.googleConsentIntro' : 'auth.oauth.consentIntro')}
            </p>

            <label className="flex items-start gap-2.5 text-sm text-text-secondary cursor-pointer mb-3">
              <input
                type="checkbox"
                checked={policy}
                onChange={(e) => setPolicy(e.target.checked)}
                className="mt-0.5 accent-champagne"
              />
              <span>
                {t('auth.oauth.policyBefore')}{' '}
                <a href="/terms" target="_blank" rel="noreferrer" className="text-champagne hover:underline">{t('auth.oauth.terms')}</a>{' '}
                {t('auth.oauth.policyMid')}{' '}
                <a href="/privacy" target="_blank" rel="noreferrer" className="text-champagne hover:underline">{t('auth.oauth.privacy')}</a>
                {t('auth.oauth.policyAfter')}
              </span>
            </label>

            <label className="flex items-start gap-2.5 text-sm text-text-secondary cursor-pointer mb-6">
              <input
                type="checkbox"
                checked={newsletter}
                onChange={(e) => setNewsletter(e.target.checked)}
                className="mt-0.5 accent-champagne"
              />
              <span>{t('auth.oauth.newsletter')}</span>
            </label>

            <div className="flex items-center gap-3">
              <button
                type="button"
                onClick={proceed}
                disabled={!policy}
                className={cn(
                  FOCUS_RING,
                  'flex-1 rounded-xl py-2.5 text-sm font-semibold transition-colors',
                  PROVIDER_UI[pending]?.className || 'bg-champagne hover:bg-champagne-muted text-white',
                  !policy && 'opacity-50 cursor-not-allowed',
                )}
              >
                {t('common.continue')}
              </button>
              <button
                type="button"
                onClick={() => setPending(null)}
                className={cn(FOCUS_RING, 'rounded-xl px-4 py-2.5 text-sm font-medium text-text-secondary border border-border-subtle hover:border-champagne/40 transition-colors')}
              >
                {t('common.cancel')}
              </button>
            </div>
          </div>
        </div>
      ), document.body)}
    </>
  );
}
