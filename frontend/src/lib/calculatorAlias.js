/**
 * Угаданные адреса калькуляторов: /calculators/mortgage, /calculators/deposit и т. п.
 * Возвращает настоящий адрес калькулятора; незнакомое слово ведёт на общий /calculator.
 */
const ALIASES = {
  mortgage: '/calculator/mortgage',
  ipoteka: '/calculator/mortgage',
  loan: '/calculator/mortgage',
  compound: '/calculator/compound',
  deposit: '/calculator/compound',
  vklad: '/calculator/compound',
  savings: '/calculator/compound',
};

export function calculatorAliasTarget(splat) {
  const first = String(splat || '').split('/')[0].toLowerCase();
  return ALIASES[first] || '/calculator';
}
