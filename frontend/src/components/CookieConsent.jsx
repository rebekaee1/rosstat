import { useEffect, useRef, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { X } from 'lucide-react';
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
  'min-h-11 min-w-0 rounded-xl px-3 py-2.5 text-sm font-medium transition-colors text-center'
);

function notifyOverlayVisibility(visible, expanded) {
  try {
    window.dispatchEvent(new CustomEvent('fe:analytics-overlay:change', {
      detail: { id: 'cookie-consent', visible, expanded },
    }));
  } catch { /* Measurement must never affect the dialog. */ }
}

export default function CookieConsent() {
  const t = useT();
  const { pathname } = useLocation();
  const [visible, setVisible] = useState(() => !isConsentCurrent(getConsent()));
  const [expanded, setExpanded] = useState(false);
  const committing = useRef(false);
  const overlayVisible = visible && !pathname.startsWith('/admin');
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
      committing.current = false;
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

  useEffect(() => {
    notifyOverlayVisibility(overlayVisible, expanded);
  }, [overlayVisible, expanded]);

  useEffect(() => () => notifyOverlayVisibility(false, false), []);

  // Служебные страницы (/admin/*) — баннер не показываем: админ не «посетитель»,
  // а перекрытие карточек BI мешает работе (владелец, 2026-07-06).
  if (!overlayVisible) return null;

  const commit = (analytics, ads, action) => {
    if (committing.current) return;
    committing.current = true;
    try {
      // Persist the choice before closing. Applying trackers can fail separately.
      saveConsent({ analytics, ads });
    } catch { /* A tracker failure must not trap the visitor in the dialog. */ }
    finally {
      setVisible(false);
      setExpanded(false);
    }
    try {
      track(events.CONSENT_UPDATE, {
        action,
        analytics: analytics ? 1 : 0,
        ads: ads ? 1 : 0,
        policy_version: CONSENT_VERSION,
      });
    } catch { /* The visitor's action is complete even if measurement fails. */ }
  };

  const dismiss = () => {
    const current = getConsent();
    // Closing settings keeps the saved choice, including an explicit opt-out.
    commit(
      isConsentCurrent(current) ? Boolean(current.analytics) : true,
      isConsentCurrent(current) ? Boolean(current.ads) : true,
      'dismiss',
    );
  };

  return (
    <div
      role="dialog"
      aria-modal="false"
      aria-label={t('cookie.aria')}
      className="fixed inset-x-0 bottom-0 z-[80] pointer-events-none p-3 sm:p-4"
    >
      <div
        data-analytics-overlay="cookie-consent"
        data-fe-attention-occluder="cookie-consent"
        data-fe-interaction="consent-dialog"
        className="pointer-events-auto mx-auto sm:mx-0 sm:max-w-md flex max-h-[calc(100dvh-1.5rem)] flex-col overflow-hidden rounded-2xl bg-obsidian border border-border-subtle shadow-[0_-8px_40px_rgba(26,26,46,0.12)] sm:shadow-[0_12px_40px_rgba(26,26,46,0.16)] consent-enter"
      >
        <div className="flex shrink-0 items-start gap-2 p-3 pb-1">
          <div className="min-w-0 flex-1">
            <p className="text-sm font-semibold text-text-primary mb-1">{t('cookie.title')}</p>
            {!expanded && (
              <p className="text-xs text-text-secondary leading-relaxed">
                {t('cookie.summary')}{' '}
                <Link to="/privacy" className="text-champagne hover:underline">
                  {t('cookie.privacyShort')}
                </Link>
              </p>
            )}
          </div>
          <button
            type="button"
            aria-label={t('common.close')}
            data-analytics-action="consent-dismiss"
            data-fe-interaction-action="dismiss"
            onClick={dismiss}
            className={cn(FOCUS_RING, 'flex h-11 w-11 shrink-0 items-center justify-center rounded-xl text-text-tertiary hover:text-text-primary transition-colors')}
          >
            <X className="w-4 h-4" aria-hidden="true" />
          </button>
        </div>

        {expanded && (
          <div data-consent-scroll-body className="min-h-0 overflow-y-auto overscroll-contain px-3 pb-3">
            <p className="mb-3 text-xs text-text-secondary leading-relaxed">
              {t('cookie.bodyBefore')}{' '}
              <Link to="/privacy" className="text-champagne hover:underline">
                {t('cookie.privacyLink')}
              </Link>
              .
            </p>
            <div className="space-y-2">
              {CATEGORY_DEFS.map((cat) => {
                const checked = cat.locked ? true : choices[cat.id];
                return (
                  <label
                    key={cat.id}
                    className={cn(
                      'flex min-h-11 items-start gap-3 rounded-xl border border-border-subtle px-3 py-2.5',
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
                      className="mt-0.5 accent-champagne w-4 h-4 shrink-0"
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
          </div>
        )}

        <div data-consent-actions className="grid shrink-0 grid-cols-2 gap-2 p-3 pt-1">
          {expanded ? (
            <>
              <button
                type="button"
                data-analytics-action="consent-save"
                data-fe-interaction-action="save"
                onClick={() => commit(choices.analytics, choices.ads, 'custom')}
                className={cn(btnBase, 'flex-1 bg-champagne text-white hover:bg-champagne-muted')}
              >
                {t('cookie.save')}
              </button>
              <button
                type="button"
                data-analytics-action="consent-accept-all"
                data-fe-interaction-action="accept-all"
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
                data-analytics-action="consent-accept"
                data-fe-interaction-action="accept"
                onClick={() => commit(true, true, 'accept_all')}
                className={cn(btnBase, 'flex-1 bg-champagne text-white hover:bg-champagne-muted')}
              >
                {t('cookie.accept')}
              </button>
              <button
                type="button"
                data-analytics-action="consent-customize"
                data-fe-interaction-action="customize"
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
