// Выгрузка сетки «колонки × строки» (сравнение, диапазон истории) через `POST /export/grid` (бэкенд круга 11).
// Файл собирает сервер: числа в Excel настоящие, в CSV русский формат. Гость получает отказ `download_limit`
// (как у `/export/table`): тогда открывается окно входа, а не файл.
import api from './api';
import { track, trackFile, events } from './track';
import { trackBusy } from './chunkRecovery';

const MAX_COLUMNS = 60;
const FORBIDDEN_KEYS = new Set(['lower', 'upper']);

/** Имя файла без пробелов и служебных знаков, не длиннее 80 знаков. */
export function safeFilename(base, ext) {
  const stem = String(base || 'data').replace(/[^\p{L}\p{N}_-]+/gu, '_').replace(/_+/g, '_').replace(/^_|_$/g, '').slice(0, 80) || 'data';
  return `${stem}.${ext}`;
}

/**
 * Тело запроса: только допустимые ключи колонок (в прогнозах диапазонов нет, и `lower`/`upper` сервер отклоняет).
 * @param {{format:'csv'|'xlsx', filename:string, title?:string, columns:Array<{key:string,label:string,unit?:string}>, rows:Array<object>, meta?:object, history?:object}} spec
 */
export function buildGridPayload(spec) {
  const columns = (spec.columns || [])
    .filter((c) => c && c.key && !FORBIDDEN_KEYS.has(String(c.key).toLowerCase()))
    .slice(0, MAX_COLUMNS)
    .map((c) => ({ key: String(c.key), label: String(c.label ?? c.key), ...(c.unit ? { unit: String(c.unit) } : {}) }));
  const keys = columns.map((c) => c.key);
  const rows = (spec.rows || []).map((row) => {
    const out = {};
    keys.forEach((key) => {
      const v = row?.[key];
      out[key] = v == null || (typeof v === 'number' && !Number.isFinite(v)) ? null : v;
    });
    return out;
  });
  const payload = {
    format: spec.format, filename: spec.filename, columns, rows,
  };
  if (spec.title) payload.title = String(spec.title).slice(0, 200);
  if (spec.meta) payload.meta = spec.meta;
  if (spec.history) payload.history = spec.history;
  return payload;
}

/** Запрос файла. При отказе по лимиту бросает ошибку с `code = 'download_limit'`. */
export async function requestGrid(spec) {
  try {
    const res = await api.post('/export/grid', buildGridPayload(spec), { responseType: 'blob' });
    const raw = res.headers?.['x-download-remaining'];
    const remaining = raw == null || raw === '' ? null : Number(raw);
    return { blob: res.data, remaining };
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

/**
 * Скачивание файла сетки. Возвращает true, если файл сохранён; false при лимите гостя (окно входа открыто).
 * В аналитику уходит только тип выгрузки и источник, без названий рядов.
 */
async function downloadGridImpl(spec, { source = 'grid' } = {}) {
  try {
    const { blob, remaining } = await requestGrid(spec);
    saveBlob(blob, spec.filename);
    window.dispatchEvent(new CustomEvent('fe:download-done', { detail: { remaining } }));
    track(spec.format === 'csv' ? events.DOWNLOAD_CSV : events.DOWNLOAD_EXCEL, { source });
    return true;
  } catch (err) {
    if (err?.code === 'download_limit') {
      track(events.DOWNLOAD_LIMIT_HIT, { source });
      window.dispatchEvent(new CustomEvent('fe:download-limit'));
      return false;
    }
    throw err;
  }
}

export const downloadGrid = (...args) => trackBusy(downloadGridImpl(...args));
