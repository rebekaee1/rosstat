// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter, Routes, Route } from 'react-router-dom';

import Register from './Register';
import Login from './Login';
import { loginUser, registerUser } from '../lib/api';
import { track } from '../lib/track';
import { rememberAuthTrigger } from '../lib/authTrigger';

vi.mock('../context/authContext', () => ({ useAuth: () => ({ setUser: vi.fn() }) }));
vi.mock('../lib/api', () => ({
  registerUser: vi.fn(),
  loginUser: vi.fn(),
  fetchOAuthProviders: vi.fn(async () => []),
  oauthStartUrl: vi.fn(() => '/oauth'),
}));
vi.mock('../lib/useMeta', () => ({ default: vi.fn() }));
vi.mock('../lib/track', () => ({
  track: vi.fn(),
  events: {
    AUTH_SIGNUP: 'signup', AUTH_LOGIN: 'login_success', NEWSLETTER_OPT_IN: 'newsletter_opt_in',
    AUTH_ERROR: 'auth_error', AUTH_FORM_ERROR: 'auth_form_error',
  },
}));
vi.mock('../i18n', () => ({
  useT: () => (key) => key,
  useLocale: () => ({ locale: 'en', t: (key) => key }),
}));

beforeEach(() => {
  vi.mocked(track).mockClear();
  vi.mocked(registerUser).mockReset();
  vi.mocked(loginUser).mockReset();
  window.sessionStorage.clear();
  window.localStorage.clear();
  document.documentElement.lang = 'ru';
});
afterEach(cleanup);

const tracked = () => vi.mocked(track).mock.calls.map(([name, params]) => [name, params]);

const renderRegister = (entry = '/register') => render(
  <MemoryRouter initialEntries={[entry]}>
    <Routes><Route path="/register" element={<Register />} /><Route path="*" element={<span>next</span>} /></Routes>
  </MemoryRouter>,
);
const renderLogin = (entry = '/login') => render(
  <MemoryRouter initialEntries={[entry]}>
    <Routes><Route path="/login" element={<Login />} /><Route path="*" element={<span>next</span>} /></Routes>
  </MemoryRouter>,
);

describe('форма регистрации', () => {
  it('у формы есть стабильное имя для воронки форм', () => {
    renderRegister();
    expect(document.querySelector('form').getAttribute('data-track')).toBe('register-email');
  });

  it('успех: signup с методом, языком, рассылкой и тем, что подтолкнуло', async () => {
    rememberAuthTrigger('download_limit');
    vi.mocked(registerUser).mockResolvedValue({ id: 'u1' });
    renderRegister();
    fireEvent.change(screen.getByLabelText('common.email'), { target: { value: 'a@b.co' } });
    fireEvent.change(screen.getByLabelText('common.password'), { target: { value: 'longpassword' } });
    fireEvent.click(screen.getAllByRole('checkbox')[0]);
    fireEvent.submit(document.querySelector('form'));
    await waitFor(() => expect(tracked().some(([name]) => name === 'signup')).toBe(true));
    const [, params] = tracked().find(([name]) => name === 'signup');
    expect(params).toMatchObject({ method: 'email', newsletter: 1, site_locale: 'ru', trigger: 'gate_download' });
    // ни почты, ни пароля в событиях нет
    expect(JSON.stringify(tracked())).not.toMatch(/a@b\.co|longpassword/);
  });

  it('без согласия: auth_form_error с полем consent, запроса на сервер нет', async () => {
    renderRegister();
    fireEvent.change(screen.getByLabelText('common.email'), { target: { value: 'a@b.co' } });
    fireEvent.change(screen.getByLabelText('common.password'), { target: { value: 'longpassword' } });
    fireEvent.submit(document.querySelector('form'));
    expect(tracked()).toContainEqual(['auth_form_error', { form: 'register', field: 'consent', code: 'required' }]);
    expect(registerUser).not.toHaveBeenCalled();
  });

  it('почта уже занята: auth_error и auth_form_error с кодами, без текста', async () => {
    vi.mocked(registerUser).mockRejectedValue({ response: { status: 409, data: { detail: 'x' } } });
    renderRegister();
    fireEvent.change(screen.getByLabelText('common.email'), { target: { value: 'a@b.co' } });
    fireEvent.change(screen.getByLabelText('common.password'), { target: { value: 'longpassword' } });
    fireEvent.click(screen.getAllByRole('checkbox')[0]);
    fireEvent.submit(document.querySelector('form'));
    await waitFor(() => expect(tracked().some(([name]) => name === 'auth_error')).toBe(true));
    expect(tracked()).toContainEqual(['auth_error', { stage: 'email_register', code: 'exists' }]);
    expect(tracked()).toContainEqual(['auth_form_error', { form: 'register', field: 'email', code: 'exists' }]);
  });
});

describe('форма входа', () => {
  it('у формы есть стабильное имя для воронки форм', () => {
    renderLogin();
    expect(document.querySelector('form').getAttribute('data-track')).toBe('login-email');
  });

  it('успех: login_success с методом и языком', async () => {
    vi.mocked(loginUser).mockResolvedValue({ id: 'u1' });
    renderLogin();
    fireEvent.change(screen.getByLabelText('common.email'), { target: { value: 'a@b.co' } });
    fireEvent.change(screen.getByLabelText('common.password'), { target: { value: 'longpassword' } });
    fireEvent.submit(document.querySelector('form'));
    await waitFor(() => expect(tracked().length).toBeGreaterThan(0));
    expect(tracked()[0]).toEqual(['login_success', { method: 'email', site_locale: 'ru' }]);
  });

  it('неверный пароль: коды ошибок без текста', async () => {
    vi.mocked(loginUser).mockRejectedValue({ response: { status: 401, data: { detail: 'bad' } } });
    renderLogin();
    fireEvent.change(screen.getByLabelText('common.email'), { target: { value: 'a@b.co' } });
    fireEvent.change(screen.getByLabelText('common.password'), { target: { value: 'wrongpass1' } });
    fireEvent.submit(document.querySelector('form'));
    await waitFor(() => expect(tracked().some(([name]) => name === 'auth_error')).toBe(true));
    expect(tracked()).toContainEqual(['auth_error', { stage: 'email_login', code: 'credentials' }]);
    expect(tracked()).toContainEqual(['auth_form_error', { form: 'login', field: 'password', code: 'credentials' }]);
  });

  it('возврат с провайдера с ошибкой: auth_error со стадией oauth_return', async () => {
    renderLogin('/login?error=oauth_denied');
    await waitFor(() => expect(tracked()).toContainEqual(['auth_error', { stage: 'oauth_return', code: 'oauth_denied' }]));
  });
});
