// Доля региона в России для абсолютных показателей (правка 18, круг «Туризм» 20.11.2026).

/**
 * Единица складывается по регионам (тысячи человек, миллионы рублей, штуки): только для такой «доля в России» имеет смысл.
 * Проценты, годы, «на 1000», средние и цены за единицу не складываются.
 */
export function isAdditiveUnit(unit) {
  const u = String(unit || '').toLowerCase();
  if (!u) return false;
  if (/%|процент|percent|п\.\s?п|индекс|index|(?<![а-яё])лет(?![а-яё])|years?|(?<![а-яё])на\s|\bper\b|средн|average|коэффициент|ratio|(?<![а-яё])за\s/.test(u)) return false;
  return /(тыс|млн|млрд|миллион|миллиард|человек|чел\.|единиц|штук|(?<![а-яё])шт(?![а-яё])|мест|койко|номер|тонн|гектар|(?<![а-яё])га(?![а-яё])|thousand|million|billion|people|persons|units|tonnes?|pieces|beds|rooms)/.test(u);
}

/** Доля региона в России (%) или null: нет значения РФ, ноль или регион больше страны. */
export function shareOfRussia(value, russiaValue) {
  if (value == null || russiaValue == null) return null;
  const v = Number(value);
  const r = Number(russiaValue);
  if (!Number.isFinite(v) || !Number.isFinite(r) || r <= 0 || v < 0 || v > r * 1.001) return null;
  return (v / r) * 100;
}

