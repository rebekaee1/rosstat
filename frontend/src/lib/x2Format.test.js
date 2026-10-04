import { describe, expect, it } from 'vitest';
import { formatCount } from './format';
import { glueDate, periodPhrase } from './periodPhrase';
import { commonTilePhrase } from './tileDates';
import { splitChipOverflow } from './chipOverflow';

const t = (key, params = {}) => ({
  'w3.tele.asOf': `на ${params.date}`,
  'w3.tele.forPeriod': `за ${params.date}`,
  'w3.tele.forYear': `за ${params.date} год`,
}[key] ?? key);

describe('formatCount', () => {
  it('тысячи — неразрывный пробел, без дробной части', () => {
    expect(formatCount(2197, 'ru')).toBe('2 197');
    expect(formatCount(8205, 'ru')).toBe('8 205');
    expect(formatCount(24, 'ru')).toBe('24');
    expect(formatCount(null, 'ru')).toBe('');
  });
});

describe('glueDate / periodPhrase', () => {
  it('дата не рвётся переносом: год не остаётся сиротой', () => {
    expect(glueDate('3 октября 2026')).toBe('3 октября 2026');
    expect(periodPhrase(t, '2026-10-03', 'day', 'ru')).toBe('на 3 октября 2026');
    expect(periodPhrase(t, '2026-08-01', 'full', 'ru')).toBe('за август 2026');
    expect(periodPhrase(t, null, 'full', 'ru')).toBeUndefined();
  });
});

describe('commonTilePhrase', () => {
  const tile = (code, date, frequency = 'daily') => ({
    code, is_active: true, frequency, current_date: date,
  });

  it('берёт самую частую подпись периода, если её делят хотя бы три плитки и половина списка', () => {
    const list = [
      tile('a', '2026-10-03'), tile('b', '2026-10-03'), tile('c', '2026-10-03'), tile('d', '2026-10-02'),
    ];
    expect(commonTilePhrase(list, t, 'ru')).toBe('на 3 октября 2026');
  });

  it('нет общей даты у разнобоя и у коротких списков', () => {
    expect(commonTilePhrase([tile('a', '2026-10-03'), tile('b', '2026-10-03')], t, 'ru')).toBeNull();
    const mixed = [tile('a', '2026-10-03'), tile('b', '2026-10-02'), tile('c', '2026-10-01'), tile('d', '2026-09-30')];
    expect(commonTilePhrase(mixed, t, 'ru')).toBeNull();
  });
});

describe('splitChipOverflow', () => {
  const items = ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h'].map((id) => ({ id }));

  it('короткий список показываем целиком', () => {
    expect(splitChipOverflow(items.slice(0, 6), () => false, 6).hidden).toHaveLength(0);
  });

  it('длинный: пять сразу, остальные под «Ещё», выбранный не прячется', () => {
    const plain = splitChipOverflow(items, () => false, 6);
    expect(plain.shown.map((i) => i.id)).toEqual(['a', 'b', 'c', 'd', 'e']);
    expect(plain.hidden).toHaveLength(3);
    const active = splitChipOverflow(items, (i) => i.id === 'g', 6);
    expect(active.shown.map((i) => i.id)).toEqual(['a', 'b', 'c', 'd', 'e', 'g']);
    expect(active.hidden.map((i) => i.id)).toEqual(['f', 'h']);
  });
});
