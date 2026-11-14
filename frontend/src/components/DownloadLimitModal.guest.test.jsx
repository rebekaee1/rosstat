// @vitest-environment jsdom
// Стена скачивания для гостя (14.11.2026): вход через Яндекс/VK прямо в окне, сверху; почта и вход — ниже.
import { act, fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, expect, it, vi } from 'vitest';

vi.mock('../context/authContext', () => ({ useAuth: () => ({ isAuthed: false }) }));
vi.mock('../lib/api', () => ({
  exportTable: vi.fn(),
  fetchOAuthProviders: vi.fn(async () => ['yandex', 'vk']),
  oauthStartUrl: vi.fn((id, opts) => `/api/v1/auth/oauth/${id}/start?next=${encodeURIComponent(opts.next)}`),
}));
vi.mock('../lib/track', () => ({ trackFile: vi.fn(), track: vi.fn(), events: {} }));
vi.mock('../i18n', () => ({
  useT: () => (key) => key,
  useLocale: () => ({ locale: 'ru', t: (key) => key }),
}));

import DownloadLimitModal from './DownloadLimitModal';

beforeEach(() => {
  history.replaceState(null, '', '/russia/indicator/fuel-diesel');
});

async function openWall() {
  render(<MemoryRouter initialEntries={['/russia/indicator/fuel-diesel']}><DownloadLimitModal /></MemoryRouter>);
  await act(async () => { window.dispatchEvent(new Event('fe:download-limit')); });
}

it('shows one-tap social sign-in at the top, then email and login', async () => {
  await openWall();
  const yandex = await screen.findByRole('button', { name: /auth\.oauth\.yandex/ });
  const vk = screen.getByRole('button', { name: /auth\.oauth\.vk/ });
  const email = screen.getByRole('link', { name: 'download.limit.email' });
  const login = screen.getByRole('link', { name: 'download.limit.haveAccount' });
  // Порядок в окне: соцсети выше почты и входа.
  expect(yandex.compareDocumentPosition(email) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  expect(vk.compareDocumentPosition(login) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  expect(screen.getByTestId('download-limit-benefits').querySelectorAll('li')).toHaveLength(3);
  expect(screen.getByText('download.limit.lead')).toBeTruthy();
  expect(email.getAttribute('href')).toContain('/register?next=');
});

it('remembers the return point before leaving for the provider', async () => {
  await openWall();
  const leave = vi.fn();
  window.addEventListener('fe:auth-leave', leave);
  const assign = vi.fn();
  Object.defineProperty(window, 'location', { value: { ...window.location, set href(v) { assign(v); } }, configurable: true });
  fireEvent.click(await screen.findByRole('button', { name: /auth\.oauth\.yandex/ }));
  // Окно согласия: галочка политики обязательна, рассылка по умолчанию включена (решение владельца).
  const boxes = await screen.findAllByRole('checkbox');
  const newsletter = boxes.find((box) => box.checked);
  expect(newsletter).toBeTruthy();
  fireEvent.click(boxes.find((box) => !box.checked));
  fireEvent.click(screen.getByRole('button', { name: 'common.continue' }));
  expect(leave).toHaveBeenCalled();
  expect(assign).toHaveBeenCalledWith(expect.stringContaining('/oauth/yandex/start?next=%2Frussia%2Findicator%2Ffuel-diesel'));
  window.removeEventListener('fe:auth-leave', leave);
});
