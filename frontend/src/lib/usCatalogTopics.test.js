import { describe, expect, it } from 'vitest';
import { groupUsSections, shortUsIndicatorName } from './usCatalogTopics';

describe('US catalog taxonomy', () => {
  it('keeps every source section and separates shared BEA tables by topic', () => {
    const sections = [
      { name: 'Состав ВВП', indicators: [{ code: 'us-bea-sagdp1-4' }] },
      { name: 'Оплата труда по отраслям', indicators: [{ code: 'us-bea-sagdp4-1' }] },
      { name: 'Пенсионные планы штатов и муниципалитетов', indicators: [{ code: 'bea-sainc70-1' }] },
      { name: 'Рынок труда', indicators: [{ code: 'unemployment-rate' }] },
    ];
    const topics = groupUsSections(sections);
    expect(topics.map((topic) => [topic.id, topic.count])).toEqual([
      ['gdp', 1], ['labor', 2], ['public', 1],
    ]);
    expect(topics.flatMap((topic) => topic.sections).map((section) => section.name).sort())
      .toEqual(sections.map((section) => section.name).sort());
  });

  it('changes only Russian navigation labels and removes repeated Russian prefixes', () => {
    const sections = [{ name: 'Prices', name_ru: 'Цены', indicators: [{ code: 'us-cpi-all' }] }];
    expect(groupUsSections(sections, 'en')[0].label).toBe('Prices');
    expect(shortUsIndicatorName('Состав ВВП: Оплата труда', 'Состав ВВП', 'ru')).toBe('Оплата труда');
    expect(shortUsIndicatorName('State GDP overview: Compensation', 'State GDP overview', 'en'))
      .toBe('State GDP overview: Compensation');
  });
});
