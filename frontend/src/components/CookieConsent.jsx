import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
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

/**
 * Cookie-баннер (152-ФЗ, ст. 9): активный opt-in на аналитические (Метрика)
 * и рекламные (РСЯ) cookie. До выбора пользователя трекеры не загружаются —
 * см. public/consent.js. Выбор логируется в собственный event-collector
 * (дата + версия политики) как фиксация факта согласия.
 *
 * Повторное открытие — событие CONSENT_OPEN_EVENT («Настройки cookie»
 * в футере и на странице политики). Смена CONSENT_VERSION (новая редакция
 * политики) показывает баннер заново.
 */

const CATEGORIES = [
  {
    id: 'necessary',
    name: 'Необходимые',
    description: 'Настройки интерфейса и работа сайта. Не передаются третьим лицам.',
    locked: true,
  },
  {
    id: 'analytics',
    name: 'Аналитические',
    description: 'Яндекс Метрика: статистика посещений для улучшения сайта.',
  },
  {
    id: 'ads',
    name: 'Рекламные',
    description: 'Рекламная сеть Яндекса: показ рекламных блоков на сайте.',
  },
];

const btnBase = cn(
  FOCUS_RING,
  'rounded-xl px-4 py-2.5 text-sm font-medium transition-colors text-center'
);

export default function CookieConsent() {
  const [visible, setVisible] = useState(() => !isConsentCurrent(getConsent()));
  const [expanded, setExpanded] = useState(false);
  const [choices, setChoices] = useState({ analytics: false, ads: false });

  useEffect(() => {
    const reopen = () => {
      const current = getConsent();
      setChoices({
        analytics: Boolean(current?.analytics),
        ads: Boolean(current?.ads),
      });
      setExpanded(true);
      setVisible(true);
    };
    window.addEventListener(CONSENT_OPEN_EVENT, reopen);
    return () => window.removeEventListener(CONSENT_OPEN_EVENT, reopen);
  }, []);

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
      aria-label="Настройки cookie"
      className="fixed inset-x-0 bottom-0 z-[80] pointer-events-none sm:p-4"
    >
      <div className="pointer-events-auto mx-auto sm:mx-0 sm:max-w-md bg-obsidian border border-border-subtle sm:rounded-2xl rounded-t-2xl shadow-[0_-8px_40px_rgba(26,26,46,0.12)] sm:shadow-[0_12px_40px_rgba(26,26,46,0.16)] p-5 consent-enter">
        <div className="flex items-start gap-3 mb-3">
          <Cookie className="w-5 h-5 text-champagne shrink-0 mt-0.5" aria-hidden="true" />
          <div className="flex-1">
            <p className="text-sm font-semibold text-text-primary mb-1">Cookie на сайте</p>
            <p className="text-xs text-text-secondary leading-relaxed">
              Мы используем необходимые cookie для работы сайта. Аналитические (Яндекс Метрика)
              и рекламные (Рекламная сеть Яндекса) cookie включаются только с вашего согласия.
              Подробнее — в{' '}
              <Link to="/privacy" className="text-champagne hover:underline">
                политике конфиденциальности
              </Link>
              .
            </p>
          </div>
          <button
            type="button"
            aria-label="Закрыть без согласия"
            onClick={() => commit(false, false, 'dismiss')}
            className={cn(FOCUS_RING, 'rounded-md p-1 text-text-tertiary hover:text-text-primary transition-colors')}
          >
            <X className="w-4 h-4" aria-hidden="true" />
          </button>
        </div>

        {expanded && (
          <div className="mb-4 space-y-2">
            {CATEGORIES.map((cat) => {
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
                      {cat.name}
                      {cat.locked && (
                        <span className="ml-2 text-[10px] uppercase tracking-wider text-text-tertiary font-medium">
                          всегда активны
                        </span>
                      )}
                    </span>
                    <span className="block text-[11px] text-text-tertiary leading-relaxed mt-0.5">
                      {cat.description}
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
                Сохранить выбор
              </button>
              <button
                type="button"
                onClick={() => commit(true, true, 'accept_all')}
                className={cn(btnBase, 'flex-1 border border-border-subtle text-text-secondary hover:text-text-primary hover:border-border-champagne')}
              >
                Принять все
              </button>
            </>
          ) : (
            <>
              <button
                type="button"
                onClick={() => commit(true, true, 'accept_all')}
                className={cn(btnBase, 'flex-1 bg-champagne text-white hover:bg-champagne-muted')}
              >
                Принять все
              </button>
              <button
                type="button"
                onClick={() => commit(false, false, 'necessary_only')}
                className={cn(btnBase, 'flex-1 border border-border-subtle text-text-secondary hover:text-text-primary hover:border-border-champagne')}
              >
                Только необходимые
              </button>
              <button
                type="button"
                onClick={() => setExpanded(true)}
                className={cn(btnBase, 'sm:flex-none text-text-tertiary hover:text-text-primary')}
              >
                Настроить
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
