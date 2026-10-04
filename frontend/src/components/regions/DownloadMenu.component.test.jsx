import { describe, it, expect, vi } from 'vitest';
import { fireEvent, screen } from '@testing-library/react';
import { renderPage } from '../../test/renderPage';
import DownloadMenu from './DownloadMenu';
import { evenYearTicks } from '../../lib/calcFormat';

describe('DownloadMenu', () => {
  const setup = () => {
    const onCsv = vi.fn();
    renderPage(
      <DownloadMenu items={[
        { key: 'csv', label: 'CSV', hint: 'Простая таблица', onSelect: onCsv },
        { key: 'png', label: 'Картинка', onSelect: () => {} },
      ]}
      />,
      { path: '/', route: '/' },
    );
    return { onCsv };
  };

  it('одна кнопка «Скачать»; пункты видны после открытия, выбор закрывает меню', () => {
    const { onCsv } = setup();
    const trigger = screen.getByRole('button', { name: /Скачать/ });
    expect(trigger.getAttribute('aria-expanded')).toBe('false');
    expect(screen.queryByRole('menuitem')).toBeNull();

    fireEvent.click(trigger);
    expect(trigger.getAttribute('aria-expanded')).toBe('true');
    expect(screen.getAllByRole('menuitem')).toHaveLength(2);

    fireEvent.click(screen.getByRole('menuitem', { name: /CSV/ }));
    expect(onCsv).toHaveBeenCalledTimes(1);
    expect(screen.queryByRole('menuitem')).toBeNull();
  });

  it('закрывается по Esc и по касанию вне меню', () => {
    setup();
    const trigger = screen.getByRole('button', { name: /Скачать/ });
    fireEvent.click(trigger);
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(screen.queryByRole('menuitem')).toBeNull();

    fireEvent.click(trigger);
    fireEvent.pointerDown(document.body);
    expect(screen.queryByRole('menuitem')).toBeNull();
  });
});

describe('evenYearTicks', () => {
  it('подписи оси лет — через равные промежутки', () => {
    expect(evenYearTicks(20)).toEqual([0, 5, 10, 15, 20]);
    expect(evenYearTicks(17)).toEqual([0, 5, 10, 15]);
    expect(evenYearTicks(8)).toEqual([0, 2, 4, 6, 8]);
    expect(evenYearTicks(40)).toEqual([0, 10, 20, 30, 40]);
    expect(evenYearTicks(5)).toEqual([0, 1, 2, 3, 4, 5]);
    expect(evenYearTicks(0)).toEqual([0]);
  });
});
