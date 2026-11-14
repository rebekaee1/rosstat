// «Попробуйте, например» под пустой выдачей (14.11.2026): соседи по разделу и региону, иначе по региону, иначе как раньше.
import { describe, expect, it } from 'vitest';
import { tryTheseExamples } from './searchLabourHints';
import ru from '../i18n/messages.ru';

const t = (key) => ru[key] ?? key;

describe('tryTheseExamples', () => {
  it('соседи от сервера — первыми; подпись короткая, запрос полный (ru и en)', () => {
    const suggest = [
      { label: 'Валовой сбор картофеля', query: 'Валовой сбор картофеля Воронежская область' },
      { label: 'Gross harvest of grain', query: 'Gross harvest of grain Voronezh Oblast' },
    ];
    const out = tryTheseExamples({ suggest, regionName: 'Воронежская область', popular: ['Курс доллара'], t });
    expect(out.map((item) => item.label)).toEqual(['Валовой сбор картофеля', 'Gross harvest of grain']);
    expect(out.map((item) => item.query)).toEqual(['Валовой сбор картофеля Воронежская область', 'Gross harvest of grain Voronezh Oblast']);
  });

  it('строки (старый формат) работают как прежде', () => {
    expect(tryTheseExamples({ suggest: ['Валовой сбор овощей Воронежская область'], t }))
      .toEqual([{ label: 'Валовой сбор овощей Воронежская область', query: 'Валовой сбор овощей Воронежская область' }]);
  });

  it('регион назван — подсказки по этому региону, без курсов валют', () => {
    const out = tryTheseExamples({ regionName: 'Воронежская область', popular: ['Курс узбекского сума'], t });
    expect(out[0]).toEqual({ label: 'Инфляция Воронежская область', query: 'Инфляция Воронежская область' });
    expect(out).toHaveLength(6);
    expect(out.map((item) => item.label).join(' ')).not.toMatch(/Курс/);
  });

  it('без региона — прежний набор: три курса и популярное, без повторов, не больше шести', () => {
    const rate = t('z4s.empty.rate.1');
    const out = tryTheseExamples({ regionName: '', popular: [rate, 'Цены на яйца в Москве', 'a', 'b', 'c', 'd'], t });
    expect(out[0].label).toBe(rate);
    expect(new Set(out.map((item) => item.query)).size).toBe(out.length);
    expect(out.length).toBeLessThanOrEqual(6);
  });
});
