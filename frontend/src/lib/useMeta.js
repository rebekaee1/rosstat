import { useEffect } from 'react';

const BASE = 'https://forecasteconomy.com';
const DEFAULTS = {
  title: 'RuStats | Прогноз инфляции и ИПЦ России',
  description:
    'RuStats — аналитическая платформа прогнозирования инфляции в России. ' +
    'Данные Росстата, OLS-модель, исторические ряды ИПЦ с 1991 года.',
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
    const fullTitle = title ? `${title} | RuStats` : DEFAULTS.title;
    const desc = description || DEFAULTS.description;
    const url = `${BASE}${path}`;

    document.title = fullTitle;
    setMeta('description', desc);
    setCanonical(url);
    setProperty('og:title', fullTitle);
    setProperty('og:description', desc);
    setProperty('og:url', url);

    return () => {
      document.title = DEFAULTS.title;
    };
  }, [title, description, path]);
}
