export async function downloadExcel(chartData, mode, indicatorCode, range) {
  const XLSX = await import('xlsx');

  const actuals = chartData.filter(d => d.actual != null);
  const forecasts = chartData.filter(d => d.forecast != null && d.actual == null);

  const valueLabel = mode === 'cpi' ? 'ИПЦ (изм. к пред. мес., %)' : 'Инфляция 12 мес. (%)';

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

  const modeLabel = mode === 'cpi' ? 'ипц_помесячно' : 'инфляция_12мес';
  const filename = `${indicatorCode}_${modeLabel}_${range}.xlsx`;
  XLSX.writeFile(wb, filename);
}
