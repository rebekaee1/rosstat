/**
 * Круг 9 (P7): недавние запросы поиска. Хранятся только в этом браузере (удобство одного человека, не данные):
 * без регистрации, без отправки на сервер. Любая ошибка хранилища (приватное окно, запрет) просто даёт пустой список.
 */
const STORAGE_KEY = 'fe_recent_queries';
/** Круг 11 (D): хранится 8 запросов, в окне поиска видны первые 6 (раньше 4: люди не замечали, что список вообще есть). */
export const RECENT_LIMIT = 8;
export const RECENT_SHOWN = 6;
/** Сколько недавних страниц («Вы смотрели») показывает окно поиска под запросами. */
export const RECENT_PAGES_SHOWN = 4;

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

/** Стереть недавние запросы (кнопка «Очистить» в окне поиска). */
export function clearRecentQueries() {
  try {
    window.localStorage.removeItem(STORAGE_KEY);
  } catch {
    /* нечего очищать */
  }
}
