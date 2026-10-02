import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import DataTable from './DataTable';
import { LocaleProvider } from '../i18n';
import { events, track } from '../lib/track';

vi.mock('../lib/track', () => ({ track: vi.fn(), events: { TABLE_SEARCH: 'table_search', TABLE_PAGE: 'table_page', TABLE_SORT: 'table_sort' } }));

const data = [{ date: '2026-01-01', value: 1234.5 }];

function renderTable(ui) {
  return render(<LocaleProvider>{ui}</LocaleProvider>);
}

describe('DataTable', () => {
  it('может показывать единицу только в заголовке', () => {
    renderTable(
      <DataTable
        data={data}
        unit="тыс. тонн"
        valueDigits={1}
        showUnitInValues={false}
      />,
    );

    expect(screen.getByText('Значение (тыс. тонн)')).toBeTruthy();
    expect(screen.getByText('1 234,5')).toBeTruthy();
    expect(screen.queryByText('1 234,5 тыс. тонн')).toBeNull();
  });

  it('по умолчанию сохраняет единицу у значения для существующих карточек', () => {
    renderTable(<DataTable data={data} unit="%" valueDigits={1} />);
    expect(screen.getByText('1 234,5%')).toBeTruthy();
  });

  it('не оставляет пустые скобки для единиц без короткого суффикса', () => {
    renderTable(<DataTable data={data} unit="индекс" valueDigits={1} showUnitInValues={false} />);
    expect(screen.getByText('Значение')).toBeTruthy();
    expect(screen.queryByText('Значение ()')).toBeNull();
  });

  it('находит число с запятой и считает для аналитики ту же выдачу', async () => {
    renderTable(<DataTable data={[{ date: '2024-12-01', value: 16.5 }, { date: '2023-12-01', value: 6.5 }]} />);
    fireEvent.change(screen.getByRole('textbox'), { target: { value: '16,5' } });
    await waitFor(() => expect(screen.getAllByRole('row')).toHaveLength(2));
    expect(screen.getByText('16,50%')).toBeTruthy();
    expect(track).toHaveBeenCalledWith(events.TABLE_SEARCH, { query: '16,5', results: 1 });
  });

  it('сохраняет видимую строку после уменьшения данных на второй странице', () => {
    const rows = Array.from({ length: 21 }, (_, index) => ({ date: `2024-01-${String(index + 1).padStart(2, '0')}`, value: index }));
    const { rerender } = renderTable(<DataTable data={rows} dateFormat="day" />);
    fireEvent.click(screen.getByRole('button', { name: 'Вперёд' }));
    rerender(<LocaleProvider><DataTable data={[rows[0]]} dateFormat="day" /></LocaleProvider>);
    expect(screen.getAllByRole('row')).toHaveLength(2);
    expect(screen.getByText('1 января 2024')).toBeTruthy();
  });
});
