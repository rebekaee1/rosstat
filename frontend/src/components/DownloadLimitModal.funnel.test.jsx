// @vitest-environment jsdom
// Воронка стены (20.11.2026): кнопки окна лимита и закрытие без действия видны в аналитике.
import { act, fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, expect, it, vi } from 'vitest';

const track = vi.fn();
vi.mock('../context/authContext', () => ({ useAuth: () => ({ isAuthed: false }) }));
vi.mock('../lib/api', () => ({
  exportTable: vi.fn(),
  fetchOAuthProviders: vi.fn(async () => ['yandex']),
  oauthStartUrl: vi.fn(() => '/x'),
}));
vi.mock('../lib/track', () => ({
  trackFile: vi.fn(),
  track: (...args) => track(...args),
  events: { LIMIT_MODAL_REGISTER: 'limit_modal_register', LIMIT_MODAL_CLOSE: 'limit_modal_close' },
}));
vi.mock('../i18n', () => ({
  useT: () => (key) => key,
  useLocale: () => ({ locale: 'ru', t: (key) => key }),
}));

import DownloadLimitModal from './DownloadLimitModal';

beforeEach(() => {
  track.mockClear();
  history.replaceState(null, '', '/russia/indicator/cpi');
});

async function openWall() {
  render(<MemoryRouter initialEntries={['/russia/indicator/cpi']}><DownloadLimitModal /></MemoryRouter>);
  await act(async () => { window.dispatchEvent(new Event('fe:download-limit')); });
  await screen.findByRole('button', { name: /auth\.oauth\.yandex/ });
}

it('counts the email and login buttons as a registration click', async () => {
  await openWall();
  fireEvent.click(screen.getByRole('link', { name: 'download.limit.email' }));
  expect(track).toHaveBeenCalledWith('limit_modal_register', { target: 'email' });
  expect(track).not.toHaveBeenCalledWith('limit_modal_close', expect.anything());
});

it('records closing the wall without an action, and how', async () => {
  await openWall();
  fireEvent.click(screen.getByRole('button', { name: 'common.close' }));
  expect(track).toHaveBeenCalledWith('limit_modal_close', { via: 'x' });
  expect(screen.queryByRole('dialog')).toBeNull();

  await act(async () => { window.dispatchEvent(new Event('fe:download-limit')); });
  fireEvent.keyDown(window, { key: 'Escape' });
  expect(track).toHaveBeenCalledWith('limit_modal_close', { via: 'escape' });
});
