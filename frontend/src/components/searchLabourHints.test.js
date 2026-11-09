import { describe, expect, it } from 'vitest';
import { isLabourQuery, isMrotQuery, labourNoteKey, labourSuggestions, localSuggestions, placeFromQuery } from './searchLabourHints';

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
    expect(labourSuggestions('зарплата врачей самара', t)[0]).toBe('Зарплата Самара');
    expect(labourSuggestions('курс', t)).toEqual([]);
  });
  it('R7-A: МРОТ отдельной подсказкой, регион из ответа важнее слова запроса', () => {
    expect(isMrotQuery('мрот самара')).toBe(true);
    expect(isMrotQuery('минимальная зарплата самара')).toBe(true);
    expect(isMrotQuery('зарплата самара')).toBe(false);
    expect(labourNoteKey('мрот самара')).toBe('r7a.search.mrotNote');
    expect(labourNoteKey('зарплата врачей')).toBe('r6a.search.labourNote');
    expect(labourSuggestions('мрот самара', t, 'Самарская область')[0]).toBe('Зарплата Самарская область');
  });
  it('R7-A: пустая выдача региона даёт ряды с названием региона', () => {
    const tl = (k) => k.replace('r7a.local.', '');
    expect(localSuggestions('Самарская область', tl)[0]).toBe('cpi Самарская область');
    expect(localSuggestions('', tl)).toEqual([]);
  });
});
