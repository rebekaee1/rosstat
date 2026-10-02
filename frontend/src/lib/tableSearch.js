import { formatDate, formatValue, formatValueWithUnit } from './format';

/** Literal search inside already loaded observations; never searches a catalogue. */
export function normalizeTableSearch(value) {
  return String(value ?? '').normalize('NFKC').toLowerCase().replace(/ё/g, 'е')
    .replace(/(\d),(?=\d)/g, '$1.').replace(/\s+/g, ' ').trim();
}

export function tableRowMatches(row, query, { dateFormat = 'full', unit = '%', valueDigits } = {}) {
  const needle = normalizeTableSearch(query);
  if (!needle) return true;
  const date = new Date(row.date);
  const quarter = dateFormat === 'quarterly' && !Number.isNaN(date.getTime())
    ? `${date.getUTCFullYear()}-q${Math.ceil((date.getUTCMonth() + 1) / 3)}` : '';
  const dateText = normalizeTableSearch(`${formatDate(row.date, dateFormat)} ${row.date} ${quarter}`);
  const valueText = normalizeTableSearch([
    row.value ?? '', formatValue(row.value, valueDigits), formatValueWithUnit(row.value, unit, valueDigits),
  ].join(' '));
  // A pasted displayed number may contain spaces between thousands groups.
  const compactNeedle = needle.replace(/(?<=\d) (?=\d{3}(?:\D|$))/g, '');
  const compactValue = valueText.replace(/(?<=\d) (?=\d{3}(?:\D|$))/g, '');
  return dateText.includes(needle) || valueText.includes(needle) || compactValue.includes(compactNeedle);
}
