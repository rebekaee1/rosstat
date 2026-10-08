/**
 * Круг 9 (P7): недавние запросы поиска. Хранятся только в этом браузере (удобство одного человека, не данные):
 * без регистрации, без отправки на сервер. Любая ошибка хранилища (приватное окно, запрет) просто даёт пустой список.
 */
const STORAGE_KEY = 'fe_recent_queries';
export const RECENT_LIMIT = 4;

export function readRecentQueries() {
  try {
    const parsed = JSON.parse(window.localStorage.getItem(STORAGE_KEY) || '[]');
    return Array.isArray(parsed)
      ? parsed.filter((item) => typeof item === 'string' && item.trim().length >= 2).slice(0, RECENT_LIMIT)
      : [];
  } catch {
    return [];
  }
}

/** Запоминает запрос первым; повтор (без учёта регистра) поднимается наверх, а не дублируется. */
export function rememberQuery(query) {
  const text = String(query || '').trim().slice(0, 80);
  if (text.length < 2) return;
  try {
    const next = [text, ...readRecentQueries().filter((item) => item.toLowerCase() !== text.toLowerCase())].slice(0, RECENT_LIMIT);
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
  } catch {
    /* приватное окно: недавнее просто не запоминается */
  }
}
