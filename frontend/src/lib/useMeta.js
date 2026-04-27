import { useEffect } from 'react';

const BASE = 'https://forecasteconomy.com';
const DEFAULTS = {
  title: 'Forecast Economy | Бесплатная аналитика экономики России',
  description:
    'Forecast Economy — бесплатная платформа макроэкономической аналитики России. ' +
    '80+ индикаторов в 9 категориях: индекс потребительских цен (ИПЦ), ВВП, ставки, валюты, рынок труда, торговля. ' +
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

export default function useDocumentMeta({ title, description, path = '/' }) {
  useEffect(() => {
    const fullTitle = title ? `${title} | Forecast Economy` : DEFAULTS.title;
    const desc = description || DEFAULTS.description;
    const url = `${BASE}${path}`;

    document.title = fullTitle;
    setMeta('description', desc);
    setCanonical(url);
    setProperty('og:title', fullTitle);
    setProperty('og:description', desc);
    setProperty('og:url', url);

  }, [title, description, path]);
}
