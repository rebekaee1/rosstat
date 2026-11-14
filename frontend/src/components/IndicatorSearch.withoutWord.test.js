// «Ближайшее» без слова, которого нет в названиях рядов (14.11.2026): подпись простыми словами, ru и en.
import { describe, expect, it } from 'vitest';
import { quotedWords } from './IndicatorSearch';
import ru from '../i18n/messages.ru';
import en from '../i18n/messages.en';

function fill(template, words) {
  return template.replace('{words}', words);
}

describe('без слова', () => {
  it('кавычки по языку и перечисление', () => {
    expect(quotedWords(['структура'], 'ru')).toBe('«структура»');
    expect(quotedWords(['активных', 'пользователей'], 'ru')).toBe('«активных», «пользователей»');
    expect(quotedWords(['structure'], 'en')).toBe('“structure”');
    expect(quotedWords(undefined, 'ru')).toBe('');
  });

  it('тексты есть в обоих языках, без служебных слов', () => {
    for (const messages of [ru, en]) {
      for (const key of ['r8a.nearest.without_word', 'r8a.nearest.without_words']) {
        expect(messages[key]).toContain('{words}');
        expect(messages[key]).not.toMatch(/nearest|query|search-|ADR|token|ряд кода/i);
      }
    }
    expect(fill(ru['r8a.nearest.without_word'], quotedWords(['структура'], 'ru')))
      .toBe('Со словом «структура» ничего не нашлось. Без него есть вот что:');
  });
});
