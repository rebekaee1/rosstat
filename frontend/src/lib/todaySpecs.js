/** Синхронно с backend/app/services/seo_today.py::TODAY_SPECS */
export const TODAY_SPECS = {
  'usd-rub': { code: 'usd-rub', query: 'Курс доллара', series: 'usd-rub' },
  'eur-rub': { code: 'eur-rub', query: 'Курс евро', series: 'eur-rub' },
  'cny-rub': { code: 'cny-rub', query: 'Курс юаня', series: 'cny-rub' },
  'key-rate': { code: 'key-rate', query: 'Ключевая ставка ЦБ', series: 'key-rate' },
  'cpi': { code: 'cpi', query: 'Инфляция', series: 'cpi-yoy' },
  'gold-price': { code: 'gold-price', query: 'Цена золота', series: 'gold-price' },
  'fuel-ai92': { code: 'fuel-ai92', query: 'Цена бензина АИ-92', series: 'fuel-ai92' },
  'fuel-ai95': { code: 'fuel-ai95', query: 'Цена бензина АИ-95', series: 'fuel-ai95' },
  'fuel-diesel': { code: 'fuel-diesel', query: 'Цена дизельного топлива', series: 'fuel-diesel' },
  'imoex': { code: 'imoex', query: 'Индекс МосБиржи', series: 'imoex' },
};

export const TODAY_CODES = Object.keys(TODAY_SPECS);

export function getTodaySpec(code) {
  return TODAY_SPECS[code] || null;
}

export function todaySeriesCode(code) {
  const spec = getTodaySpec(code);
  return spec?.series || code;
}
