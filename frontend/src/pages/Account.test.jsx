// @vitest-environment jsdom
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { beforeEach, describe, it, expect, vi } from 'vitest';
import Account from './Account';
import { logoutUser, deleteAccount } from '../lib/api';
const mocks = vi.hoisted(() => ({ setUser: vi.fn(), refetch: vi.fn() }));
vi.mock('../lib/useMeta', () => ({ default: () => {} }));
vi.mock('../context/authContext', () => ({ useAuth: () => ({ user: { email: 'test@example.com', identities: [] }, isAuthed: true, ...mocks }) }));
vi.mock('../lib/api', () => ({ logoutUser: vi.fn(), deleteAccount: vi.fn(), logoutAll: vi.fn(), submitFeedback: vi.fn(), updateNewsletter: vi.fn(), updateProfile: vi.fn() }));
vi.mock('../lib/track', () => ({ track: vi.fn(), events: {} }));
vi.mock('../i18n', () => ({ useT: () => key => key }));
beforeEach(() => { vi.clearAllMocks(); vi.spyOn(window, 'confirm').mockReturnValue(true); });
describe('account session-ending actions', () => {
  for (const [label, api] of [['account.logout', logoutUser], ['account.delete', deleteAccount]]) {
    for (const success of [false, true]) it(`${label} ${success ? 'success' : 'failure'}`, async () => {
      if (success) api.mockResolvedValueOnce({}); else api.mockRejectedValueOnce(new Error('server unavailable'));
      render(<MemoryRouter initialEntries={['/account']}><Routes><Route path="/account" element={<Account />} /><Route path="/" element={<p>Home after success</p>} /></Routes></MemoryRouter>);
      fireEvent.click(screen.getByRole('button', { name: label }));
      await waitFor(() => expect(api).toHaveBeenCalledOnce());
      if (success) {
        await screen.findByText('Home after success');
        expect(mocks.setUser).toHaveBeenCalledWith(null);
      } else {
        await screen.findByText('account.errorGeneric');
        expect(mocks.setUser).not.toHaveBeenCalled();
        expect(screen.getByRole('button', { name: label })).toBeTruthy();
      }
      expect(mocks.refetch).not.toHaveBeenCalled();
    });
  }
});
