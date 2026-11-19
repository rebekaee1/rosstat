import { trackFile, track, events } from './track';
import { exportTable } from './api';
import { rememberExport, clearPendingExport } from './authReturn';
import { subjectParams } from './downloadSubject';
import { trackBusy } from './chunkRecovery';

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

// После успешной выгрузки сообщаем UI остаток гостевого лимита (для кнопок) и что скачано:
// код ряда и страна — для предложения «присылать новые значения на почту» (AfterDownloadOffer).
function emitDownloaded(remaining, subject) {
  const detail = { remaining };
  if (subject?.code) {
    detail.code = subject.code;
    detail.country = subject.country || null;
  }
  window.dispatchEvent(new CustomEvent('fe:download-done', { detail }));
}

// Лимит гостевых скачиваний: глобальное событие подхватывает модалка регистрации.
function handleLimit(err, indicatorCode, payload) {
  if (err?.code === 'download_limit') {
    rememberExport(payload);
    track(events.DOWNLOAD_LIMIT_HIT, { indicator: indicatorCode, ...subjectParams(payload.subject) });
    window.dispatchEvent(new CustomEvent('fe:download-limit'));
    return true;
  }
  return false;
}

async function downloadExcelImpl(chartData, mode, indicatorCode, range, meta = {}) {
  const modeLabel = CPI_MODE_LABELS[mode] || mode || 'data';
  const filename = `${indicatorCode}_${modeLabel}_${range}.xlsx`;
  const payload = {
      format: 'xlsx',
      filename,
      valueLabel: valueLabel(mode, meta),
      points: toPoints(chartData),
      meta: { indicator_name: meta.name, unit: meta.unit, source: meta.source,
        source_url: meta.source_url, frequency: meta.frequency, provenance: meta.provenance },
      // Содержание для аналитики (не уходит на сервер: exportTable берёт только свои поля).
      subject: { code: indicatorCode, country: meta.country },
  };
  try {
    const { blob, remaining } = await exportTable(payload);
    saveBlob(blob, filename);
    emitDownloaded(remaining, payload.subject);
    return true;
  } catch (err) {
    if (handleLimit(err, indicatorCode, payload)) return false;
    throw err;
  }
}

async function downloadCSVImpl(chartData, mode, indicatorCode, range, meta = {}) {
  const filename = `${indicatorCode}_${mode || 'data'}_${range}.csv`;
  const payload = {
      format: 'csv',
      filename,
      valueLabel: meta.name || 'Значение',
      points: toPoints(chartData),
      meta: { indicator_name: meta.name, unit: meta.unit, source: meta.source,
        source_url: meta.source_url, frequency: meta.frequency, provenance: meta.provenance },
      // Содержание для аналитики (не уходит на сервер: exportTable берёт только свои поля).
      subject: { code: indicatorCode, country: meta.country },
  };
  try {
    const { blob, remaining } = await exportTable(payload);
    saveBlob(blob, filename);
    emitDownloaded(remaining, payload.subject);
    return true;
  } catch (err) {
    if (handleLimit(err, indicatorCode, payload)) return false;
    throw err;
  }
}

// Explicit user click after auth; replay the exact selected data, not a new default view.
async function resumeExportImpl(payload) {
  const { blob, remaining } = await exportTable(payload);
  saveBlob(blob, payload.filename);
  emitDownloaded(remaining, payload.subject);
  clearPendingExport();
  track(payload.format === 'csv' ? events.DOWNLOAD_CSV : events.DOWNLOAD_EXCEL, {
    resumed_after_auth: true,
    ...(payload.subject?.code ? { indicator: payload.subject.code } : {}),
    ...subjectParams(payload.subject),
  });
}

// Идущая выгрузка не должна обрываться автоперезагрузкой после релиза (chunkRecovery).
export const downloadExcel = (...args) => trackBusy(downloadExcelImpl(...args));
export const downloadCSV = (...args) => trackBusy(downloadCSVImpl(...args));
export const resumeExport = (...args) => trackBusy(resumeExportImpl(...args));
