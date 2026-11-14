// «Попробуйте, например» под пустой выдачей (14.11.2026): по региону запроса, иначе как раньше.
import { describe, expect, it } from 'vitest';
import { tryTheseExamples } from './searchLabourHints';
import ru from '../i18n/messages.ru';

const t = (key) => ru[key] ?? key;

describe('tryTheseExamples', () => {
  it('регион назван — подсказки по этому региону, без курсов валют', () => {
    const out = tryTheseExamples({ regionName: 'Воронежская область', popular: ['Курс узбекского сума'], t });
    expect(out[0]).toBe('Инфляция Воронежская область');
    expect(out).toHaveLength(6);
    expect(out.join(' ')).not.toMatch(/Курс/);
  });

  it('без региона — прежний набор: три курса и популярное, без повторов, не больше шести', () => {
    const rate = t('z4s.empty.rate.1');
    const out = tryTheseExamples({ regionName: '', popular: [rate, 'Цены на яйца в Москве', 'a', 'b', 'c', 'd'], t });
    expect(out[0]).toBe(rate);
    expect(new Set(out).size).toBe(out.length);
    expect(out.length).toBeLessThanOrEqual(6);
  });
});
