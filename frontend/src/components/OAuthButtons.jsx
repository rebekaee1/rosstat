import { useEffect, useState } from 'react';
import { oauthStartUrl, fetchOAuthProviders } from '../lib/api';
import { track, events } from '../lib/track';
import { cn } from '../lib/format';
import { FOCUS_RING } from '../lib/uiTokens';
import { useT } from '../i18n';

// Фирменные кнопки в цветах провайдеров (Яндекс ID — красный, VK ID — синий).
const PROVIDER_UI = {
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

const ORDER = ['yandex', 'vk'];
const PROVIDER_NAME_KEY = {
  yandex: 'auth.oauth.provider.yandex',
  vk: 'auth.oauth.provider.vk',
};

export default function OAuthButtons({ intent = 'login', next = '/account', dividerLabel = null }) {
  const t = useT();
  const [providers, setProviders] = useState(null); // null = ещё грузим
  // Согласие перед редиректом на провайдера (звонок 2026-06-19): пользователь
  // обязан подтвердить пользовательское соглашение, рассылка — по умолчанию вкл.
  const [pending, setPending] = useState(null); // id провайдера, ждущего согласия
  const [policy, setPolicy] = useState(false);
  const [newsletter, setNewsletter] = useState(true);

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

  if (providers === null) {
    return <div className="space-y-2.5" aria-hidden>
      <div className="h-11 rounded-xl bg-obsidian-lighter/40 animate-pulse" />
      <div className="h-11 rounded-xl bg-obsidian-lighter/40 animate-pulse" />
    </div>;
  }
  if (providers.length === 0) return null;

  const ordered = ORDER.filter((id) => providers.includes(id));
  if (ordered.length === 0) return null;

  const openConsent = (id) => {
    setPolicy(false);
    setNewsletter(true);
    setPending(id);
  };

  const proceed = () => {
    if (!policy || !pending) return;
    track(events.OAUTH_START, { provider: pending, intent });
    if (newsletter) track(events.NEWSLETTER_OPT_IN, { channel: pending });
    // Полностраничный редирект: согласие пробрасываем параметром newsletter.
    window.location.href = oauthStartUrl(pending, { intent, next, newsletter });
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
              onClick={() => openConsent(id)}
              className={cn(
                FOCUS_RING,
                'flex items-center justify-center gap-2.5 w-full py-2.5 rounded-xl font-medium transition-colors',
                ui.className,
              )}
            >
              {ui.logo}
              {t(ui.labelKey)}
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

      {pending && (
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
              {t('auth.oauth.consentIntro')}
            </p>

            <label className="flex items-start gap-2.5 text-sm text-text-secondary cursor-pointer mb-3">
              <input
                type="checkbox"
                checked={policy}
                onChange={(e) => setPolicy(e.target.checked)}
                className="mt-0.5 accent-[#B8942F]"
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
                className="mt-0.5 accent-[#B8942F]"
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
                  'flex-1 rounded-xl py-2.5 text-sm font-semibold text-white transition-colors',
                  PROVIDER_UI[pending]?.className || 'bg-champagne hover:bg-champagne-muted',
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
      )}
    </>
  );
}
