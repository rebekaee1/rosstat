/** @vitest-environment jsdom */
import { afterEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { LocaleProvider } from '../i18n';
import LoadingNote from './LoadingNote';

afterEach(() => { cleanup(); vi.useRealTimers(); });

const view = (ui, locale = 'ru') => render(<LocaleProvider locale={locale}>{ui}</LocaleProvider>);

describe('LoadingNote', () => {
  it('says "Loading data" at once and shows no button yet', () => {
    view(<LoadingNote />);
    expect(screen.getByRole('status').textContent).toBe('Загружаем данные…');
    expect(screen.queryByRole('button')).toBeNull();
  });

  it('after 5 s adds a "Slower than usual" remark and a refresh button that calls onRefresh', () => {
    vi.useFakeTimers();
    const onRefresh = vi.fn();
    view(<LoadingNote onRefresh={onRefresh} />);
    act(() => { vi.advanceTimersByTime(5100); });
    expect(screen.getByRole('status').textContent).toContain('Дольше обычного.');
    fireEvent.click(screen.getByRole('button', { name: /Обновить/ }));
    expect(onRefresh).toHaveBeenCalledTimes(1);
  });

  it('does not nag before 5 s', () => {
    vi.useFakeTimers();
    view(<LoadingNote />);
    act(() => { vi.advanceTimersByTime(4900); });
    expect(screen.queryByRole('button')).toBeNull();
    expect(screen.getByRole('status').textContent).not.toContain('Дольше обычного');
  });

  it('speaks English too', () => {
    vi.useFakeTimers();
    view(<LoadingNote />, 'en');
    expect(screen.getByRole('status').textContent).toBe('Loading data…');
    act(() => { vi.advanceTimersByTime(5100); });
    expect(screen.getByRole('button', { name: /Refresh/ })).toBeTruthy();
  });
});
