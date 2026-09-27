/**
 * Мировые рыночные ряды общего каталога: валюты имеют путь `/currencies`,
 * остальные рыночные ряды пока живут под `/russia/indicator/...`.
 * В хлебных крошках они не считаются российской статистикой.
 * Зеркало backend `app/data/global_market_indicators.py`.
 */
export const GLOBAL_MARKET_INDICATOR_BASES = Object.freeze([
  'btc-usd',
  'eth-usd',
  'sol-usd',
  'usd-index',
  'ust-10y',
  'eur-usd',
  'gbp-usd',
  'usd-cny',
  'brent',
  'natural-gas',
  'copper',
  'silver',
  'wheat',
  'soybean',
  'coal',
]);

export function isGlobalMarketIndicator(code) {
  if (!code) return false;
  if (GLOBAL_MARKET_INDICATOR_BASES.includes(code)) return true;
  return GLOBAL_MARKET_INDICATOR_BASES.some((base) => code.startsWith(`${base}-`));
}
