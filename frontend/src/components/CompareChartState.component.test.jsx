/** @vitest-environment jsdom */
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { LocaleProvider } from '../i18n';
import CompareChartState from './CompareChartState';

afterEach(cleanup);

function renderState(props, locale) {
  return render(
    <LocaleProvider locale={locale}>
      <CompareChartState {...props} />
    </LocaleProvider>,
  );
}

describe('CompareChartState', () => {
  it('loading: busy status with an audible label and a skeleton the height of the chart', () => {
    renderState({ kind: 'loading', height: 280 });
    const box = screen.getByTestId('compare-chart-skeleton');
    expect(box.getAttribute('aria-busy')).toBe('true');
    expect(box.getAttribute('role')).toBe('status');
    expect(box.textContent).toMatch(/Загружаем ряды/);
    const plot = box.querySelector('.skeleton[style]');
    expect(plot.style.height).toBe('280px');
  });

  it('none: says that no indicators are selected, politely announced', () => {
    renderState({ kind: 'none', height: 390, message: 'Найдите и добавьте показатели.' });
    const box = screen.getByTestId('compare-empty');
    expect(box.getAttribute('data-state')).toBe('none');
    expect(box.getAttribute('role')).toBe('status');
    expect(box.getAttribute('aria-live')).toBe('polite');
    expect(box.textContent).toMatch(/Показатели не выбраны/);
    expect(box.textContent).toMatch(/Найдите и добавьте/);
    expect(screen.queryByRole('button')).toBeNull();
    // Высота состояния не меньше высоты графика: страница не подпрыгивает.
    expect(parseInt(box.style.minHeight, 10)).toBeGreaterThan(390);
  });

  it('error: assertive alert with a Retry button that calls back', () => {
    const onRetry = vi.fn();
    renderState({ kind: 'error', height: 390, message: 'Не удалось загрузить выбранные ряды.', onRetry });
    const box = screen.getByRole('alert');
    expect(box.textContent).toMatch(/Не удалось построить график/);
    fireEvent.click(screen.getByRole('button', { name: 'Повторить' }));
    expect(onRetry).toHaveBeenCalledOnce();
  });

  it('error without a network failure has no Retry button; while retrying the button is busy', () => {
    const { unmount } = renderState({ kind: 'error', message: 'Проверьте код в адресе.' });
    expect(screen.queryByRole('button')).toBeNull();
    unmount();
    renderState({ kind: 'error', message: 'x', onRetry: () => {}, retrying: true });
    const btn = screen.getByRole('button', { name: /Повторить/ });
    expect(btn.disabled).toBe(true);
    expect(btn.getAttribute('aria-busy')).toBe('true');
  });

  it('is translated in the EN storefront', () => {
    renderState({ kind: 'none', message: 'Add indicators.' }, 'en');
    expect(screen.getByText('No indicators selected')).toBeTruthy();
  });
});
