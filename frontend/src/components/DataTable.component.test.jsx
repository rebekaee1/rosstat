import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import DataTable from './DataTable';

const data = [{ date: '2026-01-01', value: 1234.5 }];

describe('DataTable', () => {
  it('может показывать единицу только в заголовке', () => {
    render(
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
    render(<DataTable data={data} unit="%" valueDigits={1} />);
    expect(screen.getByText('1 234,5%')).toBeTruthy();
  });

  it('не оставляет пустые скобки для единиц без короткого суффикса', () => {
    render(<DataTable data={data} unit="индекс" valueDigits={1} showUnitInValues={false} />);
    expect(screen.getByText('Значение')).toBeTruthy();
    expect(screen.queryByText('Значение ()')).toBeNull();
  });
});
