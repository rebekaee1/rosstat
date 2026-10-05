import { describe, expect, it } from 'vitest';
import { prepareVariantGroup, shortVariantLabel, variantImportance } from './viewModeShortLabels';

const NBSP = '\u00A0';

describe('shortVariantLabel', () => {
  it('сокращает канцелярские русские названия, не обрывая слова', () => {
    expect(shortVariantLabel('Государственный долг сектора государственного управления')).toBe('Госдолг');
    expect(shortVariantLabel('Государственный долг сектора государственного уп')).toBe('Госдолг');
    expect(shortVariantLabel('Баланс бюджета сектора государственного управлен')).toBe('Баланс бюджета');
    expect(shortVariantLabel('Валовой внутренний продукт в текущих ценах')).toBe('ВВП');
    expect(shortVariantLabel('Валовой внутренний продукт на душу населения в т')).toBe(`ВВП на душу${NBSP}населения`);
    expect(shortVariantLabel('Численность населения')).toBe('Население');
    expect(shortVariantLabel('Изменение потребительских цен за год')).toBe('Инфляция за год');
  });

  it('подпись «% от рабочей силы» получает объект: безработица', () => {
    expect(shortVariantLabel('% от рабочей силы')).toBe('Безработица');
    expect(shortVariantLabel('% ЭАН')).toBe('Безработица');
  });

  it('оставляет короткие названия и ставит заглавную букву', () => {
    expect(shortVariantLabel('все возрасты')).toBe('Все возрасты');
    expect(shortVariantLabel('Безработица')).toBe('Безработица');
  });

  it('сокращает английские названия и пишет с заглавной', () => {
    expect(shortVariantLabel('Gross domestic product, current prices', 'en')).toBe('GDP');
    expect(shortVariantLabel('Gross domestic product per capita, current prices', 'en')).toBe('GDP per capita');
    expect(shortVariantLabel('General government gross debt', 'en')).toBe('Government debt');
    expect(shortVariantLabel('average consumer prices', 'en')).toBe('Average consumer prices');
  });
});

describe('prepareVariantGroup', () => {
  const group = {
    label: 'Что показать',
    codes: [
      { code: 'a', label: 'Государственный долг сектора государственного управления' },
      { code: 'b', label: 'Численность населения' },
      { code: 'c', label: 'Валовой внутренний продукт в текущих ценах' },
      { code: 'd', label: 'Валовой внутренний продукт на душу населения' },
      { code: 'e', label: 'Баланс бюджета сектора государственного управления' },
    ],
  };

  it('сортирует по важности, короткое имя в чипе, полное в title', () => {
    const out = prepareVariantGroup(group);
    expect(out.codes.map((c) => c.code)).toEqual(['c', 'd', 'b', 'e', 'a']);
    const debt = out.codes.find((c) => c.code === 'a');
    expect(debt.short).toBe('Госдолг');
    expect(debt.title).toBe('Государственный долг сектора государственного управления');
    expect(debt.label).toBe('Государственный долг сектора государственного управления');
  });

  it('не меняет исходную группу', () => {
    prepareVariantGroup(group);
    expect(group.codes[0].code).toBe('a');
    expect(group.codes[0].short).toBeUndefined();
  });

  it('одинаковые короткие имена остаются полными', () => {
    const out = prepareVariantGroup({
      label: 'x',
      codes: [
        { code: 'a', label: 'Валовой внутренний продукт в текущих ценах' },
        { code: 'b', label: 'Валовой внутренний продукт в текущих ценах, млрд' },
      ],
    });
    expect(out.codes.every((c) => c.short === undefined)).toBe(true);
  });

  it('без группы возвращает то же значение', () => {
    expect(prepareVariantGroup(null)).toBeNull();
  });
});

describe('variantImportance', () => {
  it('ВВП раньше инфляции, инфляция раньше госдолга', () => {
    expect(variantImportance('Валовой внутренний продукт')).toBeLessThan(variantImportance('Изменение потребительских цен'));
    expect(variantImportance('Изменение потребительских цен')).toBeLessThan(variantImportance('Государственный долг'));
    expect(variantImportance('Что-то редкое')).toBe(50);
  });
});
