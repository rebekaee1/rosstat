import { describe, expect, it } from 'vitest';
import { dropRepeatedUnit, groupNearDuplicates, indicatorBaseName } from './countryIndicatorGroups';

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
