// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import ApiRetryBanner from './ApiRetryBanner';

vi.mock('../lib/track', () => ({ track: vi.fn(), events: { API_RETRY: 'api_retry' } }));
vi.mock('../i18n', () => ({ useT: () => (key) => key }));

afterEach(cleanup);

describe('ApiRetryBanner', () => {
  it('announces the error and retries on click', () => {
    const onRetry = vi.fn();
    render(<ApiRetryBanner onRetry={onRetry} isFetching={false}>Нет данных</ApiRetryBanner>);
    expect(screen.getByRole('alert').textContent).toContain('Нет данных');
    fireEvent.click(screen.getByRole('button', { name: 'common.retry' }));
    expect(onRetry).toHaveBeenCalledOnce();
  });

  it('wave 6: retries once silently, shows a calm caption meanwhile and only then the alert', () => {
    vi.useFakeTimers();
    try {
      const onRetry = vi.fn();
      const view = render(<ApiRetryBanner onRetry={onRetry} isFetching={false} autoRetries={1}>Нет данных</ApiRetryBanner>);
      expect(screen.queryByRole('alert')).toBeNull();
      expect(screen.getByTestId('retry-quiet').textContent).toContain('w6a.loading.caption');
      expect(document.documentElement.hasAttribute('data-fe-error')).toBe(false);
      act(() => { vi.advanceTimersByTime(950); });
      expect(onRetry).toHaveBeenCalledTimes(1);
      // повтор пошёл и закончился, ошибка осталась: плашка с кнопкой «Повторить»
      view.rerender(<ApiRetryBanner onRetry={onRetry} isFetching autoRetries={1}>Нет данных</ApiRetryBanner>);
      expect(screen.queryByRole('alert')).toBeNull();
      view.rerender(<ApiRetryBanner onRetry={onRetry} isFetching={false} autoRetries={1}>Нет данных</ApiRetryBanner>);
      expect(screen.getByRole('alert').textContent).toContain('Нет данных');
      expect(screen.getByRole('button', { name: 'common.retry' })).toBeTruthy();
      expect(document.documentElement.hasAttribute('data-fe-error')).toBe(true);
      view.unmount();
      expect(document.documentElement.hasAttribute('data-fe-error')).toBe(false);
    } finally {
      vi.useRealTimers();
    }
  });

  it('wave 6: when the page gives no fetching signal the alert still appears after the grace period', () => {
    vi.useFakeTimers();
    try {
      render(<ApiRetryBanner onRetry={vi.fn()} autoRetries={1}>Нет данных</ApiRetryBanner>);
      expect(screen.queryByRole('alert')).toBeNull();
      act(() => { vi.advanceTimersByTime(9100); });
      expect(screen.getByRole('alert')).toBeTruthy();
    } finally {
      vi.useRealTimers();
    }
  });

  it('shows a spinner next to the loading text and blocks repeated clicks', () => {
    const onRetry = vi.fn();
    const { container } = render(<ApiRetryBanner onRetry={onRetry} isFetching>Нет данных</ApiRetryBanner>);
    const button = screen.getByRole('button', { name: 'common.loading' });
    expect(button.getAttribute('aria-busy')).toBe('true');
    expect(button.disabled).toBe(true);
    expect(container.querySelector('.fe-spinner')).toBeTruthy();
    fireEvent.click(button);
    expect(onRetry).not.toHaveBeenCalled();
  });
});
