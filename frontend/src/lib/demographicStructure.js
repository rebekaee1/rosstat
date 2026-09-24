export const AGE_GROUP_CODES = ['pop-under-working-age', 'working-age-population', 'pop-over-working-age'];

export function demographicTotal(row) {
  const values = AGE_GROUP_CODES.map((code) => row?.[code]);
  if (values.some((value) => typeof value !== 'number' || !Number.isFinite(value) || value < 0)) return null;
  const total = values.reduce((sum, value) => sum + value, 0);
  return total > 0 ? total : null;
}

export function latestCompleteStructure(series) {
  return [...series].reverse().find((row) => demographicTotal(row) !== null) || null;
}

export function demographicChartRows(series, percent = false) {
  return series.map((row) => {
    const total = demographicTotal(row);
    return { year: row.year, ...Object.fromEntries(AGE_GROUP_CODES.map((code) => [code,
      total === null ? null : percent ? row[code] / total * 100 : row[code],
    ])) };
  });
}
