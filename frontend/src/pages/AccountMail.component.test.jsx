// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { ForgotPassword, ResetPassword, Unsubscribe, VerifyEmail } from './AccountMail';
import {
  requestPasswordReset, resetPassword, resubscribeByLink, unsubscribeByLink, verifyEmail,
} from '../lib/api';

vi.mock('../lib/api', () => ({
  requestPasswordReset: vi.fn(async () => ({ ok: true })),
  resetPassword: vi.fn(async () => ({ ok: true })),
  verifyEmail: vi.fn(async () => ({ ok: true })),
  fetchUnsubscribeState: vi.fn(),
  unsubscribeByLink: vi.fn(async () => ({ ok: true, subscribed: false, email: 'r…a@yandex.ru' })),
  resubscribeByLink: vi.fn(async () => ({ ok: true, subscribed: true, email: 'r…a@yandex.ru' })),
}));
vi.mock('../lib/useMeta', () => ({ default: vi.fn() }));
vi.mock('../i18n', () => ({ useT: () => (key) => key }));

beforeEach(() => vi.clearAllMocks());
afterEach(cleanup);

const at = (path, element) => render(
  <MemoryRouter initialEntries={[path]}>
    <Routes><Route path={path.split('?')[0]} element={element} /></Routes>
  </MemoryRouter>,
);

describe('ссылки из писем (ADR-0032)', () => {
  it('forgot: sends the email and shows the same answer for any address', async () => {
    at('/account/forgot-password', <ForgotPassword />);
    fireEvent.change(screen.getByLabelText('common.email'), { target: { value: ' a@b.ru ' } });
    fireEvent.click(screen.getByRole('button', { name: 'mail.forgot.submit' }));
    await screen.findByTestId('forgot-sent');
    expect(requestPasswordReset).toHaveBeenCalledWith('a@b.ru');
  });

  it('reset: short password is rejected locally, then saved with the link token', async () => {
    at('/account/reset-password?t=abc.def', <ResetPassword />);
    const field = screen.getByLabelText('mail.reset.newPassword');
    fireEvent.change(field, { target: { value: 'short' } });
    fireEvent.click(screen.getByRole('button', { name: 'mail.reset.submit' }));
    expect(await screen.findByText('auth.validation.passwordShort')).toBeTruthy();
    expect(resetPassword).not.toHaveBeenCalled();
    fireEvent.change(field, { target: { value: 'longenough1' } });
    fireEvent.click(screen.getByRole('button', { name: 'mail.reset.submit' }));
    await screen.findByTestId('reset-done');
    expect(resetPassword).toHaveBeenCalledWith('abc.def', 'longenough1');
  });

  it('reset without a token says the link is broken', () => {
    at('/account/reset-password', <ResetPassword />);
    expect(screen.getByText('mail.linkBroken')).toBeTruthy();
  });

  it('verify: confirms once on open', async () => {
    at('/account/verify-email?t=tok.sig', <VerifyEmail />);
    await screen.findByTestId('verify-done');
    expect(verifyEmail).toHaveBeenCalledTimes(1);
    expect(verifyEmail).toHaveBeenCalledWith('tok.sig');
  });

  it('verify: shows the server message on a stale link', async () => {
    verifyEmail.mockRejectedValueOnce({ response: { status: 400, data: { detail: { message: 'Ссылка устарела' } } } });
    at('/account/verify-email?t=old.sig', <VerifyEmail />);
    expect((await screen.findByTestId('verify-error')).textContent).toBe('Ссылка устарела');
  });

  it('unsubscribe: one click on the link unsubscribes, the page offers to resubscribe', async () => {
    at('/account/unsubscribe?t=u.s', <Unsubscribe />);
    await screen.findByTestId('unsub-done');
    expect(unsubscribeByLink).toHaveBeenCalledWith('u.s');
    expect(screen.getByText('r…a@yandex.ru')).toBeTruthy();
    fireEvent.click(screen.getByTestId('unsub-toggle'));
    await waitFor(() => expect(screen.getByTestId('unsub-subscribed')).toBeTruthy());
    expect(resubscribeByLink).toHaveBeenCalledWith('u.s');
  });
});
