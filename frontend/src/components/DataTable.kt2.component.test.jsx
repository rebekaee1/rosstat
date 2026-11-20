import { describe, expect, it, vi } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import DataTable from './DataTable';
import { LocaleProvider } from '../i18n';

vi.mock('../lib/track', () => ({
  track: vi.fn(),
  events: {
    TABLE_SEARCH: 'table_search', TABLE_PAGE: 'table_page', TABLE_SORT: 'table_sort', TABLE_JUMP: 'table_jump',
  },
}));

const renderTable = (ui) => render(<LocaleProvider>{ui}</LocaleProvider>);
const row = (re) => screen.getByRole('row', { name: re });

describe('DataTable: правки круга «Туризм», z2', () => {
  const quarterly = [
    { date: '2024-07-01', value: 200 },
    { date: '2024-10-01', value: 100 },
    { date: '2025-01-01', value: 110 },
    { date: '2025-04-01', value: 120 },
    { date: '2025-07-01', value: 250 },
    { date: '2025-10-01', value: 90 },
  ];

  it('одна колонка «к году» с подписью; сезонный квартал сравнивается с тем же кварталом прошлого года', () => {
    renderTable(<DataTable data={quarterly} unit="тыс. поездок" valueDigits={0} dateFormat="quarterly" />);
    expect(screen.getByText('К году, %')).toBeTruthy();
    expect(screen.getByText('к тому же периоду прошлого года')).toBeTruthy();
    expect(screen.queryByText(/Изменение/)).toBeNull();
    // III кв. 2025 к III кв. 2024: 250 / 200 = +25,0 %; к предыдущему кварталу было бы +108 %.
    expect(within(row(/^III кв\. 2025/)).getByText('+25,0')).toBeTruthy();
    // Нет того же квартала год назад — прочерк.
    expect(within(row(/^II кв\. 2025/)).getByText('—')).toBeTruthy();
  });

  it('годовой ряд: «к году» — предыдущий год; через пропуск лет проценты не считаются (Египет)', () => {
    const rows = [
      { date: '2014-01-01', value: 100 }, { date: '2015-01-01', value: 110 },
      { date: '2019-01-01', value: 26 }, { date: '2021-01-01', value: 1700 },
    ];
    renderTable(<DataTable data={rows} unit="тыс. поездок" valueDigits={0} dateFormat="annual" />);
    expect(screen.getByText('к предыдущему году')).toBeTruthy();
    expect(within(row(/^2015/)).getByText('+10,0')).toBeTruthy();
    expect(within(row(/^2019/)).getByText('—')).toBeTruthy();
    expect(within(row(/^2021/)).getByText('—')).toBeTruthy();
    expect(screen.queryByText(/6\s?387/)).toBeNull();
  });

  it('«максимум за всё время» ставится на ряду без пропусков и не ставится через пропуск', () => {
    const solid = Array.from({ length: 6 }, (_, i) => ({ date: `${2020 + i}-01-01`, value: [5, 9, 3, 4, 8, 6][i] }));
    const { unmount } = renderTable(<DataTable data={solid} unit="%" valueDigits={1} dateFormat="annual" />);
    expect(screen.getByText('максимум за всё время')).toBeTruthy();
    expect(screen.getByText('минимум за всё время')).toBeTruthy();
    unmount();
    const gappy = [
      { date: '2014-01-01', value: 500 }, { date: '2015-01-01', value: 780 },
      { date: '2019-01-01', value: 26 }, { date: '2020-01-01', value: 9 },
    ];
    renderTable(<DataTable data={gappy} unit="%" valueDigits={1} dateFormat="annual" />);
    expect(screen.queryByText(/максимум/)).toBeNull();
    expect(screen.queryByText(/минимум/)).toBeNull();
  });

  it('в колонке одно число знаков, а поля «От / До» заполнены действующим диапазоном', () => {
    renderTable(<DataTable data={quarterly} unit="тыс. поездок" valueDigits={0} dateFormat="quarterly" />);
    const cells = [...document.querySelectorAll('.fe-histtable__chg')].map((c) => c.textContent).filter((t) => t !== '—');
    expect(cells.length).toBeGreaterThan(1);
    cells.forEach((text) => expect(/^[+−]\d+,\d$/.test(text)).toBe(true));
    expect(screen.getByLabelText('От').value).toBe('2024-07-01');
    expect(screen.getByLabelText('До').value).toBe('2025-10-01');
  });
});
