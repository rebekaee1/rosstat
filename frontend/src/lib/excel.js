import { trackFile, track, events } from './track';
import { exportTable } from './api';
import { rememberExport, clearPendingExport } from './authReturn';

// Генерация файла перенесена на бэкенд (гейт лимита + минус ~430 КБ xlsx из
// бандла). Здесь — только подготовка точек/подписи и сохранение ответа-blob.

const CPI_VALUE_LABELS = {
  cpi: 'ИПЦ (изм. к пред. мес., %)',
  quarterly: 'ИПЦ квартальный (%)',
  inflation: 'Инфляция 12 мес. (%)',
  annual: 'Годовая инфляция (%)',
  weekly: 'Недельный ИПЦ (изм. к пред. нед., %)',
  index: 'Накопленный индекс ИПЦ (2000=100)',
};
const CPI_MODE_LABELS = {
  cpi: 'ипц_помесячно',
  quarterly: 'ипц_квартальный',
  inflation: 'инфляция_12мес',
  annual: 'инфляция_годовая',
  weekly: 'ипц_недельный',
  index: 'индекс_накопленный',
};

function valueLabel(mode, meta) {
  const generic = meta.name
    ? `${meta.name}${meta.unit ? ` (${meta.unit})` : ''}`
    : 'Значение';
  return CPI_VALUE_LABELS[mode] || generic;
}

function toPoints(chartData) {
  return chartData
    .filter((d) => d.actual != null || d.forecast != null)
    .map((d) => ({
      date: d.date,
      actual: d.actual != null ? d.actual : null,
      forecast: d.forecast != null && d.actual == null ? d.forecast : null,
    }));
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

// После успешной выгрузки сообщаем UI остаток гостевого лимита (для кнопок).
function emitDownloaded(remaining) {
  window.dispatchEvent(new CustomEvent('fe:download-done', { detail: { remaining } }));
}

// Лимит гостевых скачиваний: глобальное событие подхватывает модалка регистрации.
function handleLimit(err, indicatorCode, payload) {
  if (err?.code === 'download_limit') {
    rememberExport(payload);
    track(events.DOWNLOAD_LIMIT_HIT, { indicator: indicatorCode });
    window.dispatchEvent(new CustomEvent('fe:download-limit'));
    return true;
  }
  return false;
}

export async function downloadExcel(chartData, mode, indicatorCode, range, meta = {}) {
  const modeLabel = CPI_MODE_LABELS[mode] || mode || 'data';
  const filename = `${indicatorCode}_${modeLabel}_${range}.xlsx`;
  const payload = {
      format: 'xlsx',
      filename,
      valueLabel: valueLabel(mode, meta),
      points: toPoints(chartData),
      meta: { indicator_name: meta.name, unit: meta.unit, source: meta.source,
        source_url: meta.source_url, frequency: meta.frequency, provenance: meta.provenance },
  };
  try {
    const { blob, remaining } = await exportTable(payload);
    saveBlob(blob, filename);
    emitDownloaded(remaining);
    return true;
  } catch (err) {
    if (handleLimit(err, indicatorCode, payload)) return false;
    throw err;
  }
}

export async function downloadCSV(chartData, mode, indicatorCode, range, meta = {}) {
  const filename = `${indicatorCode}_${mode || 'data'}_${range}.csv`;
  const payload = {
      format: 'csv',
      filename,
      valueLabel: meta.name || 'Значение',
      points: toPoints(chartData),
      meta: { indicator_name: meta.name, unit: meta.unit, source: meta.source,
        source_url: meta.source_url, frequency: meta.frequency, provenance: meta.provenance },
  };
  try {
    const { blob, remaining } = await exportTable(payload);
    saveBlob(blob, filename);
    emitDownloaded(remaining);
    return true;
  } catch (err) {
    if (handleLimit(err, indicatorCode, payload)) return false;
    throw err;
  }
}

// Explicit user click after auth; replay the exact selected data, not a new default view.
export async function resumeExport(payload) {
  const { blob, remaining } = await exportTable(payload);
  saveBlob(blob, payload.filename);
  emitDownloaded(remaining);
  clearPendingExport();
  track(payload.format === 'csv' ? events.DOWNLOAD_CSV : events.DOWNLOAD_EXCEL, { resumed_after_auth: true });
}
