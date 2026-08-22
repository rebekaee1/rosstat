/**
 * LocaleProvider — binds document lang + t() from messages.ru/en.
 * Copy lives in messages.*.js (content agents); do not put strings here.
 */
import { useEffect, useMemo, useState } from 'react';
import {
  htmlLang,
  isPreviewLocaleActive,
  PREVIEW_QUERY,
  resolveBrowserLocale,
} from './locale';
import { translate } from './messages';
import { LocaleContext } from './localeContext';

export function LocaleProvider({ children }) {
  // Локаль известна до первого рендера (хост или ?preview_locale), поэтому
  // в эффекте только DOM: перезапись состояния давала каскадный рендер.
  const [locale] = useState(() => resolveBrowserLocale());
  const [isPreview] = useState(() => isPreviewLocaleActive());

  useEffect(() => {
    document.documentElement.lang = htmlLang(locale);
    if (isPreview) {
      let robots = document.querySelector('meta[name="robots"]');
      if (!robots) {
        robots = document.createElement('meta');
        robots.setAttribute('name', 'robots');
        document.head.appendChild(robots);
      }
      robots.setAttribute('content', 'noindex, nofollow');
    }
  }, [locale, isPreview]);

  const value = useMemo(() => {
    const t = (key, varsOrFallback) => translate(key, varsOrFallback, locale);
    const setPreviewLocale = (next) => {
      const url = new URL(window.location.href);
      if (next === 'ru' || next === 'en') {
        url.searchParams.set(PREVIEW_QUERY, next);
      } else {
        url.searchParams.delete(PREVIEW_QUERY);
      }
      window.location.assign(url.toString());
    };
    return { locale, t, isPreview, setPreviewLocale };
  }, [locale, isPreview]);

  return <LocaleContext.Provider value={value}>{children}</LocaleContext.Provider>;
}
