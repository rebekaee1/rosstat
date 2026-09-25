import { useEffect } from 'react';
import { useLocation } from 'react-router-dom';
import { resolveBrowserLocale } from '../i18n/locale';
import { getPageSeo } from './pageMeta';
import { getSiteOrigin, publicPageUrl } from './siteOrigin';
import { pageImagePath } from './pageImage';

// Title без бренд-суффикса: backend SSR (seo_renderer.py::build_document) кладёт
// в <title> ровно тот же текст, что и API возвращает в indicator.seo_title /
// CategorySeo.title / PageSeo.title. Если клиент допишет здесь "| Forecast Economy",
// после React-гидратации Yandex/Google увидят другой title и расценят страницу
// как изменившуюся → удаление и повторное добавление в индексе. См. инцидент
// 2026-04-29 «страницы добавляются и удаляются» в Webmaster.
const KEYWORDS = {
  ru: 'экономика России, макроэкономические данные, Росстат, Банк России, ВВП, инфляция, ставки, валюты',
  en: 'macroeconomic indicators, official statistics, GDP, inflation, unemployment, interest rates, Eurostat, IMF',
};
const PUBLIC_ROBOTS = 'index, follow, max-snippet:-1, max-image-preview:large, max-video-preview:-1';

function setMeta(name, content) {
  let el = document.querySelector(`meta[name="${name}"]`);
  if (!el) {
    el = document.createElement('meta');
    el.setAttribute('name', name);
    document.head.appendChild(el);
  }
  el.setAttribute('content', content);
}

function setProperty(property, content) {
  let el = document.querySelector(`meta[property="${property}"]`);
  if (!el) {
    el = document.createElement('meta');
    el.setAttribute('property', property);
    document.head.appendChild(el);
  }
  el.setAttribute('content', content);
}

function setCanonical(href) {
  let el = document.querySelector('link[rel="canonical"]');
  if (!el) {
    el = document.createElement('link');
    el.setAttribute('rel', 'canonical');
    document.head.appendChild(el);
  }
  el.setAttribute('href', href);
}

export default function useDocumentMeta(options) {
  const location = useLocation();
  // null/undefined → не трогаем <head> вообще, оставляем то, что положил backend SSR.
  // Это нужно, пока данные индикатора ещё не загружены: иначе title мигает
  // на промежуточное значение ("Индикатор cpi") и поисковик может сделать
  // snapshot именно в этот момент.
  const skip = !options;
  const title = options?.title;
  const description = options?.description;
  const path = options?.path ?? location.pathname;
  const robots = options?.robots; // напр. 'noindex, nofollow' для /account, /login
  const params = new URLSearchParams(location.search);
  const preview = params.has('preview_locale');
  const previewLocale = params.get('preview_locale');
  const locale = previewLocale === 'en' || previewLocale === 'ru'
    ? previewLocale
    : resolveBrowserLocale();
  // Year-controlled maps/rankings carry the selected year in the URL query.
  // Other query keys are ignored by pageImagePath, and never enter canonical.
  const imageRoute = path.includes('?') ? path : `${path}${location.search}`;
  const imagePath = options?.image || pageImagePath(imageRoute);

  useEffect(() => {
    if (skip) return;

    const home = getPageSeo('home', locale);
    const fullTitle = title || home?.title || 'Forecast Economy';
    const desc = description || home?.description || '';
    const url = publicPageUrl(getSiteOrigin(), path);

    document.title = fullTitle;
    setMeta('description', desc);
    setMeta('keywords', KEYWORDS[locale] || KEYWORDS.ru);
    setCanonical(url);
    setProperty('og:title', fullTitle);
    setProperty('og:description', desc);
    setProperty('og:url', url);
    setProperty('og:locale', locale === 'en' ? 'en_US' : 'ru_RU');
    setMeta('twitter:card', 'summary_large_image');
    setMeta('twitter:title', fullTitle);
    setMeta('twitter:description', desc);
    if (imagePath) {
      const image = imagePath.startsWith('/') ? `${getSiteOrigin()}${imagePath}` : imagePath;
      setProperty('og:image', image);
      setProperty('og:image:alt', fullTitle);
      setMeta('twitter:image', image);
      setMeta('twitter:image:alt', fullTitle);
    }
    const directives = robots || PUBLIC_ROBOTS;
    setMeta('robots', preview
      ? ['noindex', ...directives.split(',').map((s) => s.trim()).filter((s) => s !== 'index' && s !== 'noindex')].join(', ')
      : directives);
  }, [skip, title, description, path, robots, preview, locale, imagePath]);
}
