import { describe, expect, it } from 'vitest';
import { isAccountPath, isToolsPath, resolveActiveNavId } from './navItems';

describe('navItems, круг 11 G (U2, U33)', () => {
  it('«Страны» подсвечены по адресу #countries и пока видна секция каталога, только на главной', () => {
    expect(resolveActiveNavId('/', undefined, '#countries')).toBe('countries');
    expect(resolveActiveNavId('/', undefined, '', true)).toBe('countries');
    expect(resolveActiveNavId('/', undefined, '', false)).toBe('home');
    expect(resolveActiveNavId('/compare', undefined, '#countries')).toBe('compare');
    expect(resolveActiveNavId('/world/rating/gdp-usd', undefined, '', true)).toBe('world-rating');
  });

  it('страницы валют подсвечивают «Курсы валют»', () => {
    expect(resolveActiveNavId('/currencies/indicator/usd-rub')).toBe('currencies');
    expect(resolveActiveNavId('/currencies')).toBe('currencies');
  });

  it('калькуляторы и виджеты — «Инструменты», кабинет — своя кнопка', () => {
    expect(isToolsPath('/calculator')).toBe(true);
    expect(isToolsPath('/calculator/mortgage')).toBe(true);
    expect(isToolsPath('/widgets')).toBe(true);
    expect(isToolsPath('/calculators-news')).toBe(false);
    expect(isToolsPath('/compare')).toBe(false);
    expect(isAccountPath('/account')).toBe(true);
    expect(isAccountPath('/account/exports')).toBe(true);
    expect(isAccountPath('/accounting')).toBe(false);
  });
});
