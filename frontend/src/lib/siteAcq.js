// Привлечение (совет 19.11.2026, общая стратегия, раздел 1): строка «присылать» под числом и первый экран.
//
// Флаги приходят от бэкенда (GET /api/v1/site-acq/config) и переключаются переменными окружения без
// пересборки фронта; по умолчанию всё выключено. Ошибка запроса = выключено.
// Ссылка ведёт в публичного бота: `t.me/<бот>?start=site_<тема>` — бот разбирает тему из хвоста кода
// (backend/app/services/public_bot.py::parse_start), код `site_*` пишется в событие start.
// Тексты — чистые функции ниже (lineCopy, isDelayed), чтобы их проверяли тесты без браузера.
import { useEffect, useState } from 'react';

const CONFIG_URL = '/api/v1/site-acq/config';
const OFF = Object.freeze({ line: false, topics: [], bot: '', first_screen: false, mail_topics: [] });

/** Код страницы → тема публичного бота. На ИПЦ бот присылает инфляцию за год (cpi-yoy), текст строки говорит о ней. */
export const PAGE_TOPIC = Object.freeze({
  'fuel-diesel': 'diesel',
  'fuel-ai92': 'ai92',
  'fuel-ai95': 'ai95',
  cpi: 'inflation',
  'cpi-yoy': 'inflation',
  'gold-price': 'gold',
  'key-rate': 'keyrate',
  'deposit-rate': 'deposit',
  'mortgage-rate': 'mortgage',
  'usd-rub': 'usd',
  'eur-rub': 'eur',
});

/** Страницы первого экрана (10 главных входов из Яндекса): темы бота + зарплата и население — без строки «присылать». */
export const FIRST_SCREEN_CODES = new Set([...Object.keys(PAGE_TOPIC), 'wages-nominal', 'population']);

/** Чей выход данных смотреть в календаре: код показателя, к которому привязаны события. */
const RELEASE_CODE = Object.freeze({
  cpi: 'cpi',
  'cpi-yoy': 'cpi',
  'key-rate': 'key-rate',
  'deposit-rate': 'deposit-rate',
  'mortgage-rate': 'mortgage-rate',
  'wages-nominal': 'wages-nominal',
  population: 'population',
});

export function releaseCodeOf(code) {
  return RELEASE_CODE[code] || null;
}

// Сколько дней ряд может стоять без новой точки по обычному графику источника (с запасом).
// Месячные ряды выходят с лагом до двух месяцев (ставки по вкладам), поэтому порог 100 дней.
const NORMAL_AGE_DAYS = { daily: 6, weekly: 12, monthly: 100, quarterly: 200, annual: 500 };
const DAY_MS = 86400000;

function dayNumber(value) {
  if (!value) return null;
  const d = value instanceof Date ? value : new Date(`${String(value).slice(0, 10)}T00:00:00Z`);
  const t = d.getTime();
  return Number.isNaN(t) ? null : Math.floor(t / DAY_MS);
}

/**
 * Источник задерживает данные: сервер пометил ряд устаревшим, или последняя точка старше обычного
 * и ближайший выход по календарю не ожидается в ближайшие 14 дней.
 */
export function isDelayed({ freshness, frequency, lastDate, nextRelease, today = new Date() }) {
  if (freshness && freshness.level === 'stale') return true;
  const limit = NORMAL_AGE_DAYS[frequency];
  const last = dayNumber(lastDate);
  const now = dayNumber(today);
  if (!limit || last == null || now == null) return false;
  if (now - last <= limit) return false;
  const next = dayNumber(nextRelease);
  return !(next != null && next >= now && next - now <= 14);
}

/** Месяц, за который выйдут следующие месячные данные: следующий после последней точки. */
export function nextPeriodMonth(lastDate) {
  const last = dayNumber(lastDate);
  if (last == null) return null;
  const d = new Date(last * DAY_MS);
  return new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth() + 1, 1));
}

/**
 * Какую фразу ставить в строку. Возвращает { key, params } для словаря или null (сказать нечего).
 * key — ключ i18n без префикса `acq.when.`.
 */
export function lineCopy({ code, frequency, lastDate, nextRelease, nextEstimated = false, delayed = false }) {
  if (delayed) return { key: 'delayed', params: {} };
  const topic = PAGE_TOPIC[code];
  // Ставка ЦБ хранится по дням, но меняется только на заседаниях: важна дата решения, а не «каждый день».
  if (code === 'key-rate') return nextRelease ? { key: 'keyrate', params: { date: nextRelease } } : null;
  if (frequency === 'daily') return { key: 'daily', params: {} };
  if (nextRelease) {
    if (topic === 'inflation') {
      const month = nextPeriodMonth(lastDate);
      if (month) return { key: nextEstimated ? 'cpiApprox' : 'cpi', params: { month, date: nextRelease } };
    }
    return { key: nextEstimated ? 'nextApprox' : 'next', params: { date: nextRelease } };
  }
  // Недельные цены топлива Росстат публикует по средам; события в календаре у них нет.
  if (frequency === 'weekly' && String(code).startsWith('fuel-')) return { key: 'fuelWeekly', params: {} };
  return null;
}

export function botStartUrl(bot, topic) {
  if (!bot || !topic) return null;
  return `https://t.me/${encodeURIComponent(bot)}?start=site_${encodeURIComponent(topic)}`;
}

let _config = null;
let _inflight = null;

export function loadSiteAcqConfig() {
  if (_config) return Promise.resolve(_config);
  if (!_inflight) {
    _inflight = (async () => {
      try {
        const response = await fetch(CONFIG_URL, { headers: { Accept: 'application/json' } });
        const raw = response.ok ? await response.json() : null;
        _config = raw && typeof raw === 'object'
          ? {
            line: raw.line === true,
            topics: Array.isArray(raw.topics) ? raw.topics.filter((t) => typeof t === 'string') : [],
            bot: typeof raw.bot === 'string' ? raw.bot : '',
            first_screen: raw.first_screen === true,
            // Темы почтового способа: не зависят от бота и Telegram-части (почта наравне, решение совета).
            mail_topics: Array.isArray(raw.mail_topics) ? raw.mail_topics.filter((t) => typeof t === 'string') : [],
          }
          : OFF;
      } catch {
        _config = OFF;
      }
      return _config;
    })();
  }
  return _inflight;
}

/** Только для тестов. */
export function resetSiteAcqForTests() {
  _config = null;
  _inflight = null;
}

export function useSiteAcqConfig() {
  const [config, setConfig] = useState(_config || OFF);
  useEffect(() => {
    let alive = true;
    loadSiteAcqConfig().then((c) => { if (alive) setConfig(c); });
    return () => { alive = false; };
  }, []);
  return config;
}
