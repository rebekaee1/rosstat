export async function downloadExcel(chartData, mode, indicatorCode, range) {
  const XLSX = await import('xlsx');

  const actuals = chartData.filter(d => d.actual != null);
  const forecasts = chartData.filter(d => d.forecast != null && d.actual == null);

  const VALUE_LABELS = {
    cpi: 'ИПЦ (изм. к пред. мес., %)',
    quarterly: 'ИПЦ квартальный (%)',
    inflation: 'Инфляция 12 мес. (%)',
  };
  const MODE_LABELS = {
    cpi: 'ипц_помесячно',
    quarterly: 'ипц_квартальный',
    inflation: 'инфляция_12мес',
  };
  const valueLabel = VALUE_LABELS[mode] || `Значение (${mode})`;

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

  const modeLabel = MODE_LABELS[mode] || mode;
  const filename = `${indicatorCode}_${modeLabel}_${range}.xlsx`;
  XLSX.writeFile(wb, filename);
}
