import { useEffect, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { Cookie, X } from 'lucide-react';
import { cn } from '../lib/format';
import { FOCUS_RING } from '../lib/uiTokens';
import { track, events } from '../lib/track';
import {
  CONSENT_OPEN_EVENT,
  CONSENT_VERSION,
  getConsent,
  isConsentCurrent,
  saveConsent,
} from '../lib/consent';
import { useT } from '../i18n';

/**
 * Cookie-баннер (152-ФЗ): информирование о подразумеваемом согласии.
 * Продолжая пользоваться сайтом, посетитель соглашается на использование
 * cookie, включая аналитические (Яндекс Метрика) и рекламные (РСЯ). По
 * умолчанию трекеры загружаются сразу (см. public/consent.js), баннер лишь
 * информирует и фиксирует факт согласия. Отказаться можно через «Настроить».
 *
 * Повторное открытие — событие CONSENT_OPEN_EVENT («Настройки cookie»
 * в футере и на странице политики). Смена CONSENT_VERSION (новая редакция
 * политики) показывает баннер заново.
 */

const CATEGORY_DEFS = [
  {
    id: 'necessary',
    nameKey: 'cookie.cat.necessary',
    descKey: 'cookie.cat.necessaryDesc',
    locked: true,
  },
  {
    id: 'analytics',
    nameKey: 'cookie.cat.analytics',
    descKey: 'cookie.cat.analyticsDesc',
  },
  {
    id: 'ads',
    nameKey: 'cookie.cat.ads',
    descKey: 'cookie.cat.adsDesc',
  },
];

const btnBase = cn(
  FOCUS_RING,
  'rounded-xl px-4 py-2.5 text-sm font-medium transition-colors text-center'
);

export default function CookieConsent() {
  const t = useT();
  const { pathname } = useLocation();
  const [visible, setVisible] = useState(() => !isConsentCurrent(getConsent()));
  const [expanded, setExpanded] = useState(false);
  // Подразумеваемое согласие: по умолчанию всё включено (трекеры уже загружены).
  const [choices, setChoices] = useState(() => {
    const current = getConsent();
    return {
      analytics: current ? Boolean(current.analytics) : true,
      ads: current ? Boolean(current.ads) : true,
    };
  });

  useEffect(() => {
    const reopen = () => {
      const current = getConsent();
      setChoices({
        analytics: current ? Boolean(current.analytics) : true,
        ads: current ? Boolean(current.ads) : true,
      });
      setExpanded(true);
      setVisible(true);
    };
    window.addEventListener(CONSENT_OPEN_EVENT, reopen);
    return () => window.removeEventListener(CONSENT_OPEN_EVENT, reopen);
  }, []);

  // Служебные страницы (/admin/*) — баннер не показываем: админ не «посетитель»,
  // а перекрытие карточек BI мешает работе (владелец, 2026-07-06).
  if (pathname.startsWith('/admin')) return null;
  if (!visible) return null;

  const commit = (analytics, ads, action) => {
    saveConsent({ analytics, ads });
    track(events.CONSENT_UPDATE, {
      action,
      analytics: analytics ? 1 : 0,
      ads: ads ? 1 : 0,
      policy_version: CONSENT_VERSION,
    });
    setVisible(false);
    setExpanded(false);
  };

  return (
    <div
      role="dialog"
      aria-modal="false"
      aria-label={t('cookie.aria')}
      className="fixed inset-x-0 bottom-0 z-[80] pointer-events-none sm:p-4"
    >
      <div className="pointer-events-auto mx-auto sm:mx-0 sm:max-w-md bg-obsidian border border-border-subtle sm:rounded-2xl rounded-t-2xl shadow-[0_-8px_40px_rgba(26,26,46,0.12)] sm:shadow-[0_12px_40px_rgba(26,26,46,0.16)] p-5 consent-enter">
        <div className="flex items-start gap-3 mb-3">
          <Cookie className="w-5 h-5 text-champagne shrink-0 mt-0.5" aria-hidden="true" />
          <div className="flex-1">
            <p className="text-sm font-semibold text-text-primary mb-1">{t('cookie.title')}</p>
            <p className="text-xs text-text-secondary leading-relaxed">
              {t('cookie.bodyBefore')}{' '}
              <Link to="/privacy" className="text-champagne hover:underline">
                {t('cookie.privacyLink')}
              </Link>
              .
            </p>
          </div>
          <button
            type="button"
            aria-label={t('common.close')}
            onClick={() => commit(true, true, 'dismiss')}
            className={cn(FOCUS_RING, 'rounded-md p-1 text-text-tertiary hover:text-text-primary transition-colors')}
          >
            <X className="w-4 h-4" aria-hidden="true" />
          </button>
        </div>

        {expanded && (
          <div className="mb-4 space-y-2">
            {CATEGORY_DEFS.map((cat) => {
              const checked = cat.locked ? true : choices[cat.id];
              return (
                <label
                  key={cat.id}
                  className={cn(
                    'flex items-start gap-3 rounded-xl border border-border-subtle px-3 py-2.5',
                    cat.locked ? 'opacity-70' : 'cursor-pointer hover:border-border-champagne transition-colors'
                  )}
                >
                  <input
                    type="checkbox"
                    checked={checked}
                    disabled={cat.locked}
                    onChange={(e) =>
                      setChoices((prev) => ({ ...prev, [cat.id]: e.target.checked }))
                    }
                    className="mt-0.5 accent-[#B8942F] w-4 h-4 shrink-0"
                  />
                  <span className="flex-1">
                    <span className="block text-xs font-semibold text-text-primary">
                      {t(cat.nameKey)}
                      {cat.locked && (
                        <span className="ml-2 text-[10px] uppercase tracking-wider text-text-tertiary font-medium">
                          {t('cookie.alwaysOn')}
                        </span>
                      )}
                    </span>
                    <span className="block text-[11px] text-text-tertiary leading-relaxed mt-0.5">
                      {t(cat.descKey)}
                    </span>
                  </span>
                </label>
              );
            })}
          </div>
        )}

        <div className="flex flex-col sm:flex-row gap-2">
          {expanded ? (
            <>
              <button
                type="button"
                onClick={() => commit(choices.analytics, choices.ads, 'custom')}
                className={cn(btnBase, 'flex-1 bg-champagne text-white hover:bg-champagne-muted')}
              >
                {t('cookie.save')}
              </button>
              <button
                type="button"
                onClick={() => commit(true, true, 'accept_all')}
                className={cn(btnBase, 'flex-1 border border-border-subtle text-text-secondary hover:text-text-primary hover:border-border-champagne')}
              >
                {t('cookie.acceptAll')}
              </button>
            </>
          ) : (
            <>
              <button
                type="button"
                onClick={() => commit(true, true, 'accept_all')}
                className={cn(btnBase, 'flex-1 bg-champagne text-white hover:bg-champagne-muted')}
              >
                {t('cookie.accept')}
              </button>
              <button
                type="button"
                onClick={() => setExpanded(true)}
                className={cn(btnBase, 'sm:flex-none border border-border-subtle text-text-secondary hover:text-text-primary hover:border-border-champagne')}
              >
                {t('cookie.customize')}
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
