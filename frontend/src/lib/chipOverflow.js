/**
 * Какие чипы показать сразу: до `limit` штук плюс выбранный (он не прячется), остальные — под «Ещё режимы».
 * Порядок сохраняется. Чистая функция — тестируется отдельно от разметки.
 */
export function splitChipOverflow(items, isActive, limit = 6) {
  if (!Array.isArray(items) || items.length <= limit) return { shown: items || [], hidden: [] };
  const shown = [];
  const hidden = [];
  items.forEach((item, index) => {
    if (index < limit - 1 || isActive(item)) shown.push(item);
    else hidden.push(item);
  });
  return { shown, hidden };
}
