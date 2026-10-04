import { describe, it, expect } from 'vitest';
import {
  NBSP, unitLabel, formatRegionNumber, formatRegionWithUnit, formatRegionCompact,
  formatDeltaPercent, prioritizeIndicators,
} from './regionUi';
import { flagForSlug, flagFromIso } from './slugFlags';

describe('unitLabel', () => {
  it('называет единицу коротко и по-человечески', () => {
    expect(unitLabel('рублей')).toBe('₽');
    expect(unitLabel('в процентах')).toBe('%');
    expect(unitLabel('тысяч человек')).toBe('тыс. чел.');
    expect(unitLabel('% к предыдущему году')).toBe('% за год');
    expect(unitLabel('% к предыдущему году', 'en')).toBe('% YoY');
  });

  it('длинную единицу с процентами сводит к «%», а неизвестную не выдумывает', () => {
    expect(unitLabel('Численность населения с денежными доходами ниже границы, процентов от общей численности')).toBe('%');
    expect(unitLabel('')).toBe('');
    expect(unitLabel('какая-то очень длинная и непонятная единица измерения')).toBe('');
  });
});

describe('formatRegionWithUnit', () => {
  it('проценты — с одним знаком и неразрывным пробелом: «1,0 %», «3,4 %»', () => {
    expect(formatRegionWithUnit(1, '%')).toBe(`1,0${NBSP}%`);
    expect(formatRegionWithUnit(3.4, '%')).toBe(`3,4${NBSP}%`);
    expect(formatRegionWithUnit(3.404, 'в процентах')).toBe(`3,4${NBSP}%`);
  });

  it('«₽» не отрывается от числа', () => {
    expect(formatRegionWithUnit(65822, '₽')).toBe(`65${NBSP}822${NBSP}₽`);
  });

  it('нет значения — тире без единицы', () => {
    expect(formatRegionWithUnit(null, '%')).toBe('—');
  });
});

describe('formatRegionCompact', () => {
  it('сжимает крупные суммы и численность для узких карточек', () => {
    expect(formatRegionCompact(8118831, 'миллионов рублей')).toBe(`8,1${NBSP}трлн${NBSP}₽`);
    expect(formatRegionCompact(13150, 'тысяч человек')).toBe(`13,2${NBSP}млн${NBSP}чел.`);
    expect(formatRegionCompact(2463550, 'рублей')).toBe(`2,5${NBSP}млн${NBSP}₽`);
  });

  it('обычные величины не трогает', () => {
    expect(formatRegionCompact(162572, 'рублей')).toBe(`162${NBSP}572${NBSP}₽`);
    expect(formatRegionCompact(2.9, 'процентов')).toBe(`2,9${NBSP}%`);
  });
});

describe('formatRegionNumber / formatDeltaPercent', () => {
  it('крупные целые, малые с дробью', () => {
    expect(formatRegionNumber(188561, '₽')).toBe(`188${NBSP}561`);
    expect(formatRegionNumber(26.4, '%')).toBe('26,4');
  });

  it('изменение: «44,4 %» и «<0,1 %»', () => {
    expect(formatDeltaPercent(-44.4)).toBe(`44,4${NBSP}%`);
    expect(formatDeltaPercent(0.02)).toBe(`<0,1${NBSP}%`);
    expect(formatDeltaPercent(3.3, 'en')).toBe(`3.3${NBSP}%`);
  });
});

describe('prioritizeIndicators', () => {
  it('«Численность населения» впереди, беженцы и убежище — в конец, порядок прочих сохраняется', () => {
    const rows = [
      { name: 'Численность беженцев' },
      { name: 'Рождаемость' },
      { name: 'Численность лиц, получивших временное убежище' },
      { name: 'Численность населения' },
      { name: 'Смертность' },
    ];
    expect(prioritizeIndicators(rows).map((r) => r.name)).toEqual([
      'Численность населения', 'Рождаемость', 'Смертность',
      'Численность беженцев', 'Численность лиц, получивших временное убежище',
    ]);
  });
});

describe('slugFlags', () => {
  it('флаг по slug каталога и по коду ISO', () => {
    expect(flagForSlug('germany')).toBe('\u{1F1E9}\u{1F1EA}');
    expect(flagForSlug('united-states')).toBe(flagFromIso('US'));
    expect(flagForSlug('atlantis')).toBe('');
    expect(flagFromIso('x')).toBe('');
  });
});
