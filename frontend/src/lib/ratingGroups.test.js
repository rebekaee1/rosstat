import { describe, expect, it } from 'vitest';
import {
  filterRowsByGroup, groupCounts, inRatingGroup, normalizeRatingGroup, RATING_GROUP_IDS,
} from './ratingGroups';

const rows = ['US', 'JP', 'DE', 'GB', 'FR', 'IT', 'CA', 'RU', 'CN', 'IN', 'BR', 'ZA', 'TR', 'AZ', 'AM', 'MD', 'PL']
  .map((code) => ({ country_code: code }));

describe('группы стран рейтинга', () => {
  it('порядок кнопок: Все, G7, БРИКС, СНГ', () => {
    expect(RATING_GROUP_IDS).toEqual(['all', 'g7', 'brics', 'cis']);
  });

  it('G7 это семь стран, БРИКС пять, СНГ те из каталога, что входят в содружество', () => {
    const codes = (id) => filterRowsByGroup(rows, id).map((r) => r.country_code).sort();
    expect(codes('g7')).toEqual(['CA', 'DE', 'FR', 'GB', 'IT', 'JP', 'US']);
    expect(codes('brics')).toEqual(['BR', 'CN', 'IN', 'RU', 'ZA']);
    expect(codes('cis')).toEqual(['AM', 'AZ', 'MD', 'RU']);
    expect(filterRowsByGroup(rows, 'all')).toBe(rows);
  });

  it('неизвестная группа из адреса читается как «все»', () => {
    expect(normalizeRatingGroup('G7')).toBe('g7');
    expect(normalizeRatingGroup('nato')).toBe('all');
    expect(normalizeRatingGroup(null)).toBe('all');
    expect(inRatingGroup('nato', 'US')).toBe(false);
    expect(inRatingGroup('all', 'XX')).toBe(true);
  });

  it('счётчики по группам: пустые видны как ноль', () => {
    expect(groupCounts(rows)).toEqual({ all: 17, g7: 7, brics: 5, cis: 4 });
    expect(groupCounts([{ country_code: 'PL' }])).toEqual({ all: 1, g7: 0, brics: 0, cis: 0 });
  });
});
