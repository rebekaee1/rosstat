import { describe, it, expect, vi } from 'vitest';
import { plural, years, loanYearOrdinal, fmtPct, formatInput, formatRubles, decimalText, formatCompactAmount, fitAmountText, formatAmountPlain } from './calcFormat';
import { currentUiLocale } from '../i18n/locale';

vi.mock('../i18n/locale', async (importOriginal) => ({
  ...(await importOriginal()),
  currentUiLocale: vi.fn(() => 'ru'),
}));

describe('calcFormat — склонения', () => {
  it('годы склоняются по русским правилам, включая второй десяток', () => {
    expect(years(1)).toBe('1 год');
    expect(years(2)).toBe('2 года');
    expect(years(4)).toBe('4 года');
    expect(years(5)).toBe('5 лет');
    expect(years(11)).toBe('11 лет');
    expect(years(12)).toBe('12 лет');
    expect(years(14)).toBe('14 лет');
    expect(years(21)).toBe('21 год');
    expect(years(22)).toBe('22 года');
    expect(years(25)).toBe('25 лет');
    expect(years(31)).toBe('31 год');
    expect(years(40)).toBe('40 лет');
  });

  it('форма выбирается для любого существительного', () => {
    expect(plural(1, 'месяц', 'месяца', 'месяцев')).toBe('месяц');
    expect(plural(3, 'месяц', 'месяца', 'месяцев')).toBe('месяца');
    expect(plural(13, 'месяц', 'месяца', 'месяцев')).toBe('месяцев');
  });
});

describe('loanYearOrdinal', () => {
  it('русская форма с -й', () => {
    expect(loanYearOrdinal(1)).toBe('1-й');
    expect(loanYearOrdinal(3, 'ru')).toBe('3-й');
    expect(loanYearOrdinal(21)).toBe('21-й');
  });

  it('английские ordinal-суффиксы', () => {
    expect(loanYearOrdinal(1, 'en')).toBe('1st');
    expect(loanYearOrdinal(2, 'en')).toBe('2nd');
    expect(loanYearOrdinal(3, 'en')).toBe('3rd');
    expect(loanYearOrdinal(4, 'en')).toBe('4th');
    expect(loanYearOrdinal(11, 'en')).toBe('11th');
    expect(loanYearOrdinal(12, 'en')).toBe('12th');
    expect(loanYearOrdinal(13, 'en')).toBe('13th');
    expect(loanYearOrdinal(21, 'en')).toBe('21st');
    expect(loanYearOrdinal(22, 'en')).toBe('22nd');
    expect(loanYearOrdinal(23, 'en')).toBe('23rd');
  });
});

describe('числа калькуляторов следуют языку страницы', () => {
  it('русский: запятая и пробел тысяч', () => {
    currentUiLocale.mockReturnValue('ru');
    expect(fmtPct(40.5, true)).toBe('+40,5%');
    expect(formatInput(100000)).toBe('100 000');
    expect(decimalText(1.414, 2)).toBe('1,41');
    expect(formatRubles(140532)).toBe('140\u00A0532\u00A0₽');
  });

  it('английский: точка и запятая тысяч', () => {
    currentUiLocale.mockReturnValue('en');
    expect(fmtPct(40.5, true)).toBe('+40.5%');
    expect(formatInput(100000)).toBe('100,000');
    expect(decimalText(1.414, 2)).toBe('1.41');
    expect(formatRubles(140532)).toBe('140,532\u00A0₽');
    currentUiLocale.mockReturnValue('ru');
  });
});

describe('круг 11 (E): длинные суммы и проценты', () => {
  it('«Рост цен» с пробелами между разрядами', () => {
    currentUiLocale.mockReturnValue('ru');
    expect(fmtPct(17147219.6, true)).toBe('+17\u00A0147\u00A0219,6%');
    expect(fmtPct(-1234.5)).toBe('-1\u00A0234,5%');
    expect(decimalText(171473.19, 2)).toBe('171\u00A0473,19');
    expect(fmtPct(40.5, true)).toBe('+40,5%');
    currentUiLocale.mockReturnValue('en');
    expect(fmtPct(17147219.6, true)).toBe('+17,147,219.6%');
    currentUiLocale.mockReturnValue('ru');
  });

  it('сокращение: «17,1 млрд ₽» вместо «17 147 319 6…»', () => {
    currentUiLocale.mockReturnValue('ru');
    expect(formatCompactAmount(17147319615)).toBe('17,1\u00A0млрд\u00A0₽');
    expect(formatCompactAmount(160000000)).toBe('160\u00A0млн\u00A0₽');
    expect(formatCompactAmount(2500000000000)).toBe('2,5\u00A0трлн\u00A0₽');
    expect(formatCompactAmount(98772)).toBe('98\u00A0772\u00A0₽');
    currentUiLocale.mockReturnValue('en');
    expect(formatCompactAmount(17147319615, '$', { prefix: true })).toBe('$17.1B');
    currentUiLocale.mockReturnValue('ru');
  });

  it('fitAmountText оставляет короткое полностью и сокращает длинное', () => {
    currentUiLocale.mockReturnValue('ru');
    const short = formatRubles(98772);
    expect(fitAmountText(short, 98772)).toBe(short);
    const long = formatRubles(17147319615);
    expect(fitAmountText(long, 17147319615)).toBe('17,1\u00A0млрд\u00A0₽');
    expect(formatAmountPlain(1234567)).toBe('1\u00A0234\u00A0567');
  });
});
