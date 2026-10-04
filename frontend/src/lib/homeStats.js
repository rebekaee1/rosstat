/** Крупное число показателей: 268 003 → { value: 268, unit: 'thousand' } (округляем вниз, чтобы не завышать). */
export function compactIndicatorCount(count) {
  const n = Number(count);
  if (!Number.isFinite(n) || n <= 0) return null;
  if (n >= 1_000_000) return { value: Math.floor(n / 1_000_000), unit: 'million' };
  if (n >= 10_000) return { value: Math.floor(n / 1000), unit: 'thousand' };
  return { value: Math.round(n), unit: null };
}

/** Первый год из подписи периода: «1897–2026» → 1897. */
export function startYear(periodValue) {
  const match = /^\s*(\d{4})/.exec(String(periodValue || ''));
  return match ? Number(match[1]) : null;
}
