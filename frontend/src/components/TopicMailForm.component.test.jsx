// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import TopicMailForm from './TopicMailForm';
import { resetTopicMailConfig } from '../lib/topicMail';
import AfterDownloadOffer from './AfterDownloadOffer';
import { TopicConfirm } from '../pages/AccountMail';
import { AuthContext } from '../context/authContext';
import {
  confirmTopicMail, fetchTopicMailConfig, fetchTopicMailConfirm, subscribeTopicMail,
} from '../lib/api';
import { track } from '../lib/track';

vi.mock('../lib/api', () => ({
  fetchTopicMailConfig: vi.fn(async () => ({ enabled: true })),
  subscribeTopicMail: vi.fn(async () => ({ ok: true, status: 'confirm_sent' })),
  fetchTopicMailConfirm: vi.fn(async () => ({ ok: true, title: 'Цена дизельного топлива', email: 'a…d@example.com' })),
  confirmTopicMail: vi.fn(async () => ({
    ok: true, status: 'subscribed', title: 'Цена дизельного топлива', email: 'a…d@example.com',
    new_account: true, code: 'fuel-diesel',
  })),
}));
vi.mock('../lib/track', () => ({
  track: vi.fn(),
  events: new Proxy({}, { get: (_t, k) => String(k).toLowerCase() }),
}));
vi.mock('../lib/useMeta', () => ({ default: vi.fn() }));
const watchState = { authed: false, watching: false, loaded: true };
vi.mock('../lib/useCabinet', () => ({ useWatch: vi.fn(() => watchState) }));
vi.mock('../i18n', () => ({ useT: () => (key, vars) => (vars ? `${key}:${JSON.stringify(vars)}` : key) }));

const auth = (isAuthed) => ({ isAuthed, isLoading: false });

function at(ui, { authed = false, path = '/russia/indicator/fuel-diesel/2026' } = {}) {
  return render(
    <AuthContext.Provider value={auth(authed)}>
      <MemoryRouter initialEntries={[path]}>{ui}</MemoryRouter>
    </AuthContext.Provider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  Object.assign(watchState, { authed: false, watching: false, loaded: true });
  resetTopicMailConfig();
  window.sessionStorage.clear();
});
afterEach(cleanup);

describe('TopicMailForm', () => {
  it('draws nothing while the server flag is off', async () => {
    fetchTopicMailConfig.mockResolvedValueOnce({ enabled: false });
    const { container } = at(<TopicMailForm code="fuel-diesel" />);
    await waitFor(() => expect(fetchTopicMailConfig).toHaveBeenCalled());
    expect(container.innerHTML).toBe('');
  });

  it('guest: consent is required, then the request goes with the page and the answer is shown', async () => {
    at(<TopicMailForm code="fuel-diesel" topic="diesel" />);
    const field = await screen.findByLabelText('common.email');
    fireEvent.change(field, { target: { value: ' a@b.ru ' } });
    fireEvent.click(screen.getByRole('button', { name: 'topicMail.submit' }));
    expect(await screen.findByText('topicMail.consentRequired')).toBeTruthy();
    expect(subscribeTopicMail).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole('checkbox'));
    fireEvent.click(screen.getByRole('button', { name: 'topicMail.submit' }));
    await screen.findByTestId('topic-mail-done');
    expect(subscribeTopicMail).toHaveBeenCalledWith({
      code: 'fuel-diesel', email: 'a@b.ru', consent: true, page: expect.any(String),
    });
    expect(track).toHaveBeenCalledWith('subscribe_line_click', expect.objectContaining({ topic: 'diesel', channel: 'email' }));
    expect(screen.getByTestId('topic-mail-done').textContent).toContain('topicMail.doneGuest');
  });

  it('signed in: one button, no address field', async () => {
    subscribeTopicMail.mockResolvedValueOnce({ ok: true, status: 'subscribed', email: 'a…d@example.com' });
    at(<TopicMailForm code="fuel-diesel" />, { authed: true });
    fireEvent.click(await screen.findByTestId('topic-mail-one-click'));
    await screen.findByTestId('topic-mail-done');
    expect(subscribeTopicMail).toHaveBeenCalledWith({ code: 'fuel-diesel' });
    expect(screen.queryByLabelText('common.email')).toBeNull();
    expect(screen.getByTestId('topic-mail-done').textContent).toContain('topicMail.doneSubscribed');
  });
});

describe('AfterDownloadOffer', () => {
  const fire = (detail) => act(() => {
    window.dispatchEvent(new CustomEvent('fe:download-done', { detail }));
  });

  it('offers mail once per Russian series, never for world series', async () => {
    at(<AfterDownloadOffer />);
    await waitFor(() => expect(fetchTopicMailConfig).toHaveBeenCalled());
    await act(async () => {});
    fire({ remaining: 2, code: 'gdp', country: 'germany' });
    expect(screen.queryByTestId('after-download-offer')).toBeNull();
    fire({ remaining: 2, code: 'fuel-diesel', country: null });
    expect(await screen.findByTestId('after-download-offer')).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: 'common.close' }));
    expect(screen.queryByTestId('after-download-offer')).toBeNull();
    fire({ remaining: 1, code: 'fuel-diesel', country: null });
    expect(screen.queryByTestId('after-download-offer')).toBeNull();
  });
});

describe('TopicConfirm', () => {
  it('opening the link changes nothing; the button confirms', async () => {
    at(<Routes><Route path="/account/topic-confirm" element={<TopicConfirm />} /></Routes>,
      { path: '/account/topic-confirm?t=abc.def' });
    await screen.findByTestId('topic-confirm-ready');
    expect(fetchTopicMailConfirm).toHaveBeenCalledWith('abc.def');
    expect(confirmTopicMail).not.toHaveBeenCalled();
    fireEvent.click(screen.getByTestId('topic-confirm-button'));
    await screen.findByTestId('topic-confirm-done');
    expect(confirmTopicMail).toHaveBeenCalledWith('abc.def');
    expect(screen.getByText('topicMail.confirm.setPassword')).toBeTruthy();
  });

  it('broken link shows the error', async () => {
    fetchTopicMailConfirm.mockRejectedValueOnce({ response: { status: 400, data: { detail: { code: 'expired', message: 'Ссылка устарела' } } } });
    at(<Routes><Route path="/account/topic-confirm" element={<TopicConfirm />} /></Routes>,
      { path: '/account/topic-confirm?t=x.y' });
    expect((await screen.findByTestId('topic-confirm-error')).textContent).toContain('Ссылка устарела');
  });
});

describe('AfterDownloadOffer for a signed-in watcher', () => {
  it('is not shown when the person already watches the series (or the list is still loading)', async () => {
    Object.assign(watchState, { authed: true, watching: true, loaded: true });
    at(<AfterDownloadOffer />, { authed: true });
    await waitFor(() => expect(fetchTopicMailConfig).toHaveBeenCalled());
    await act(async () => {});
    act(() => { window.dispatchEvent(new CustomEvent('fe:download-done', { detail: { code: 'fuel-diesel' } })); });
    expect(screen.queryByTestId('after-download-offer')).toBeNull();
    expect(track).not.toHaveBeenCalledWith('download_mail_offer_view', expect.anything());

    cleanup();
    window.sessionStorage.clear();
    Object.assign(watchState, { authed: true, watching: false, loaded: false });
    at(<AfterDownloadOffer />, { authed: true });
    await act(async () => {});
    act(() => { window.dispatchEvent(new CustomEvent('fe:download-done', { detail: { code: 'cpi' } })); });
    expect(screen.queryByTestId('after-download-offer')).toBeNull();
  });
});
