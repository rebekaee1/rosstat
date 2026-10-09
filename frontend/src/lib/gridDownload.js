/**
 * Выгрузка таблицы-сетки (рейтинг стран, сравнение регионов) через `POST /export/grid` (круг 11, зона A):
 * общая рамка CSV / Excel, только точечные значения (поля диапазона сервер отклоняет).
 *
 * Отдельный файл, а не дополнение `lib/api.js`: этот файл правят и другие зоны круга. Лимит гостевых выгрузок тот же, что у
 * `/export/table`: при 403 `download_limit` вызывающий показывает окно регистрации (событие `fe:download-limit`).
 */
import api from './api';
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
  try {
    const res = await api.post('/export/grid', payload, { responseType: 'blob' });
    saveBlob(res.data, payload.filename);
    const raw = res.headers?.['x-download-remaining'];
    const remaining = raw == null || raw === '' ? null : Number(raw);
    if (typeof window !== 'undefined') {
      window.dispatchEvent(new CustomEvent('fe:download-done', { detail: { remaining } }));
    }
    return { remaining };
  } catch (err) {
    const blob = err?.response?.data;
    if (err?.response?.status === 403 && blob && typeof blob.text === 'function') {
      try {
        const parsed = JSON.parse(await blob.text());
        const detail = parsed?.detail || parsed;
        const e = new Error(detail?.message || 'download_limit');
        e.code = detail?.code || 'download_limit';
        throw e;
      } catch (parseErr) {
        if (parseErr.code) throw parseErr;
      }
    }
    throw err;
  }
}
