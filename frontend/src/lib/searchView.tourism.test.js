// Раздел «Туризм» в поиске (20.11.2026): строка раздела первой, только без иностранного места.
import { describe, expect, it } from 'vitest';
import { buildSearchView, sectionRowsFor } from './searchView';

const t = (key) => key;
const base = { nameOf: (r) => r.name, titleOf: (r) => r.name, detailOf: () => '', t };

describe('sectionRowsFor', () => {
  it.each(['туризм', 'Туризм в России', 'tourism', 'турпоток', 'туристический налог', 'статистика туризма'])('«%s» → раздел', (q) => {
    const rows = sectionRowsFor(q, { intent: { countries: [], regions: [] }, t });
    expect(rows.map((r) => r.open.path)).toEqual(['/russia/category/tourism']);
  });
  it('без раздела: другая тема, иностранная страна или регион', () => {
    expect(sectionRowsFor('инфляция', { t })).toEqual([]);
    expect(sectionRowsFor('туризм турция', { intent: { countries: ['turkey'] }, t })).toEqual([]);
    expect(sectionRowsFor('туризм самара', { intent: { regions: ['samarskaya-oblast'] }, t })).toEqual([]);
  });
});

it('строка раздела стоит первой секцией выдачи', () => {
  const rows = [{ key: 'ru:tour-outbound-trips', kind: 'russia', code: 'tour-outbound-trips', name: 'Выездные поездки', path: '/russia/indicator/tour-outbound-trips' }];
  const view = buildSearchView(rows, { ...base, query: 'туризм', intent: { countries: [], regions: [] } });
  expect(view.sections[0].id).toBe('sections');
  expect(view.sections[0].rows[0].open.path).toBe('/russia/category/tourism');
  expect(view.sections[1].rows[0].item.code).toBe('tour-outbound-trips');
});
