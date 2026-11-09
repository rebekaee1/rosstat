import { describe, expect, it } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { goodsSubgroup, splitGoods } from './RegionPricesSubgroups';
import { RegionPriceSection } from './RegionPrices';
import { LocaleProvider } from '../../i18n';

const mk = (code, name, group) => ({ code, name, short_name: name, price_group: group, price_group_label: group, value: 10, prev_value: 9, unit: '₽', year: 2026 });

describe('R8-B: подгруппы «Одежда и товары»', () => {
  it('раскладывает позиции по смыслу', () => {
    expect(goodsSubgroup({ short_name: 'Блузка женская' })).toBe('clothes');
    expect(goodsSubgroup({ short_name: 'Кроссовки для взрослых, пара' })).toBe('shoes');
    expect(goodsSubgroup({ short_name: 'Колготки детские' })).toBe('kids');
    expect(goodsSubgroup({ short_name: 'Холодильник двухкамерный отечественный' })).toBe('tech');
    expect(goodsSubgroup({ short_name: 'Краска для волос' })).toBe('care');
    expect(goodsSubgroup({ short_name: 'Нечто странное' })).toBe('other');
  });

  it('ничего не теряет и держит порядок', () => {
    const items = ['Диван-кровать', 'Смартфон', 'Мыло', 'Блузка женская', 'Нечто'].map((n, i) => mk(`c${i}`, n, 'Одежда и товары'));
    const parts = splitGoods(items);
    expect(parts.reduce((n, p) => n + p.items.length, 0)).toBe(5);
    expect(parts.map((p) => p.key)).toEqual(['home', 'tech', 'care', 'clothes', 'other']);
  });

  it('в разделе цен показывает кнопки подгрупп и фильтрует по ним; еда, ЖКХ и лекарства — первыми', () => {
    const goods = Array.from({ length: 70 }, (_, i) => mk(`g${i}`, i % 2 ? `Диван ${i}` : `Смартфон ${i}`, 'Одежда и товары'));
    const section = {
      num: 1,
      name: 'Цены и тарифы',
      indicators: [...goods, mk('m1', 'Аспирин', 'Лекарства'), mk('f1', 'Хлеб', 'Продукты')],
    };
    render(
      <MemoryRouter>
        <LocaleProvider>
          <RegionPriceSection section={section} groupOrder={['Продукты', 'Одежда и товары', 'Лекарства']} pathFor={(c) => `/x/${c}`} searching={false} eyebrow="" />
        </LocaleProvider>
      </MemoryRouter>,
    );
    const titles = screen.getAllByRole('heading', { level: 3 }).map((h) => h.textContent);
    expect(titles[0]).toMatch(/^Продукты/);
    expect(titles[1]).toMatch(/^Лекарства/);
    const chips = screen.getByTestId('goods-subchips');
    expect(chips.textContent).toMatch(/Дом/);
    fireEvent.click(screen.getByRole('button', { name: /Дом/ }));
    expect(screen.getAllByText(/^Диван/).length).toBeGreaterThan(0);
    expect(screen.queryAllByText(/^Смартфон/).length).toBe(0);
  });
});
