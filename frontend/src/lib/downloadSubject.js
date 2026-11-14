// Содержание скачивания для аналитики (14.11.2026, отчёт «Скачивания» служебного бота):
// каждое событие скачивания и упора в лимит несёт код показателя и, где есть, страну и регион.
// Прежний параметр `indicator` (в т.ч. с префиксом вида `region:` / `regions-leaders:`) остаётся как был —
// его читают Пульс и BI; новые поля только добавляются. Адрес страницы на сервере — запасной источник.

const MAX_CODES = 8;
// Приём событий режет строку до 200 знаков (backend/app/services/event_params.py, MAX_STR):
// список собираем целыми кодами в пределах лимита, остаток — числом в `<поле>_more`.
export const MAX_LIST_CHARS = 200;

function joinWhole(values, field, out) {
  const list = (values || []).filter(Boolean).map(String).slice(0, MAX_CODES);
  const kept = [];
  let length = 0;
  for (const value of list) {
    const next = length + (kept.length ? 1 : 0) + value.length;
    if (next > MAX_LIST_CHARS) break;
    kept.push(value);
    length = next;
  }
  if (kept.length) out[field] = kept.join(',');
  const more = (values || []).filter(Boolean).length - kept.length;
  if (more > 0) out[`${field}_more`] = more;
}

/**
 * @param {{ code?: string, country?: string, region?: string, codes?: string[], regions?: string[] }} subject
 * @returns {Record<string, string|number>} только непустые поля; Россия как страна не пишется (она по умолчанию)
 */
export function subjectParams({ code, country, region, codes, regions } = {}) {
  const out = {};
  if (code) out.code = String(code);
  if (country && country !== 'russia') out.country = String(country);
  if (region) out.region = String(region);
  joinWhole(codes, 'codes', out);
  joinWhole(regions, 'regions', out);
  return out;
}
