// Общие мелочи интерфейса денежных калькуляторов (/calculator*).

/** Верхняя граница денежного поля: триллион. Выше — почти наверняка опечатка. */
export const MONEY_MAX = 1_000_000_000_000;

/**
 * Стиль появления блока средствами CSS (`.fe-reveal`): начальное состояние задаёт CSS,
 * а не JS после монтирования, поэтому нет вспышки. Суммарная задержка — не более 0,2 с.
 */
export function revealStyle(index = 0) {
  return {
    '--fe-delay': `${Math.min(index * 0.03, 0.2).toFixed(2)}s`,
    '--fe-rise': '16px',
    '--fe-duration': '0.45s',
  };
}

const NON_MONEY_CHARS = /[^\d\s\u00A0\u202F.,]/;

/**
 * Разбор введённой суммы. Возвращает `{ value, error }`:
 *  - error 'chars' — в строке есть буквы или символы кроме цифр, пробелов и разделителей;
 *  - error 'empty' — пусто или ноль (расчёт без суммы невозможен; при allowZero ноль допустим);
 *  - error 'max'   — больше MONEY_MAX;
 *  - иначе error null, value — целое число рублей (копейки округляются).
 * При ошибке `value` — null: вызывающий код оставляет прошлое корректное значение
 * вместо молчаливого сброса в ноль.
 */
export function parseMoneyInput(raw, { max = MONEY_MAX, allowZero = false } = {}) {
  const text = String(raw ?? '').trim();
  if (!text) return allowZero ? { value: 0, error: null } : { value: null, error: 'empty' };
  if (NON_MONEY_CHARS.test(text)) return { value: null, error: 'chars' };

  const compact = text.replace(/[\s\u00A0\u202F]/g, '');
  if (!/\d/.test(compact)) return { value: null, error: 'chars' };

  // «100.000» / «1,234,567» — разделители тысяч; «100,50» / «100.5» — дробная часть.
  let normalized;
  if (/^\d{1,3}([.,]\d{3})+$/.test(compact)) {
    normalized = compact.replace(/[.,]/g, '');
  } else {
    const seps = compact.match(/[.,]/g) || [];
    if (seps.length > 1) return { value: null, error: 'chars' };
    normalized = compact.replace(',', '.');
  }

  const num = Number(normalized);
  if (!Number.isFinite(num)) return { value: null, error: 'chars' };
  const value = Math.round(num);
  if (value < 0 || (value === 0 && !allowZero)) return { value: null, error: 'empty' };
  if (value > max) return { value: null, error: 'max' };
  return { value, error: null };
}

/** Сумма с неразрывными пробелами для подписи ошибки: 1 000 000 000 000. */
export function formatMoneyLimit(n = MONEY_MAX) {
  return String(n).replace(/\B(?=(\d{3})+(?!\d))/g, '\u00A0');
}
