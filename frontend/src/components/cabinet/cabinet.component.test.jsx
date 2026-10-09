// @vitest-environment jsdom
import { render, screen, fireEvent, waitFor, cleanup } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const api = vi.hoisted(() => ({
  fetchCabinetConfig: vi.fn(),
  listSaved: vi.fn(),
  saveItem: vi.fn(),
  deleteSavedByKey: vi.fn(),
  listWatches: vi.fn(),
  addWatch: vi.fn(),
  deleteWatchByKey: vi.fn(),
  importSaved: vi.fn(),
}));
const auth = vi.hoisted(() => ({ value: { user: null, isAuthed: false, isLoading: false } }));
vi.mock('../../lib/cabinetApi', () => api);
vi.mock('../../context/authContext', () => ({ useAuth: () => auth.value }));

const store = await import('../../lib/cabinetStore');
const { default: SaveButton } = await import('./SaveButton');
const { default: WatchButton } = await import('./WatchButton');
const { default: FeedBadge } = await import('./FeedBadge');

const ENABLED = { enabled: true, features: {}, limits: { saved: 200, watches: 50 } };
const guest = { user: null, isAuthed: false, isLoading: false };
const signedIn = { user: { id: 'u1', email: 'a@b.c' }, isAuthed: true, isLoading: false };

beforeEach(() => {
  vi.clearAllMocks();
  window.localStorage.clear();
  window.sessionStorage.clear();
  store.__resetCabinetStore();
  auth.value = guest;
  api.fetchCabinetConfig.mockResolvedValue(ENABLED);
  api.listSaved.mockResolvedValue({ items: [] });
  api.listWatches.mockResolvedValue({ items: [], limit: 50 });
});
afterEach(cleanup);

const renderIn = (ui) => render(<MemoryRouter>{ui}</MemoryRouter>);

describe('SaveButton', () => {
  it('при выключенном кабинете не рисуется совсем', async () => {
    api.fetchCabinetConfig.mockResolvedValue({ enabled: false, features: {}, limits: {} });
    const { container } = renderIn(<SaveButton kind="country" itemKey="turkey" title="Турция" />);
    await waitFor(() => expect(api.fetchCabinetConfig).toHaveBeenCalled());
    await new Promise((r) => setTimeout(r, 10));
    expect(container.innerHTML).toBe('');
  });

  it('без провайдеров входа и запросов работает как гость', async () => {
    renderIn(<SaveButton kind="country" itemKey="turkey" title="Турция" />);
    const btn = await screen.findByRole('button', { name: 'c11b.save.addAria' });
    expect(btn.getAttribute('aria-pressed')).toBe('false');
  });

  it('гость сохраняет в браузере и видит приглашение войти', async () => {
    renderIn(<SaveButton kind="country" itemKey="turkey" title="Турция" />);
    fireEvent.click(await screen.findByRole('button', { name: 'c11b.save.addAria' }));
    await screen.findByText('c11b.tip.guestSaved');
    expect(screen.getByText('c11b.tip.signIn').getAttribute('href')).toMatch(/^\/login\?next=/);
    expect(JSON.parse(window.localStorage.getItem(store.GUEST_KEY))[0]).toMatchObject({ kind: 'country', item_key: 'turkey', title: 'Турция' });
    expect(api.saveItem).not.toHaveBeenCalled();
    expect(screen.getByRole('button', { name: 'c11b.save.removeAria' }).getAttribute('aria-pressed')).toBe('true');
  });

  it('вошедший сохраняет в кабинете и может убрать', async () => {
    auth.value = signedIn;
    api.saveItem.mockResolvedValue({ item: { id: 's1', kind: 'country', item_key: 'turkey', title: 'Турция' }, created: true });
    api.deleteSavedByKey.mockResolvedValue({ ok: true });
    const onChange = vi.fn();
    renderIn(<SaveButton kind="country" itemKey="turkey" title="Турция" onChange={onChange} />);
    fireEvent.click(await screen.findByRole('button', { name: 'c11b.save.addAria' }));
    await waitFor(() => expect(onChange).toHaveBeenCalledWith(true));
    expect(api.saveItem).toHaveBeenCalledWith(expect.objectContaining({ kind: 'country', itemKey: 'turkey', title: 'Турция' }));
    expect(screen.queryByText('c11b.tip.guestSaved')).toBeNull();
    fireEvent.click(await screen.findByRole('button', { name: 'c11b.save.removeAria' }));
    await waitFor(() => expect(api.deleteSavedByKey).toHaveBeenCalledWith('country', 'turkey'));
  });

  it('предел показывает подсказку и не оставляет звёздочку включённой', async () => {
    auth.value = signedIn;
    api.saveItem.mockRejectedValue({ response: { status: 409, data: { detail: { code: 'limit_reached' } } } });
    renderIn(<SaveButton kind="country" itemKey="turkey" title="Турция" />);
    fireEvent.click(await screen.findByRole('button', { name: 'c11b.save.addAria' }));
    await screen.findByText('c11b.save.limit');
    expect(screen.getByRole('button', { name: 'c11b.save.addAria' }).getAttribute('aria-pressed')).toBe('false');
  });

  it('вариант с подписью показывает слово', async () => {
    renderIn(<SaveButton kind="comparison" itemKey="codes=a,b" variant="button" />);
    expect((await screen.findByRole('button')).textContent).toContain('c11b.save.add');
  });
});

