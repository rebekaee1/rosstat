import { describe, expect, it } from 'vitest';
import { changeCorrelation, changePairs, pearsonCorrelation } from './compareStats';

const series = (values) => values.map((value, i) => ({ date: `2000-${String(i + 1).padStart(2, '0')}-01`, value }));

describe('compareStats', () => {
  it('два растущих ряда с разными скачками не считаются связанными', () => {
    const a = series([100, 110, 121, 133, 146, 161, 177, 195, 214, 235]);
    // растёт ровно так же в уровнях, но прирост у второго идёт вразнобой
    const b = series([100, 130, 135, 170, 172, 210, 215, 260, 262, 330]);
    const byLevel = pearsonCorrelation(a.map((p, i) => [p.value, b[i].value]));
    const byChange = changeCorrelation(a, b).value;
    expect(byLevel).toBeGreaterThan(0.9);
    expect(Math.abs(byChange)).toBeLessThan(0.6);
  });

  it('совпадающие подъёмы и спады дают значение около 1', () => {
    const a = series([5, 6, 4, 7, 3, 8, 5, 9, 4]);
    const b = series([50, 62, 41, 70, 29, 85, 52, 93, 38]);
    expect(changeCorrelation(a, b).value).toBeGreaterThan(0.95);
  });

  it('противоположные движения дают значение около -1; сальдо с нулями считается разностью', () => {
    const a = series([1, 3, 0, 4, -1, 5, 0, 6]);
    const b = series([4, 2, 5, 1, 6, 0, 5, -1]);
    expect(changePairs(a, b)).toHaveLength(7);
    expect(changeCorrelation(a, b).value).toBeLessThan(-0.95);
  });

  it('мало общих дат: связи нет', () => {
    const a = series([1, 2, 3]);
    expect(changeCorrelation(a, a).value).toBeNull();
    expect(changeCorrelation([], a).observations).toBe(0);
  });
});
