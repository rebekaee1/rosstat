import { useEffect, useRef, useState } from 'react';
import { ChevronDown } from 'lucide-react';
import { cn } from '../lib/format';
import { FOCUS_RING } from '../lib/uiTokens';
import { useLocale, useT } from '../i18n';

const LOCALES = [
  { code: 'ru', labelKey: 'nav.locale.ru' },
  { code: 'en', labelKey: 'nav.locale.en' },
];

function FlagRu({ className }) {
  return (
    <svg viewBox="0 0 16 12" className={className} aria-hidden focusable="false">
      <rect width="16" height="4" fill="#fff" />
      <rect y="4" width="16" height="4" fill="#0039A6" />
      <rect y="8" width="16" height="4" fill="#D52B1E" />
    </svg>
  );
}

function FlagUs({ className }) {
  return (
    <svg viewBox="0 0 16 12" className={className} aria-hidden focusable="false">
      <rect width="16" height="12" fill="#BF0A30" />
      <rect y="1.09" width="16" height="1.09" fill="#fff" />
      <rect y="3.27" width="16" height="1.09" fill="#fff" />
      <rect y="5.45" width="16" height="1.09" fill="#fff" />
      <rect y="7.64" width="16" height="1.09" fill="#fff" />
      <rect y="9.82" width="16" height="1.09" fill="#fff" />
      <rect width="7.2" height="6.54" fill="#002868" />
      <circle cx="1.6" cy="1.5" r="0.38" fill="#fff" />
      <circle cx="3.6" cy="1.5" r="0.38" fill="#fff" />
      <circle cx="5.6" cy="1.5" r="0.38" fill="#fff" />
      <circle cx="2.6" cy="3.15" r="0.38" fill="#fff" />
      <circle cx="4.6" cy="3.15" r="0.38" fill="#fff" />
      <circle cx="1.6" cy="4.8" r="0.38" fill="#fff" />
      <circle cx="3.6" cy="4.8" r="0.38" fill="#fff" />
      <circle cx="5.6" cy="4.8" r="0.38" fill="#fff" />
    </svg>
  );
}

function LocaleFlag({ locale, className }) {
  return (
    <span
      className={cn(
        'inline-flex h-[14px] w-[18px] shrink-0 overflow-hidden rounded-[2px]',
        'ring-1 ring-black/[0.14] dark:ring-white/20',
        className,
      )}
    >
      {locale === 'en' ? (
        <FlagUs className="h-full w-full" />
      ) : (
        <FlagRu className="h-full w-full" />
      )}
    </span>
  );
}

/**
 * Язык в шапке: флаг текущей локали, клик открывает список флагов.
 * Переход — тот же switchLanguage (хост en.* / ru.* / apex), не ?lang=.
 */
export default function LocaleSwitcher() {
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
          'flex h-8 items-center gap-1 rounded-lg px-1.5 text-text-secondary transition-colors',
          'hover:text-text-primary',
          open && 'text-champagne',
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
            'absolute top-full z-[110] mt-2 min-w-[10.5rem] rounded-2xl border border-border-subtle',
            'bg-surface py-1.5 shadow-2xl ring-1 ring-black/[0.08]',
            'right-0',
          )}
          role="menu"
        >
          {LOCALES.map((item) => {
            const active = item.code === locale;
            return (
              <button
                key={item.code}
                type="button"
                role="menuitem"
                aria-current={active ? 'true' : undefined}
                onClick={() => pick(item.code)}
                className={cn(
                  FOCUS_RING,
                  'flex w-full items-center gap-2.5 rounded-xl px-3 py-2 text-left text-sm transition-colors',
                  'hover:bg-obsidian-lighter/80',
                  active ? 'text-champagne bg-champagne/5' : 'text-text-primary',
                )}
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
