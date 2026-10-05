import { describe, expect, it } from 'vitest';
import { pickerHintKey, pickerLabel } from './pickerLabels';

describe('pickerLabel', () => {
  it('раскрывает «соотв.» и «пред.»', () => {
    expect(pickerLabel('К соотв. периоду пред. года', 'ru')).toBe('Год к году');
    expect(pickerLabel('К соотв. периоду пред. года — по кварталам', 'ru')).toBe('Год к году — по кварталам');
  });

  it('раскрывает «Г/г», «М/м», «Кв/кв»', () => {
    expect(pickerLabel('Г/г', 'ru')).toBe('Год к году');
    expect(pickerLabel('М/м', 'ru')).toBe('Месяц к месяцу');
    expect(pickerLabel('Кв/Кв', 'ru')).toBe('Квартал к кварталу');
  });

  it('не оставляет «ряд» в подсказках недоступных вариантов', () => {
    expect(pickerLabel('нет официального ряда', 'ru')).not.toMatch(/ряд/);
  });

  it('не оставляет слово «период» в подписях режимов', () => {
    expect(pickerLabel('На конец периода', 'ru')).toBe('На конец');
    expect(pickerLabel('Средняя за период', 'ru')).toBe('В среднем');
    expect(pickerLabel('К прошлому периоду', 'ru')).toBe('К прошлому значению');
    expect(pickerLabel('К прошлому периоду (г/г)', 'ru')).not.toMatch(/период/);
    expect(pickerLabel('За период', 'ru')).not.toMatch(/период/);
  });

  it('текст без сокращений не трогает', () => {
    expect(pickerLabel('По месяцам', 'ru')).toBe('По месяцам');
  });

  it('EN идёт через прежний словарь', () => {
    expect(pickerLabel('Г/г', 'en')).toBe('YoY');
    expect(pickerLabel('К году', 'en')).toBe('Year over year');
  });
});

describe('pickerHintKey', () => {
  it('у смысловых групп есть подсказка, у детализации нет', () => {
    expect(pickerHintKey('К прошлому периоду')).toBe('w3.hint.vsPrevious');
    expect(pickerHintKey('К соотв. периоду пред. года')).toBe('w3.hint.yoy');
    expect(pickerHintKey('По месяцам')).toBeNull();
  });
});
