import { afterEach, describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';

const recover = vi.fn();
vi.mock('../lib/chunkRecovery', async (importOriginal) => ({
  ...(await importOriginal()),
  recoverFromStaleChunk: () => recover(),
}));
vi.mock('../lib/track', () => ({ track: vi.fn(), events: { ERROR_RELOAD: 'error_reload' } }));

import ErrorBoundary from './ErrorBoundary';

function Boom({ message }) {
  throw new TypeError(message);
}

const CHUNK_MSG = 'Failed to fetch dynamically imported module: https://x/assets/LiveTicker-abc.js';

afterEach(() => recover.mockReset());

describe('ErrorBoundary и устаревший чанк', () => {
  it('ошибка загрузки чанка запускает перезагрузку и не показывает экран ошибки', () => {
    vi.spyOn(console, 'error').mockImplementation(() => {});
    recover.mockReturnValue(true);
    const { container } = render(<ErrorBoundary><Boom message={CHUNK_MSG} /></ErrorBoundary>);
    expect(recover).toHaveBeenCalled();
    expect(container.innerHTML).toBe('');
  });

  it('перезагрузка отклонена (идёт ввод / недавно уже перезагружались) — обычный экран ошибки', () => {
    vi.spyOn(console, 'error').mockImplementation(() => {});
    recover.mockReturnValue(false);
    render(<ErrorBoundary><Boom message={CHUNK_MSG} /></ErrorBoundary>);
    expect(recover).toHaveBeenCalled();
    expect(screen.getByRole('button')).toBeTruthy();
  });

  it('обычная ошибка кода перезагрузку не запускает', () => {
    vi.spyOn(console, 'error').mockImplementation(() => {});
    render(<ErrorBoundary><Boom message="Cannot read properties of undefined" /></ErrorBoundary>);
    expect(recover).not.toHaveBeenCalled();
    expect(screen.getByRole('button')).toBeTruthy();
  });

  it('fallback={null} прячет упавший виджет без экрана ошибки', () => {
    vi.spyOn(console, 'error').mockImplementation(() => {});
    recover.mockReturnValue(false);
    render(
      <div><ErrorBoundary fallback={null}><Boom message={CHUNK_MSG} /></ErrorBoundary><p>страница жива</p></div>,
    );
    expect(screen.getByText('страница жива')).toBeTruthy();
    expect(screen.queryByRole('button')).toBeNull();
  });
});
