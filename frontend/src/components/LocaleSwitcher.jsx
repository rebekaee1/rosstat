import { useEffect, useRef, useState } from 'react';
import { ChevronDown } from 'lucide-react';
import { cn } from '../lib/format';
import { FOCUS_RING } from '../lib/uiTokens';
import { useLocale, useT } from '../i18n';
import { canonicalLanguageUrl } from '../i18n/locale';
import '../styles/k3-shell.css';

const LOCALES = [
  { code: 'ru', labelKey: 'nav.locale.ru' },
  { code: 'en', labelKey: 'nav.locale.en' },
];

/** Язык показываем кружком с кодом (RU / EN): флаг означает страну, а не язык. */
function LocaleFlag({ locale, className }) {
  return (
    <span
      aria-hidden="true"
      className={cn(
        'inline-flex h-[22px] w-[22px] shrink-0 items-center justify-center rounded-full',
        'fe-locale-flag text-[9.5px] font-bold uppercase leading-none tracking-[0.02em] text-text-primary',
        className,
      )}
    >
      {locale === 'en' ? 'EN' : 'RU'}
    </span>
  );
}

/**
 * Язык в шапке: кружок с кодом текущего языка, клик открывает список языков.
 * До cutover / localhost: тот же origin + ?preview_locale=en (не канон).
 * После cutover на прод-хостах: path-identical host-swap (EN=apex, RU=ru.).
 */
export default function LocaleSwitcher({ className: triggerClassName }) {
  const t = useT();
  const { locale, switchLanguage } = useLocale();
  const [open, setOpen] = useState(false);
  const wrapRef = useRef(null);
  const current = LOCALES.find((item) => item.code === locale) || LOCALES[0];

  useEffect(() => {
    if (!open) return;
    const onDoc = (e) => {
      if (wrapRef.current && !wrapRef.current.contains(e.target)) setOpen(false);
    };
    const onKey = (e) => {
      if (e.key === 'Escape') setOpen(false);
    };
    document.addEventListener('mousedown', onDoc);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onDoc);
      document.removeEventListener('keydown', onKey);
    };
  }, [open]);

  const pick = (code) => {
    setOpen(false);
    if (code === locale) return;
    switchLanguage(code);
  };

  return (
    <div className="relative" ref={wrapRef}>
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className={cn(
          FOCUS_RING,
          'flex h-8 items-center gap-1 rounded-lg px-1.5 text-text-secondary transition-colors [@media(pointer:coarse)]:h-11 [@media(pointer:coarse)]:min-w-11 [@media(pointer:coarse)]:justify-center',
          'hover:text-text-primary',
          open && 'text-champagne',
          triggerClassName,
        )}
        aria-label={`${t('nav.language')}: ${t(current.labelKey)}`}
        aria-expanded={open}
        aria-haspopup="menu"
      >
        <LocaleFlag locale={current.code} />
        <ChevronDown className={cn('h-3 w-3 transition-transform', open && 'rotate-180')} />
      </button>
      {open && (
        <div
          className={cn(
            'absolute top-full z-[110] mt-2 min-w-[10.5rem] rounded-2xl',
            'py-1.5 shadow-2xl fe-glass-pop',
            'right-0',
          )}
          role="menu"
        >
          {LOCALES.map((item) => {
            const active = item.code === locale;
            const href = canonicalLanguageUrl(item.code);
            const className = cn(
              FOCUS_RING,
              'flex w-full items-center gap-2.5 rounded-xl px-3 py-2 text-left text-sm transition-colors',
              'fe-locale-item',
              active ? 'is-active text-champagne' : 'text-text-primary',
            );
            // Production hosts: real alternate URL, identical to hreflang.
            // Click still sets the preference cookie so a geo-redirect does not
            // bounce the visitor back. Localhost keeps the preview button.
            if (href) {
              return (
                <a
                  key={item.code}
                  href={href}
                  hrefLang={item.code}
                  rel="alternate"
                  role="menuitem"
                  aria-current={active ? 'true' : undefined}
                  onClick={(event) => {
                    event.preventDefault();
                    pick(item.code);
                  }}
                  className={className}
                >
                  <LocaleFlag locale={item.code} />
                  <span>{t(item.labelKey)}</span>
                </a>
              );
            }
            return (
              <button
                key={item.code}
                type="button"
                role="menuitem"
                aria-current={active ? 'true' : undefined}
                onClick={() => pick(item.code)}
                className={className}
              >
                <LocaleFlag locale={item.code} />
                <span>{t(item.labelKey)}</span>
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
