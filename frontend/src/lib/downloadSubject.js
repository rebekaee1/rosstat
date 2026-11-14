// Содержание скачивания для аналитики (14.11.2026, отчёт «Скачивания» служебного бота):
// каждое событие скачивания и упора в лимит несёт код показателя и, где есть, страну и регион.
// Прежний параметр `indicator` (в т.ч. с префиксом вида `region:` / `regions-leaders:`) остаётся как был —
// его читают Пульс и BI; новые поля только добавляются. Адрес страницы на сервере — запасной источник.

const MAX_CODES = 8;

/**
 * @param {{ code?: string, country?: string, region?: string, codes?: string[], regions?: string[] }} subject
 * @returns {Record<string, string>} только непустые поля; Россия как страна не пишется (она по умолчанию)
 */
export function subjectParams({ code, country, region, codes, regions } = {}) {
  const out = {};
  if (code) out.code = String(code);
  if (country && country !== 'russia') out.country = String(country);
  if (region) out.region = String(region);
  const list = (codes || []).filter(Boolean).slice(0, MAX_CODES);
  if (list.length) out.codes = list.join(',');
  const regs = (regions || []).filter(Boolean).slice(0, MAX_CODES);
  if (regs.length) out.regions = regs.join(',');
  return out;
}
