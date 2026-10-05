import { describe, expect, it } from 'vitest';
import { buildChartTitle } from './z4ChartTitle';

describe('buildChartTitle', () => {
  it('значения: короткое название, страна, период и единица', () => {
    expect(buildChartTitle({
      name: 'Валовой внутренний продукт в текущих ценах', place: 'США', rangeText: 'за 10 лет', unit: 'млрд $',
    })).toBe('ВВП, США: за 10 лет, млрд $');
  });

  it('другой режим: подпись режима вместо периода', () => {
    expect(buildChartTitle({
      name: 'Безработица', place: 'Германия', modeLabel: 'Изменение за год', rangeText: 'за 5 лет', unit: '%',
    })).toBe('Безработица, Германия: Изменение за год, %');
  });

  it('длинное название без сокращения: null, вызывающий оставит прежнюю подпись', () => {
    expect(buildChartTitle({
      name: 'Импорт и экспорт товаров и услуг, в текущих ценах, в миллионах евро по методике источника',
      place: 'Германия', rangeText: 'за 10 лет', unit: 'млн €',
    })).toBeNull();
  });

  it('английский: GDP и период словами', () => {
    expect(buildChartTitle({
      name: 'Gross domestic product, current prices', place: 'United States', rangeText: 'last 10 years', unit: '$ bn', locale: 'en',
    })).toBe('GDP, United States: last 10 years, $ bn');
  });

  it('без периода и единицы остаётся только предмет', () => {
    expect(buildChartTitle({ name: 'Население', place: 'Китай' })).toBe('Население, Китай');
  });
});
