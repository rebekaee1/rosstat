/**
 * LocaleProvider — binds document lang + t() from messages.ru/en.
 * Copy lives in messages.*.js (content agents); do not put strings here.
 */
import { useEffect, useMemo, useState } from 'react';
import {
  apexLocaleEnEnabled,
  bindUiLocale,
  htmlLang,
  isPreviewLocaleActive,
  PREVIEW_QUERY,
  resolveBrowserLocale,
  setLocalePreference,
  switchLanguage,
} from './locale';
import { translate } from './messages';
import { LocaleContext } from './localeContext';

export function LocaleProvider({ children, locale: localeProp }) {
  // Локаль известна до первого рендера (хост, ?preview_locale или cookie).
  // localeProp — для тестов (EN через preview без window.location).
  const [locale] = useState(() => localeProp || resolveBrowserLocale());
  const [isPreview] = useState(() => Boolean(localeProp) || isPreviewLocaleActive());
  bindUiLocale(locale);

  useEffect(() => {
    bindUiLocale(locale);
    return () => bindUiLocale(undefined);
  }, [locale]);

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
        setLocalePreference(next);
        url.searchParams.set(PREVIEW_QUERY, next);
      } else {
        if (!apexLocaleEnEnabled()) setLocalePreference('ru');
        url.searchParams.delete(PREVIEW_QUERY);
      }
      window.location.assign(url.toString());
    };
    return { locale, t, isPreview, setPreviewLocale, switchLanguage };
  }, [locale, isPreview]);

  return <LocaleContext.Provider value={value}>{children}</LocaleContext.Provider>;
}
