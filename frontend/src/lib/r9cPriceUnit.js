// R9-C: единица цены с «за кг / за шт / за л»: общий unitLabel сводит «рублей за кг» к голому «₽»,
// и пекарь не видит, за что цена. Для неценовых единиц возвращает пустую строку (работает общий unitLabel).
export function priceUnitLabel(unit) {
  const raw = String(unit || '').trim();
  const ru = raw.match(/^рубл\S*\s+(за\s+.+)$/i);
  if (ru) return `₽ ${ru[1]}`;
  const en = raw.match(/^rub(?:le)?s?\s+(per\s+.+)$/i);
  if (en) return `₽ ${en[1]}`;
  return '';
}
