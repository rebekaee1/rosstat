import { useEffect, useRef, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { Settings2, X } from 'lucide-react';
import { cn } from '../lib/format';
import { FOCUS_RING } from '../lib/uiTokens';
import Button from './Button';
import { track, events } from '../lib/track';
import {
  CONSENT_OPEN_EVENT,
  CONSENT_VERSION,
  getConsent,
  isConsentCurrent,
  saveConsent,
} from '../lib/consent';
import { useT } from '../i18n';
import useMediaQuery from '../lib/useMediaQuery';
import { useScrollDirection } from '../lib/useScrollDirection';
import '../styles/shell.css';
import '../styles/z2-shell.css';
import '../styles/k3-shell.css';

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
 *
 * Телефон: после первой прокрутки плашка прячется целиком (плавающего значка нет: он ложился на цифры и кнопки страницы).
 * «Настройки cookie» остаются в меню «Ещё» и в подвале; вернувшись наверх страницы, посетитель снова видит плашку.
 * Прятание не записывает согласие: молчание остаётся молчанием, трекеры и выбор не меняются.
 */

// Два переключателя обычными словами вместо названий сервисов. «Необходимые» — не переключатель, а строка текста.
const CATEGORY_DEFS = [
  { id: 'analytics', nameKey: 'shell3.cookie.analytics', descKey: 'shell3.cookie.analyticsDesc' },
  { id: 'ads', nameKey: 'shell3.cookie.ads', descKey: 'shell3.cookie.adsDesc' },
];

// Кнопки баннера делят ширину поровну и переносят подпись на узком экране.
const btnBase = 'min-w-0 whitespace-normal! text-center';

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
  // Телефон: после первой прокрутки плашка спрятана (открытые настройки не прячутся).
  const phone = useMediaQuery('(max-width: 639px)');
  const { scrolled } = useScrollDirection();
  const collapsed = phone && scrolled && !expanded;
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
    notifyOverlayVisibility(overlayVisible && !collapsed, expanded);
  }, [overlayVisible, expanded, collapsed]);

  useEffect(() => () => notifyOverlayVisibility(false, false), []);

  // Баннер не должен навсегда закрывать конец страницы: резервируем под ним место внизу документа
  // (переменная читается в styles/z2-shell.css: она добавляется к нижнему отступу подвала, фон подвала доходит до края).
  const panelRef = useRef(null);
  useEffect(() => {
    if (!overlayVisible || typeof document === 'undefined') return undefined;
    const root = document.documentElement;
    const node = panelRef.current;
    // Спрятанная плашка места внизу документа не занимает.
    if (collapsed || !node) return undefined;
    const apply = () => {
      const h = Math.ceil(node.getBoundingClientRect().height);
      root.style.setProperty('--fe-cookie-h', `${h + 12}px`);
    };
    apply();
    let observer = null;
    if (node && typeof ResizeObserver !== 'undefined') {
      observer = new ResizeObserver(apply);
      observer.observe(node);
    }
    return () => {
      if (observer) observer.disconnect();
      root.style.removeProperty('--fe-cookie-h');
    };
  }, [overlayVisible, expanded, collapsed]);

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

  if (collapsed) return null;

  return (
    <div
      role="dialog"
      aria-modal="false"
      aria-label={t('cookie.aria')}
      // Появление (прозрачность и сдвиг) играет обёртка, а не панель с blur: пока идёт анимация, размытие не пересчитывается.
      className="fe-cookie-wrap fe-reveal fe-reveal--free fixed inset-x-0 bottom-0 z-[80] pointer-events-none p-2 [padding-bottom:max(0.5rem,env(safe-area-inset-bottom))] [--fe-duration:0.22s] [--fe-rise:10px] sm:right-auto sm:p-4"
    >
      <div
        ref={panelRef}
        data-analytics-overlay="cookie-consent"
        data-fe-attention-occluder="cookie-consent"
        data-fe-interaction="consent-dialog"
        data-expanded={expanded ? 'true' : 'false'}
        className="fe-cookie-panel pointer-events-auto mx-auto sm:mx-0 flex max-h-[min(30rem,calc(100dvh-1.5rem))] flex-col overflow-hidden sm:max-w-[26rem]"
      >
        {expanded ? (
          <div className="flex shrink-0 items-start gap-1 px-3 pt-3 pb-1">
            <div className="min-w-0 flex-1 self-center">
              <p className="text-sm font-semibold text-text-primary mb-1">{t('cookie.title')}</p>
            </div>
            <button
              type="button"
              aria-label={t('common.close')}
              data-analytics-action="consent-dismiss"
              data-fe-interaction-action="dismiss"
              onClick={dismiss}
              className={cn(FOCUS_RING, 'fe-press -mr-1 flex h-11 w-11 shrink-0 items-center justify-center rounded-xl text-text-tertiary hover:text-text-primary transition-colors')}
            >
              <X className="w-4 h-4" aria-hidden="true" />
            </button>
          </div>
        ) : (
          <div className="fe-cookie-compact">
            <p className="fe-cookie-compact__text">
              <span className="fe-cookie-compact__long">{t('cookie.summary')}</span>
              <span className="fe-cookie-compact__short">{t('z2.cookie.short')}</span>
              {' '}
              <Link to="/privacy" className="text-champagne-ink hover:underline">
                {t('cookie.privacyShort')}
              </Link>
            </p>
            <div className="fe-cookie-compact__actions">
              <Button
                data-analytics-action="consent-accept"
                data-fe-interaction-action="accept"
                onClick={() => commit(true, true, 'accept_all')}
                className={cn(btnBase, 'fe-cookie-accept')}
              >
                {t('cookie.accept')}
              </Button>
              <Button
                variant="ghost"
                data-analytics-action="consent-customize"
                data-fe-interaction-action="customize"
                onClick={() => setExpanded(true)}
                title={t('cookie.customize')}
                className={cn(btnBase, 'fe-cookie-gear')}
              >
                <Settings2 aria-hidden="true" />
                <span className="fe-cookie-gear__label">{t('cookie.customize')}</span>
              </Button>
            </div>
          </div>
        )}

        {expanded && (
          <div data-consent-scroll-body className="min-h-0 overflow-y-auto overscroll-contain px-3 pb-3">
            <p className="mb-3 text-[13px] text-text-secondary leading-snug">
              {t('shell3.cookie.intro')}{' '}
              <Link to="/privacy" className="text-champagne-ink hover:underline">
                {t('cookie.privacyShort')}
              </Link>
            </p>
            <div className="space-y-2">
              {CATEGORY_DEFS.map((cat) => (
                <label key={cat.id} className="fe-cookie-row">
                  <span className="min-w-0 flex-1">
                    <span className="block text-sm font-semibold text-text-primary">{t(cat.nameKey)}</span>
                    <span className="mt-0.5 block text-[13px] leading-snug text-text-secondary">{t(cat.descKey)}</span>
                  </span>
                  <input
                    type="checkbox"
                    role="switch"
                    checked={choices[cat.id]}
                    onChange={(e) => setChoices((prev) => ({ ...prev, [cat.id]: e.target.checked }))}
                    className="fe-cookie-switch"
                  />
                </label>
              ))}
            </div>
          </div>
        )}

        {expanded && (
        <div data-consent-actions className="grid shrink-0 grid-cols-2 gap-2 px-3 pb-3 pt-1">
            <>
              <Button
                data-analytics-action="consent-save"
                data-fe-interaction-action="save"
                onClick={() => commit(choices.analytics, choices.ads, 'custom')}
                className={cn(btnBase, 'flex-1')}
              >
                {t('cookie.save')}
              </Button>
              <Button
                variant="secondary"
                data-analytics-action="consent-accept-all"
                data-fe-interaction-action="accept-all"
                onClick={() => commit(true, true, 'accept_all')}
                className={cn(btnBase, 'flex-1')}
              >
                {t('cookie.acceptAll')}
              </Button>
              <Button
                variant="ghost"
                data-analytics-action="consent-necessary-only"
                data-fe-interaction-action="necessary-only"
                onClick={() => commit(false, false, 'necessary_only')}
                className={cn(btnBase, 'col-span-2')}
              >
                {t('shell.cookie.necessaryOnly')}
              </Button>
            </>
        </div>
        )}
      </div>
    </div>
  );
}
