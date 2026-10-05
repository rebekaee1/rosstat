/**
 * Подпись над графиком показателя страны: что именно нарисовано («Значения, млрд $», «Изменение за год, %»).
 * Название показателя здесь не повторяется: оно уже стоит в заголовке страницы.
 */
const MODE_TITLE_KEY = {
  level: 'w2.mode.level',
  step: 'w2.mode.step',
  yoy: 'w2.mode.yoy',
  yoyabs: 'w2.mode.yoy',
  index: 'w2.mode.index',
};

export function chartCaption(modeMeta, unit, t) {
  const label = t(MODE_TITLE_KEY[modeMeta?.type] || MODE_TITLE_KEY.level);
  return unit ? `${label}, ${unit}` : label;
}
