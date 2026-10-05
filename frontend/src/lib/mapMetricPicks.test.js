import { describe, it, expect } from 'vitest';
import { buildTopicGroups, groupIndicatorsByTopic, pickPopularIndicators } from './mapMetricPicks';

const long = (n) => Array.from({ length: n }, (_u, i) => ({
  code: `exp-${i}`,
  name: `Потребительские расходы по функциям: Статья ${i}`,
  section: 'Расходы',
}));

const INDICATORS = [
  ...long(40),
  { code: 'pop', name: 'Население', section: 'Население' },
  { code: 'unemp', name: 'Безработица', section: 'Труд' },
  { code: 'inc', name: 'Доход на душу населения', section: 'Доходы' },
  { code: 'cpi', name: 'Индекс цен', section: 'Цены' },
  { code: 'house', name: 'Цены на жильё', section: 'Жильё' },
  { code: 'gdp', name: 'ВРП', section: 'Счета' },
  { code: 'wage', name: 'Средняя зарплата', section: 'Труд' },
];

describe('pickPopularIndicators', () => {
  it('берёт не больше шести понятных тем и не берёт «разбивки» с двоеточием', () => {
    const picked = pickPopularIndicators(INDICATORS, 'unemp', 6);
    expect(picked).toHaveLength(6);
    expect(picked[0].code).toBe('unemp');
    expect(picked.every((i) => !i.name.includes(':'))).toBe(true);
    const codes = picked.map((i) => i.code);
    expect(codes).toContain('pop');
    expect(codes).toContain('inc');
  });

  it('если простых названий мало — добирает остальными, но не дублирует', () => {
    const picked = pickPopularIndicators(long(3), null, 6);
    expect(picked).toHaveLength(3);
    expect(new Set(picked.map((i) => i.code)).size).toBe(3);
  });

  it('пустой ввод не падает', () => {
    expect(pickPopularIndicators(null, 'x')).toEqual([]);
  });
});

describe('groupIndicatorsByTopic / buildTopicGroups', () => {
  it('группирует по теме в порядке появления', () => {
    const groups = groupIndicatorsByTopic(INDICATORS, 'Прочее');
    expect(groups[0].name).toBe('Расходы');
    expect(groups[0].items).toHaveLength(40);
    expect(groups.map((g) => g.name)).toContain('Труд');
  });

  it('без темы — в запасную группу', () => {
    const groups = groupIndicatorsByTopic([{ code: 'a', name: 'A' }], 'Прочее');
    expect(groups).toEqual([{ name: 'Прочее', items: [{ code: 'a', name: 'A' }] }]);
  });

  it('темы США берутся, только если разделы покрывают весь список', () => {
    const sections = [{ name: 'Труд', indicators: [{ code: 'unemployment-rate', name: 'Безработица' }] }];
    const partial = buildTopicGroups({
      indicators: [{ code: 'unemployment-rate', name: 'Безработица', section: 'Труд' }, { code: 'x', name: 'X', section: 'Y' }],
      sections, usTopics: true, locale: 'ru', fallbackName: 'Прочее',
    });
    expect(partial.map((g) => g.name)).toEqual(['Труд', 'Y']);
    const full = buildTopicGroups({
      indicators: [{ code: 'unemployment-rate', name: 'Безработица', section: 'Труд' }],
      sections, usTopics: true, locale: 'ru', fallbackName: 'Прочее',
    });
    expect(full[0].name).toBe('Труд и зарплаты');
    expect(full[0].blocks[0].items[0].code).toBe('unemployment-rate');
  });
});
