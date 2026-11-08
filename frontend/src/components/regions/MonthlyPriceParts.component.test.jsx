import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import GroupedSiblings, { CompareLines, DiscontinuedNote } from './MonthlyPriceParts';
import { LocaleProvider } from '../../i18n';

const wrap = (ui) => render(<LocaleProvider><MemoryRouter>{ui}</MemoryRouter></LocaleProvider>);

describe('MonthlyPriceParts', () => {
  it('пометка снятого ряда называет месяц', () => {
    wrap(<DiscontinuedNote lastLabel="декабрь 2017" />);
    expect(screen.getByRole('note').textContent).toContain('декабрь 2017');
  });

  it('сравнение цифрой: строки России и Москвы со знаком отклонения', () => {
    wrap(<CompareLines
      rows={[{ key: 'russia', value: 100, month: 202609, pct: 6.3 }, { key: 'moskva', value: 120, month: 202608, pct: -8 }]}
      unit="рублей за литр"
      lastMonth={202609}
    />);
    expect(screen.getByText('Россия')).toBeTruthy();
    expect(screen.getByText(/\+6,3/)).toBeTruthy();
    expect(screen.getByText(/−8,0/)).toBeTruthy();
  });

  it('«Ещё в разделе»: группа текущей первой, снятые позже живых, ссылка на регион', () => {
    const { container } = wrap(<GroupedSiblings
      slug="moskva"
      regionName="г. Москва"
      section="Цены и тарифы"
      currentGroup="Топливо"
      siblings={[
        { code: 'a', name: 'А', short_name: 'Хлеб', price_group: 'Продукты', value: 60, unit: 'рублей за кг', last_month: 202609 },
        { code: 'b', name: 'Б', short_name: 'Старый диск', price_group: 'Продукты', is_discontinued: true, last_month: 201712 },
        { code: 'c', name: 'В', short_name: 'Бензин', price_group: 'Топливо' },
      ]}
    />);
    const titles = [...container.querySelectorAll('.z2p-group__title')].map((n) => n.textContent);
    expect(titles[0]).toMatch(/Топливо/);
    const names = [...container.querySelectorAll('.z2p-row__name')].map((n) => n.textContent);
    expect(names.indexOf('Хлеб')).toBeLessThan(names.indexOf('Старый диск'));
    expect(container.querySelector('a[href="/russia/region/moskva"]')).toBeTruthy();
  });
});
