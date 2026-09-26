/**
 * Ссылки на источники данных в основном SPA.
 *
 * На быстрых SEO-страницах (/seo/…, backend seo_renderer/seo_world) имя
 * ведомства намеренно ведёт на раздел сайта. В SPA ссылка «Источник» ведёт
 * на внешний source_url ряда (Росстат, FRED, Евростат…) в новой вкладке;
 * внутренний переход — только фолбэк, когда URL источника неизвестен.
 */

/** true для абсолютного http(s)-адреса (внешний источник). */
export function isExternalHref(href) {
  return typeof href === 'string' && /^https?:\/\//i.test(href.trim());
}

/** Первый внешний http(s)-адрес из списка кандидатов или null. */
export function pickExternalHref(...candidates) {
  const hit = candidates.find(isExternalHref);
  return hit ? hit.trim() : null;
}
