/**
 * LocaleProvider — binds document lang + t() from messages.ru/en.
 * Copy lives in messages.*.js (content agents); do not put strings here.
 */
import { createContext, useContext, useEffect, useMemo, useState } from 'react';
import {
  htmlLang,
  isPreviewLocaleActive,
  PREVIEW_QUERY,
  resolveBrowserLocale,
} from './locale';
import { translate } from './messages';

const LocaleContext = createContext({
  locale: 'ru',
  t: (key) => key,
  isPreview: false,
  setPreviewLocale: () => {},
});

export function LocaleProvider({ children }) {
  const [locale, setLocale] = useState(() => resolveBrowserLocale());
  const [isPreview, setIsPreview] = useState(() => isPreviewLocaleActive());

  useEffect(() => {
    const next = resolveBrowserLocale();
    setLocale(next);
    setIsPreview(isPreviewLocaleActive());
    document.documentElement.lang = htmlLang(next);
    if (isPreviewLocaleActive()) {
      let robots = document.querySelector('meta[name="robots"]');
      if (!robots) {
        robots = document.createElement('meta');
        robots.setAttribute('name', 'robots');
        document.head.appendChild(robots);
      }
      robots.setAttribute('content', 'noindex, nofollow');
    }
  }, []);

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

export function useLocale() {
  return useContext(LocaleContext);
}

export function useT() {
  return useLocale().t;
}
