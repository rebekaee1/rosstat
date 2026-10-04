import { describe, it, expect } from 'vitest';
import { indicatorPolarity, deltaTone, deltaArrow } from './deltaTone';

describe('deltaTone', () => {
  it('does not paint rising inflation or unemployment as good', () => {
    expect(deltaTone(0.3, indicatorPolarity('Инфляция'))).toBe('bad');
    expect(deltaTone(-44.4, indicatorPolarity('Уровень безработицы'))).toBe('good');
    expect(deltaTone(1, indicatorPolarity('Unemployment rate'))).toBe('bad');
  });
  it('treats growth of output and income as good', () => {
    expect(deltaTone(2, indicatorPolarity('ВВП'))).toBe('good');
    expect(deltaTone(-2, indicatorPolarity('Реальные доходы'))).toBe('bad');
  });
  it('stays neutral when the meaning is unknown and flat on no change', () => {
    expect(deltaTone(5, indicatorPolarity('Цена золота'))).toBe('neutral');
    expect(deltaTone(0, 'up-good')).toBe('flat');
    expect(deltaTone(null, 'up-good')).toBe('flat');
    expect(deltaArrow(3)).toBe('↗');
    expect(deltaArrow(-3)).toBe('↘');
    expect(deltaArrow(0)).toBe('→');
  });
});
