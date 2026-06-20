import { useEffect } from 'react';

const BASE = 'https://forecasteconomy.com';

// Title без бренд-суффикса: backend SSR (seo_renderer.py::build_document) кладёт
// в <title> ровно тот же текст, что и API возвращает в indicator.seo_title /
// CategorySeo.title / PageSeo.title. Если клиент допишет здесь "| Forecast Economy",
// после React-гидратации Yandex/Google увидят другой title и расценят страницу
// как изменившуюся → удаление и повторное добавление в индексе. См. инцидент
// 2026-04-29 «страницы добавляются и удаляются» в Webmaster.
const DEFAULTS = {
  title: 'Forecast Economy — бесплатная аналитика экономики России',
  description:
    'Forecast Economy — бесплатная платформа макроэкономической аналитики России. ' +
    '100+ индикаторов в 9 категориях: ВВП, цены, ставки, валюты, рынок труда, население и торговля. ' +
    'Данные Росстата и ЦБ РФ, прогнозы. Без регистрации.',
};

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
  // null/undefined → не трогаем <head> вообще, оставляем то, что положил backend SSR.
  // Это нужно, пока данные индикатора ещё не загружены: иначе title мигает
  // на промежуточное значение ("Индикатор cpi") и поисковик может сделать
  // snapshot именно в этот момент.
  const skip = !options;
  const title = options?.title;
  const description = options?.description;
  const path = options?.path ?? '/';
  const robots = options?.robots; // напр. 'noindex, nofollow' для /account, /login

  useEffect(() => {
    if (skip) return;

    const fullTitle = title || DEFAULTS.title;
    const desc = description || DEFAULTS.description;
    const url = `${BASE}${path}`;

    document.title = fullTitle;
    setMeta('description', desc);
    setMeta('keywords', 'экономика России, макроэкономические данные, Росстат, Банк России, ВВП, инфляция, ставки, валюты');
    setCanonical(url);
    setProperty('og:title', fullTitle);
    setProperty('og:description', desc);
    setProperty('og:url', url);
    if (robots) {
      setMeta('robots', robots);
    }
  }, [skip, title, description, path, robots]);
}