describe('WatchButton', () => {
  it('гость получает приглашение войти, сервер не трогается', async () => {
    renderIn(<WatchButton subjectKind="indicator" subjectKey="cpi_yoy" />);
    fireEvent.click(await screen.findByRole('button', { name: 'c11b.watch.onAriaPlain' }));
    await screen.findByText('c11b.tip.watchGuest');
    expect(api.addWatch).not.toHaveBeenCalled();
  });

  it('вошедший включает и выключает слежение', async () => {
    auth.value = signedIn;
    api.addWatch.mockResolvedValue({ item: { id: 'w1', subject_kind: 'indicator', subject_key: 'cpi_yoy', is_new: false }, created: true });
    api.deleteWatchByKey.mockResolvedValue({ ok: true });
    renderIn(<WatchButton subjectKind="indicator" subjectKey="cpi_yoy" />);
    const on = await screen.findByRole('button', { name: 'c11b.watch.onAriaPlain' });
    await waitFor(() => expect(on.disabled).toBe(false));
    fireEvent.click(on);
    await screen.findByText('c11b.tip.watchOn');
    fireEvent.click(await screen.findByRole('button', { name: 'c11b.watch.offAriaPlain' }));
    await waitFor(() => expect(api.deleteWatchByKey).toHaveBeenCalledWith('indicator', 'cpi_yoy'));
  });

  it('ряд, которого нет в каталоге, даёт понятную ошибку', async () => {
    auth.value = signedIn;
    api.addWatch.mockRejectedValue({ response: { status: 404, data: { detail: { code: 'subject_not_found' } } } });
    renderIn(<WatchButton subjectKind="world" subjectKey="nope" />);
    const btn = await screen.findByRole('button', { name: 'c11b.watch.onAriaPlain' });
    await waitFor(() => expect(btn.disabled).toBe(false));
    fireEvent.click(btn);
    await screen.findByText('c11b.err.subjectGone');
  });
});

describe('FeedBadge', () => {
  it('показывает число нового только вошедшему при включённом кабинете', async () => {
    api.listWatches.mockResolvedValue({
      items: [{ id: 'w1', subject_kind: 'indicator', subject_key: 'a', is_new: true }, { id: 'w2', subject_kind: 'indicator', subject_key: 'b', is_new: true }],
      limit: 50,
    });
    auth.value = signedIn;
    renderIn(<FeedBadge />);
    const badge = await screen.findByRole('status');
    expect(badge.textContent).toBe('2');
    expect(badge.getAttribute('data-c11b')).toBe('feed-badge');
  });

  it('у гостя не рисуется и список слежения не запрашивается', async () => {
    const { container } = renderIn(<FeedBadge />);
    await new Promise((r) => setTimeout(r, 10));
    expect(container.innerHTML).toBe('');
    expect(api.listWatches).not.toHaveBeenCalled();
  });
});
