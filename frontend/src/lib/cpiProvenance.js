/** Annual CPI reconstructed from rounded monthly indices, not the published YoY. */
export function cpiProvenance(code, mode, locale = 'ru') {
  const isAnnualDerived = /^cpi(?:-food|-nonfood|-services)?-yoy$/.test(code || '')
    || (/^cpi(?:-food|-nonfood|-services)?$/.test(code || '') && ['inflation', 'yoy'].includes(mode));
  if (!isAnnualDerived) return null;
  return locale === 'en'
    ? 'Calculated by Forecast Economy from Rosstat monthly indices. May differ from the annual change published by Rosstat because the input indices are rounded.'
    : 'Расчёт Forecast Economy по месячным индексам Росстата. Может отличаться от опубликованного Росстатом годового изменения из-за округления исходных индексов.';
}
