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
    // Число и единица через пробел (в разметке неразрывный): «1 234,5 %», а не «1 234,5%».
    expect(screen.getByText('1 234,5 %')).toBeTruthy();
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
    expect(screen.getByText('16,50 %')).toBeTruthy();
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

  // Пульс 2026-10-04, /russia/indicator/imoex: «Вперёд» «не реагирует на первый клик».
  // Родитель пересобирает массив data (тот же состав, новая ссылка) — раньше
  // дебаунс-эффект поиска через 250 мс сбрасывал страницу на первую.
  it('новая ссылка на те же данные не сбрасывает выбранную страницу и не шлёт лишний table_search', async () => {
    const rows = Array.from({ length: 45 }, (_, index) => ({ date: `2024-02-${String(index + 1).padStart(2, '0')}`, value: index }));
    const { rerender } = renderTable(<DataTable data={rows} dateFormat="day" />);
    await new Promise((r) => setTimeout(r, 300)); // первичный дебаунс отработал
    fireEvent.click(screen.getByRole('button', { name: 'Вперёд' }));
    expect(screen.getByText('2 / 3')).toBeTruthy();
    vi.mocked(track).mockClear();
    rerender(<LocaleProvider><DataTable data={rows.map((r) => ({ ...r }))} dateFormat="day" /></LocaleProvider>);
    await new Promise((r) => setTimeout(r, 400));
    expect(screen.getByText('2 / 3')).toBeTruthy();
    expect(track).not.toHaveBeenCalledWith(events.TABLE_SEARCH, expect.anything());
  });

  it('клик «Вперёд» сразу после монтирования не откатывается дебаунсом поиска', async () => {
    const rows = Array.from({ length: 45 }, (_, index) => ({ date: `2024-02-${String(index + 1).padStart(2, '0')}`, value: index }));
    renderTable(<DataTable data={rows} dateFormat="day" />);
    fireEvent.click(screen.getByRole('button', { name: 'Вперёд' }));
    await new Promise((r) => setTimeout(r, 400));
    expect(screen.getByText('2 / 3')).toBeTruthy();
  });

  it('поиск по-прежнему возвращает на первую страницу', async () => {
    const rows = Array.from({ length: 45 }, (_, index) => ({ date: `2024-02-${String(index + 1).padStart(2, '0')}`, value: index }));
    renderTable(<DataTable data={rows} dateFormat="day" />);
    fireEvent.click(screen.getByRole('button', { name: 'Вперёд' }));
    fireEvent.change(screen.getByRole('textbox'), { target: { value: '2024' } });
    await waitFor(() => expect(screen.getByText('1 / 3')).toBeTruthy());
  });

  it('ряд «изменение за год, %» не повторяет единицу в каждой строке: в строках «%», полная единица в заголовке (круг 9, W10)', () => {
    renderTable(<DataTable data={[{ date: '2026-01-01', value: 31.54 }]} unit="изменение за год, %" valueDigits={2} />);
    expect(screen.getByText('31,54 %')).toBeTruthy();
    expect(screen.queryByText(/изменение за год, %$/, { selector: 'td' })).toBeNull();
  });

  it('ступенчатый ряд по умолчанию показывает только дни перемен, переключатель возвращает все строки', () => {
    const rows = Array.from({ length: 60 }, (_, index) => ({
      date: new Date(Date.UTC(2026, 0, 1 + index)).toISOString().slice(0, 10),
      value: index < 30 ? 14 : 15,
    }));
    renderTable(<DataTable data={rows} dateFormat="day" unit="%" />);
    // Две перемены: первая точка и скачок с 14 на 15.
    expect(document.querySelectorAll('tbody tr')).toHaveLength(2);
    fireEvent.click(screen.getByRole('button', { name: 'Только изменения' }));
    expect(screen.getByText('1 / 3')).toBeTruthy();
  });

  it('у ряда без повторов переключателя «Только изменения» нет', () => {
    const rows = Array.from({ length: 5 }, (_, index) => ({ date: `2026-0${index + 1}-01`, value: index }));
    renderTable(<DataTable data={rows} unit="%" />);
    expect(screen.queryByRole('button', { name: 'Только изменения' })).toBeNull();
  });
});
