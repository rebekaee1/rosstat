// Строки подсказки графика «Сравнение»: по одной на ряд, только с человеческим именем.
// Recharts кладёт в payload и заливку под линией, и белый блик-штрих: у них нет имени, подпись берётся из ключа данных
// («v0», «v1»), а строки идут дважды. Здесь остаются только именованные линии рядов, по одной на ключ.

/**
 * @param {Array} payload элементы подсказки Recharts
 * @param {Object<string,string>} [colors] ключ ряда → цвет; если задан, чужие ключи отбрасываются
 */
export function compareTooltipRows(payload, colors = null) {
  if (!Array.isArray(payload)) return [];
  const seen = new Set();
  const rows = [];
  for (const item of payload) {
    if (!item || item.value == null || Number.isNaN(Number(item.value))) continue;
    const key = item.dataKey;
    if (colors && !Object.prototype.hasOwnProperty.call(colors, key)) continue;
    if (seen.has(key)) continue;
    const name = typeof item.name === 'string' ? item.name.trim() : '';
    // Имя, совпавшее с ключом данных («v0»), — техническое: это заливка или блик, не линия ряда.
    if (!name || name === String(key)) continue;
    seen.add(key);
    rows.push(item);
  }
  return rows;
}
