/**
 * Короткая единица у числа региона в выдаче поиска (правка 8, 20.11.2026).
 * Раньше любая «рубли» превращалась в «₽», и «1 757 млн руб.» читалось как «1 757 ₽». Теперь множитель ряда
 * («тыс.», «млн», «млрд», «трлн») сохраняется: «1 757 млн ₽». Единица берётся только из строки, данные не меняются.
 */

const SCALE_RU = [
  [/трлн|триллион/i, 'трлн'],
  [/млрд|миллиард/i, 'млрд'],
  [/млн|миллион/i, 'млн'],
  [/тыс/i, 'тыс.'],
];
const SCALE_EN = [
  [/\b(?:tn|trillion)\b/i, 'tn'],
  [/\b(?:bn|billion)\b/i, 'bn'],
  [/\b(?:mn|million)\b/i, 'mn'],
  [/\b(?:thousand|ths?)\b/i, 'k'],
];

/** «₽», «млн ₽», «%»; пустая строка — единицу коротко не записать. */
export function regionRubleUnit(rawUnit, locale = 'ru') {
  const unit = String(rawUnit || '');
  if (!/руб|₽|rub/i.test(unit)) return '';
  // Рубли за что-то («руб. за кг») — цена, множителя нет, как и в «руб./кв. м».
  const scales = locale === 'en' ? [...SCALE_EN, ...SCALE_RU] : [...SCALE_RU, ...SCALE_EN];
  const scale = scales.find(([pattern]) => pattern.test(unit));
  return scale ? `${scale[1]}\u00A0₽` : '₽';
}
