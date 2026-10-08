import { describe, expect, it } from 'vitest';
import { periodPhrase, sincePhrase } from './periodPhrase';

const NB = ' ';
const t = (key, params = {}) => `${key}|${params.date ?? ''}`;

describe('sincePhrase: «с августа 2016»', () => {
  it('месячная дата в родительном падеже и без разрыва строки', () => {
    expect(sincePhrase(t, '2016-08-01', 'full', 'ru')).toBe(`w6e.tile.growthNote|августа${NB}2016`);
  });

  it('квартал, год и день падежа не меняют', () => {
    expect(sincePhrase(t, '2016-04-01', 'quarterly', 'ru')).toBe(`w6e.tile.growthNote|II${NB}кв.${NB}2016`);
    expect(sincePhrase(t, '2016-01-01', 'annual', 'ru')).toBe('w6e.tile.growthNote|2016');
    expect(sincePhrase(t, '2016-08-15', 'day', 'ru')).toBe(`w6e.tile.growthNote|15${NB}августа${NB}2016`);
  });

  it('английский — полное имя месяца', () => {
    expect(sincePhrase(t, '2016-08-01', 'full', 'en')).toBe(`w6e.tile.growthNote|August${NB}2016`);
  });

  it('пустая или неверная дата — без подписи', () => {
    expect(sincePhrase(t, null, 'full', 'ru')).toBeUndefined();
    expect(sincePhrase(t, 'abc', 'full', 'ru')).toBeUndefined();
  });

  it('periodPhrase по-прежнему даёт именительный для «за август 2016»', () => {
    expect(periodPhrase(t, '2016-08-01', 'full', 'ru')).toBe(`w3.tele.forPeriod|август${NB}2016`);
  });
});
