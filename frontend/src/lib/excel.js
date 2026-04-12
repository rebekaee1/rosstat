import { trackFile } from './track';

export async function downloadExcel(chartData, mode, indicatorCode, range, meta = {}) {
  const XLSX = await import('xlsx');

  const actuals = chartData.filter(d => d.actual != null);
  const forecasts = chartData.filter(d => d.forecast != null && d.actual == null);

  const CPI_VALUE_LABELS = {
    cpi: 'ИПЦ (изм. к пред. мес., %)',
    quarterly: 'ИПЦ квартальный (%)',
    inflation: 'Инфляция 12 мес. (%)',
    annual: 'Годовая инфляция (%)',
    weekly: 'Недельный ИПЦ (изм. к пред. нед., %)',
  };
  const CPI_MODE_LABELS = {
    cpi: 'ипц_помесячно',
    quarterly: 'ипц_квартальный',
    inflation: 'инфляция_12мес',
    annual: 'инфляция_годовая',
    weekly: 'ипц_недельный',
  };
  const genericLabel = meta.name
    ? `${meta.name}${meta.unit ? ` (${meta.unit})` : ''}`
    : 'Значение';
  const valueLabel = CPI_VALUE_LABELS[mode] || genericLabel;

  const factsSheet = actuals.map(d => ({
    'Дата': d.date,
    [valueLabel]: Number(d.actual?.toFixed(4)),
  }));

  const forecastSheet = forecasts.map(d => ({
    'Дата': d.date,
    [`Прогноз ${valueLabel}`]: Number(d.forecast?.toFixed(4)),
  }));

  const wb = XLSX.utils.book_new();

  const ws1 = XLSX.utils.json_to_sheet(factsSheet);
  XLSX.utils.book_append_sheet(wb, ws1, 'Факт');

  if (forecastSheet.length > 0) {
    const ws2 = XLSX.utils.json_to_sheet(forecastSheet);
    XLSX.utils.book_append_sheet(wb, ws2, 'Прогноз');
  }

  const modeLabel = CPI_MODE_LABELS[mode] || mode || 'data';
  const filename = `${indicatorCode}_${modeLabel}_${range}.xlsx`;
  XLSX.writeFile(wb, filename);
  trackFile(filename);
}

export function downloadCSV(chartData, mode, indicatorCode, range, meta = {}) {
  const rows = chartData.filter(d => d.actual != null || d.forecast != null);
  if (!rows.length) return;

  const header = ['Дата', meta.name || 'Значение', 'Тип'];
  const csvRows = [header.join(';')];

  for (const d of rows) {
    const val = d.actual != null ? d.actual : d.forecast;
    const type = d.actual != null ? 'факт' : 'прогноз';
    csvRows.push([d.date, val?.toFixed(4) ?? '', type].join(';'));
  }

  const bom = '\uFEFF';
  const blob = new Blob([bom + csvRows.join('\n')], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  const filename = `${indicatorCode}_${mode || 'data'}_${range}.csv`;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
  trackFile(filename);
}
