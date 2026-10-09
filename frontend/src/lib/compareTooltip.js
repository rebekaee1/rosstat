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

/**
 * Что значит число в режиме «рост от старта» (старт = 100), одной короткой фразой для подсказки.
 * От 150 и выше: «в 1,9 раза больше старта»; от 100 до 150 и ниже 100: изменение в процентах («+19 %», «−12 %»);
 * от 2/3 и ниже: «в 1,5 раза меньше старта». Возвращает данные для текста, а не готовую строку: слова лежат в i18n.
 * @returns {{kind:'times'|'less'|'pct'|'same', ratio?:string, plural?:string, pct?:string}}
 */
export function indexNote(value, locale = 'ru') {
  const v = Number(value);
  if (!Number.isFinite(v) || v <= 0) return { kind: 'same' };
  const lang = locale === 'en' ? 'en-US' : 'ru-RU';
  const formatRatio = (raw) => {
    const rounded = raw >= 10 ? Math.round(raw) : Math.round(raw * 10) / 10;
    let plural = 'other';
    try {
      plural = new Intl.PluralRules(locale === 'en' ? 'en' : 'ru').select(rounded);
    } catch { /* без правил множественного числа */ }
    return { ratio: new Intl.NumberFormat(lang, { maximumFractionDigits: raw >= 10 ? 0 : 1 }).format(rounded), plural };
  };
  if (v >= 150) return { kind: 'times', ...formatRatio(v / 100) };
  if (v <= 66.7) return { kind: 'less', ...formatRatio(100 / v) };
  const pct = v - 100;
  if (Math.abs(pct) < 0.5) return { kind: 'same' };
  const body = new Intl.NumberFormat(lang, { maximumFractionDigits: 0 }).format(Math.abs(pct));
  return { kind: 'pct', pct: `${pct > 0 ? '+' : '\u2212'}${body}\u00A0%` };
}
