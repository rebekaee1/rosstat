/**
 * Заголовок графика на странице показателя: «ВВП, США: за 10 лет, млрд $».
 * Название показателя берём коротким (см. viewModeShortLabels), период и единицу говорим словами.
 * Если название всё равно длинное, возвращаем null: вызывающий оставляет прежнюю подпись «Значения, млрд $».
 */
import { shortVariantLabel } from './viewModeShortLabels';

const MAX_SUBJECT = 46;

/**
 * @param {object} p
 * @param {string} p.name Название показателя (как в заголовке страницы).
 * @param {string} [p.place] Страна или регион.
 * @param {string} [p.modeLabel] Подпись режима, если это не «Значения» («Изменение за год»).
 * @param {string} [p.rangeText] «за 10 лет» (пусто, если окно подвинули вручную).
 * @param {string} [p.unit] Единица («млрд $», «%»).
 * @param {string} [p.locale]
 * @returns {string|null}
 */
export function buildChartTitle({
  name, place = '', modeLabel = '', rangeText = '', unit = '', locale = 'ru',
}) {
  const subject = shortVariantLabel(name, locale);
  if (!subject || subject.length > MAX_SUBJECT) return null;
  const head = [subject, place].filter(Boolean).join(', ');
  const tail = [modeLabel || rangeText, unit].filter(Boolean).join(', ');
  return tail ? `${head}: ${tail}` : head;
}
