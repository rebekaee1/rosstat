import { describe, expect, it } from 'vitest';
import {
  dropRepeatedUnit, groupBaseName, groupMemberLabel, groupNearDuplicates, indicatorBaseName,
} from './countryIndicatorGroups';

const name = (item) => item.name;

describe('indicatorBaseName', () => {
  it('берёт начало названия до «по», двоеточия, скобки или запятой', () => {
    expect(indicatorBaseName('Число родившихся по возрасту матери')).toBe('Число родившихся');
    expect(indicatorBaseName('Число умерших, человек')).toBe('Число умерших');
    expect(indicatorBaseName('Население (на начало года)')).toBe('Население');
    expect(indicatorBaseName('Births by age of mother')).toBe('Births');
  });
});

describe('dropRepeatedUnit', () => {
  it('убирает единицу из хвоста названия, если она показана отдельно', () => {
    expect(dropRepeatedUnit('Число умерших, человек', 'человек')).toBe('Число умерших');
    expect(dropRepeatedUnit('Площадь (км2)', 'км2')).toBe('Площадь');
  });

  it('не трогает название без повтора и не оставляет пустую строку', () => {
    expect(dropRepeatedUnit('Число умерших', 'человек')).toBe('Число умерших');
    expect(dropRepeatedUnit('человек', 'человек')).toBe('человек');
  });
});

describe('groupNearDuplicates', () => {
  const items = [
    { code: 'a', name: 'Число родившихся по возрасту матери, до 20 лет' },
    { code: 'b', name: 'Безработица' },
    { code: 'c', name: 'Число родившихся по возрасту матери, 20-24' },
    { code: 'd', name: 'Число родившихся по месту проживания' },
    { code: 'e', name: 'Число умерших' },
    { code: 'f', name: 'Число умерших, человек' },
  ];

  it('склеивает почти-дубли в группу на месте первого и оставляет одиночные', () => {
    const rows = groupNearDuplicates(items, name);
    expect(rows.map((row) => row.kind)).toEqual(['group', 'single', 'group']);
    expect(rows[0].base).toBe('Число родившихся');
    expect(rows[0].items.map((i) => i.code)).toEqual(['a', 'c', 'd']);
    expect(rows[1].item.code).toBe('b');
    expect(rows[2].items.map((i) => i.code)).toEqual(['e', 'f']);
  });

  it('короткое общее начало не склеивает разные показатели', () => {
    const rows = groupNearDuplicates([{ name: 'ВВП по расходам' }, { name: 'ВВП по доходам' }], name);
    expect(rows.every((row) => row.kind === 'single')).toBe(true);
  });
});

describe('groupBaseName (круг 9, W1)', () => {
  it('короткое начало («Занятые») заменяется названием до первой запятой', () => {
    expect(groupBaseName('Занятые по стажу на работе и виду деятельности, тысяч человек, мужчины'))
      .toBe('Занятые по стажу на работе и виду деятельности');
  });

  it('длинное начало работает как раньше, короткое без запятой не склеивается', () => {
    expect(groupBaseName('Число родившихся по возрасту матери')).toBe('Число родившихся');
    expect(groupBaseName('ВВП по расходам')).toBe('');
  });
});

describe('groupNearDuplicates: «Занятые по …»', () => {
  const rows = groupNearDuplicates([
    { code: 'a', name: 'Занятые по стажу на работе и виду деятельности, тысяч человек, мужчины' },
    { code: 'b', name: 'Занятые по стажу на работе и виду деятельности, тысяч человек, женщины' },
    { code: 'c', name: 'Занятые по занятию и уровню образования, тысяч человек, 20–64 лет' },
    { code: 'd', name: 'Занятые по занятию и уровню образования, тысяч человек, мужчины' },
  ], name);

  it('два разреза рынка труда дают две группы, а не одну огромную', () => {
    expect(rows.map((row) => row.kind)).toEqual(['group', 'group']);
    expect(rows.map((row) => row.items.length)).toEqual([2, 2]);
  });
});

describe('groupMemberLabel', () => {
  const base = 'Занятые по стажу на работе и виду деятельности';
  it('оставляет только отличие и убирает единицу', () => {
    expect(groupMemberLabel(`${base}, тысяч человек, мужчины`, base, 'тысяч человек')).toBe('Мужчины');
    expect(groupMemberLabel(`${base}, тысяч человек, 15–24 лет`, base, 'тысяч человек')).toBe('15–24 лет');
  });

  it('остаток, который сам единица («% of active population»), не становится чипом без названия', () => {
    const basePart = 'Individuals using the internet';
    expect(groupMemberLabel(`${basePart}, % of active population`, basePart, 'persons')).toBe(`${basePart}, % of active population`);
    expect(groupMemberLabel(`${basePart}, persons`, basePart, 'persons')).toBe(`${basePart}, persons`);
  });

  it('если отличий нет, возвращает полное название', () => {
    expect(groupMemberLabel(`${base}, тысяч человек`, base, 'тысяч человек')).toBe(`${base}, тысяч человек`);
  });
});
