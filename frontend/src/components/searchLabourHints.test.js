import { describe, expect, it } from 'vitest';
import { isLabourQuery, labourSuggestions, placeFromQuery } from './searchLabourHints';

const t = (k) => ({ 'r6a.labour.wage': 'Зарплата', 'r6a.labour.unemployment': 'Безработица', 'r6a.labour.living': 'Прожиточный минимум', 'r6a.labour.pension': 'Пенсия', 'r6a.labour.income': 'Доходы' })[k];

describe('searchLabourHints', () => {
  it('узнаёт вопрос про работу', () => {
    expect(isLabourQuery('зарплата врачей самара')).toBe(true);
    expect(isLabourQuery('курс доллара')).toBe(false);
  });
  it('берёт место из запроса', () => {
    expect(placeFromQuery('зарплата врачей самара')).toBe('самара');
    expect(placeFromQuery('сколько получает учитель тольятти')).toBe('тольятти');
  });
  it('даёт ближайшие ряды с местом', () => {
    expect(labourSuggestions('зарплата врачей самара', t)[0]).toBe('Зарплата самара');
    expect(labourSuggestions('курс', t)).toEqual([]);
  });
});
