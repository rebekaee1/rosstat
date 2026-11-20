import { describe, expect, it } from 'vitest';
import { isAccountPath, isToolsPath, isTourismPath, mobileNavGroups, resolveActiveNavId } from './navItems';

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

describe('navItems, правка 43 (подсветка раздела «Туризм»)', () => {
  const mobileItems = mobileNavGroups('ru').flatMap((group) => group.items);

  it('раздел и страницы его показателей подсвечивают «Туризм», а не «Цены по регионам» или «Категории»', () => {
    expect(resolveActiveNavId('/russia/category/tourism', mobileItems)).toBe('tourism');
    expect(resolveActiveNavId('/russia/region/moskva/tour-hotel-guests', mobileItems)).toBe('tourism');
    expect(resolveActiveNavId('/russia/region-rating/tour-hotel-guests', mobileItems)).toBe('tourism');
    expect(resolveActiveNavId('/world/rating/tour-inbound-trips', mobileItems)).toBe('tourism');
  });

  it('там, где отдельного пункта нет (верхняя пилюля), чужой пункт не подсвечивается', () => {
    expect(resolveActiveNavId('/russia/region/moskva/tour-hotel-guests')).toBeNull();
  });

  it('обычные региональные страницы по-прежнему подсвечивают «Цены по регионам»', () => {
    expect(resolveActiveNavId('/russia/region/moskva', mobileItems)).toBe('region-prices');
    expect(isTourismPath('/russia/region/moskva/cpi')).toBe(false);
    expect(isTourismPath('/russia/category/tourism')).toBe(true);
  });
});
