import { describe, expect, it } from 'vitest';
import { formatPointLabel, pointLabelWidth } from './chartPointLabel';

const flat = (s) => s.replace(/\u00A0/g, ' ');

describe('formatPointLabel', () => {
  it('миллионы: «28,08 млн» вместо полной записи', () => {
    expect(flat(formatPointLabel(28076986, 2, 'ru'))).toBe('28,08 млн');
  });

  it('миллиарды и триллионы укрупняются; чем больше число, тем меньше знаков', () => {
    expect(flat(formatPointLabel(3.4e9, 2, 'ru'))).toBe('3,4 млрд');
    expect(flat(formatPointLabel(32.5e12, 2, 'ru'))).toBe('32,5 трлн');
    expect(flat(formatPointLabel(150e6, 2, 'ru'))).toBe('150 млн');
  });

  it('меньшие числа остаются обычными с заданной точностью', () => {
    expect(flat(formatPointLabel(30767.1, 1, 'ru'))).toBe('30 767,1');
    expect(flat(formatPointLabel(3.1, 1, 'ru'))).toBe('3,1');
  });

  it('английские сокращения', () => {
    expect(flat(formatPointLabel(28076986, 2, 'en'))).toBe('28.08 M');
  });

  it('пустое значение даёт пустую подпись', () => {
    expect(formatPointLabel(null)).toBe('');
    expect(formatPointLabel(NaN)).toBe('');
  });
});

describe('pointLabelWidth', () => {
  it('растёт с длиной текста', () => {
    expect(pointLabelWidth('28,08 млн')).toBeGreaterThan(pointLabelWidth('3,1'));
  });
});
