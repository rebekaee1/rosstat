/**
 * Выгрузка таблицы-сетки (рейтинг стран, сравнение регионов) через `POST /export/grid` (круг 11, зона A):
 * общая рамка CSV / Excel, только точечные значения (поля диапазона сервер отклоняет).
 *
 * Запрос идёт через общую `exportGrid` из `lib/api.js`; здесь сохранение файла и имена. Лимит гостевых выгрузок тот же, что у
 * `/export/table`: при 403 `download_limit` вызывающий показывает окно регистрации (событие `fe:download-limit`).
 */
import { exportGrid } from './api';
import { trackFile } from './track';

function saveBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  setTimeout(() => URL.revokeObjectURL(url), 100);
  trackFile(filename);
}

/** Ключ колонки для сервера: латиница, цифры и `_.:-` (до 64 знаков). */
export function gridColumnKey(text, fallback = 'col') {
  const key = String(text || '').replace(/[^A-Za-z0-9_.:-]+/g, '_').replace(/^_+|_+$/g, '').slice(0, 64);
  return key || fallback;
}

/** Безопасное имя файла: без слэшей и пробелов, не длиннее 120 знаков. */
export function gridFilename(base, format) {
  const clean = String(base || 'table')
    .replace(/[\\/:*?"<>|\s]+/g, '_')
    .replace(/_+/g, '_')
    .replace(/^_+|_+$/g, '')
    .slice(0, 120) || 'table';
  return `${clean}.${format}`;
}

/**
 * @param {{ format: 'csv'|'xlsx', filename: string, title?: string,
 *   columns: Array<{key: string, label: string, unit?: string}>,
 *   rows: Array<Record<string, number|string|null>>, meta?: object, history?: object }} payload
 * @returns {Promise<{ remaining: number|null }>} бросает ошибку с `code === 'download_limit'`, когда гостевой лимит исчерпан
 */
export async function downloadGrid(payload) {
  // Сам вызов `POST /export/grid` и разбор отказа по лимиту — общая функция `exportGrid` из `lib/api.js` (круг 11, интеграция).
  const { blob, remaining } = await exportGrid(payload);
  saveBlob(blob, payload.filename);
  if (typeof window !== 'undefined') {
    window.dispatchEvent(new CustomEvent('fe:download-done', { detail: { remaining } }));
  }
  return { remaining };
}
