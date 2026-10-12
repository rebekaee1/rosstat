/**
 * Настройки кабинета, которые сайт реально применяет (круг 12, UI2). Сервер хранит шесть полей (`lib/cabinetApi.js`, `PrefsForm`);
 * применяются три:
 *   number_format  разделители чисел: 'ru' (1 234,5) или 'en' (1,234.5) независимо от языка страницы (`lib/format.js`, `setNumberFormat`);
 *   currency       валюта конвертера на «Курсах валют» по умолчанию (`CurrencyDesk`), пока человек сам не выбрал другую;
 *   home_country   первая быстрая ссылка на главной «Ваша страна» (`HomeHero`).
 * Не применяются: `locale` (язык задаёт хост страницы, ADR-0003/0013, автопереход между хостами теряет сессию и ломает адреса),
 * `units` (единицы подбираются по величине в `formatTileValue`, общего выбора вида единиц нет), `newsletter_topics` (письма не отправляются).
 * Настройки читаются один раз на вход (`CabinetPrefsApplier` в App) и сразу обновляются после сохранения в форме.
 */
import { useSyncExternalStore } from 'react';
import { setNumberFormat } from './format';

let prefs = null;
const listeners = new Set();
const subscribe = (fn) => { listeners.add(fn); return () => listeners.delete(fn); };
const emit = () => listeners.forEach((fn) => fn());

export const getPrefs = () => prefs;

export const NUMBER_FORMAT_EVENT = 'fe:number-format';
const NUMBER_FORMATS = ['ru', 'en'];
const CURRENCIES = ['USD', 'EUR', 'CNY'];

/** Принять настройки (или `null` при выходе). Возвращает true, если поменялся вид чисел (тогда уходит событие NUMBER_FORMAT_EVENT). */
export function applyPrefs(next) {
  const clean = next && typeof next === 'object' ? { ...next } : null;
  const numberFormat = clean && NUMBER_FORMATS.includes(clean.number_format) ? clean.number_format : null;
  const changedNumbers = setNumberFormat(numberFormat);
  prefs = clean;
  emit();
  // Числа рисуются прямо в разметке страниц: перерисовку всего содержимого просит App (`CabinetPrefsApplier`).
  if (changedNumbers && typeof window !== 'undefined') window.dispatchEvent(new Event(NUMBER_FORMAT_EVENT));
  return changedNumbers;
}

export function usePrefs() {
  return useSyncExternalStore(subscribe, getPrefs, () => null);
}

/** Валюта, с которой открывается конвертер (USD, EUR или CNY); рубль и всё остальное оставляют прежний вход «USD → RUB». */
export function converterCurrency(p) {
  return p && CURRENCIES.includes(p.currency) ? p.currency : null;
}

/** Slug страны для быстрой ссылки на главной или null. */
export function homeCountrySlug(p) {
  return p && typeof p.home_country === 'string' && /^[a-z0-9-]{2,60}$/.test(p.home_country) ? p.home_country : null;
}

export function __resetPrefs() {
  prefs = null;
  setNumberFormat(null);
  emit();
}
