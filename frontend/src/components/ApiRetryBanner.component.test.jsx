// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
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
