// Круг 10, зона «страница показателя», С1: прогноз и методология выровнены по краям таблицы.
import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';

const z4 = readFileSync(new URL('./z4-indicator.css', import.meta.url), 'utf8');
const russia = readFileSync(new URL('./indicator-russia.css', import.meta.url), 'utf8');

describe('круг 10 С1: низ страницы показателя', () => {
  it('с прогнозом: таблица и прогноз поровну в первом ряду, методология вторым рядом на всю ширину', () => {
    expect(z4).toMatch(/\[data-lower='wide'\] \{[^}]*grid-template-columns: minmax\(0, 1fr\) minmax\(0, 1fr\);[^}]*grid-template-areas: 'table aside' 'method method';[^}]*align-items: stretch/);
  });

  it('карточка прогноза тянется до низа ряда, пустого места под ней нет', () => {
    expect(z4).toMatch(/\[data-block='forecast'\] > \.k5-table \{ flex: 1 1 auto; \}/);
    expect(z4).toMatch(/\.fe-datatable \.k5-seam--top \{ margin-top: auto; \}/);
  });

  it('без прогноза: прежняя колонка справа, таблица на всю высоту слева', () => {
    expect(z4).toMatch(/\[data-lower='stack'\] \{[^}]*grid-template-areas: 'table aside' 'table method' 'table \.'/);
  });

  it('на планшете и телефоне прогноз выше таблицы, методология в самом низу', () => {
    expect(z4).toMatch(/\.z4-lower__aside \{[^}]*order: 1;/);
    expect(z4).toMatch(/\.z4-lower__table \{ min-width: 0; order: 2; \}/);
    expect(z4).toMatch(/\.z4-lower__method \{ min-width: 0; order: 3; \}/);
  });

  it('старая сетка «методология 1fr + прогноз 2fr» удалена', () => {
    expect(russia).not.toMatch(/\.fe-info-grid/);
  });
});
