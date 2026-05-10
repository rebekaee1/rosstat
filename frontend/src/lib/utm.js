/**
 * UTM-разметка исходящих и share-ссылок.
 *
 * Фронт сам не «генерирует» рекламные кампании — настоящий UTM-источник Direct
 * проставляется в кабинете Яндекс.Директ (см. `docs/utm_taxonomy.md`).
 * Зато все внутренние share / copy-link / outbound-кнопки на сайте обязаны
 * проставлять собственную UTM-разметку, чтобы трафик, который пользователь
 * отправил из своего поста / Telegram / email, в Метрике становился отдельным
 * сегментом, а не «Direct».
 *
 * Канонические значения utm_source:
 *   - 'self' — share-кнопки внутри fe (Calculator, Compare, IndicatorPage)
 *   - 'embed' — пользовательский iframe-виджет (Embed Builder)
 *   - 'newsletter' — рассылка (когда появится)
 *   - 'social-{platform}' — конкретные posts (tg/vk/dzen/youtube)
 *
 * Канонические значения utm_medium:
 *   - 'share-link' — ручной share через clipboard / native share
 *   - 'embed' — iframe widget
 *   - 'cta' — кнопка-призыв (например, «Сравнить с другим»)
 *   - 'context' — контекстная ссылка внутри текстов
 *
 * Кампании (utm_campaign): человекочитаемое имя без пробелов, kebab-case.
 *   Примеры: 'calc-share', 'compare-share', 'indicator-share',
 *   'forecast-cta', 'calendar-event'.
 */

const TRACKING_PARAMS = ['utm_source', 'utm_medium', 'utm_campaign', 'utm_content', 'utm_term'];

function isAbsoluteUrl(value) {
  return /^https?:\/\//i.test(value);
}

/**
 * Собирает URL с UTM-параметрами. Любые уже присутствующие utm_* в исходном
 * URL перезаписываются переданными — это сознательно: вызывающий код всегда
 * знает текущий контекст лучше, чем «случайные» query-параметры.
 *
 * @param {string} url - абсолютный или относительный URL
 * @param {object} utm
 * @param {string} utm.source - utm_source (обязателен)
 * @param {string} utm.medium - utm_medium (обязателен)
 * @param {string} utm.campaign - utm_campaign (обязателен)
 * @param {string} [utm.content] - utm_content (опц.)
 * @param {string} [utm.term] - utm_term (опц.)
 * @returns {string} URL с UTM
 */
export function buildShareUrl(url, { source, medium, campaign, content, term }) {
  if (!source || !medium || !campaign) {
    throw new Error('buildShareUrl: source/medium/campaign required');
  }
  const base = isAbsoluteUrl(url)
    ? new URL(url)
    : new URL(url, typeof window !== 'undefined' ? window.location.origin : 'https://forecasteconomy.com');

  for (const key of TRACKING_PARAMS) base.searchParams.delete(key);

  base.searchParams.set('utm_source', source);
  base.searchParams.set('utm_medium', medium);
  base.searchParams.set('utm_campaign', campaign);
  if (content) base.searchParams.set('utm_content', content);
  if (term) base.searchParams.set('utm_term', term);

  return base.toString();
}

/**
 * Возвращает абсолютный URL текущей страницы с UTM. Вызывается из share-кнопок:
 *   const url = currentShareUrl({ source: 'self', medium: 'share-link', campaign: 'indicator-share' });
 */
export function currentShareUrl(utm) {
  if (typeof window === 'undefined') return '';
  return buildShareUrl(window.location.href, utm);
}
