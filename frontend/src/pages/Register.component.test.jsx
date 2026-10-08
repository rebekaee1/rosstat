import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter, Routes, Route, useLocation } from 'react-router-dom';

import Register from './Register';

vi.mock('../context/authContext', () => ({ useAuth: () => ({ setUser: vi.fn() }) }));
vi.mock('../lib/api', () => ({
  registerUser: vi.fn(),
  fetchOAuthProviders: vi.fn(async () => ['yandex', 'vk']),
  oauthStartUrl: vi.fn(() => '/oauth'),
}));
vi.mock('../lib/useMeta', () => ({ default: vi.fn() }));
vi.mock('../lib/track', () => ({ track: vi.fn(), events: {} }));
vi.mock('../i18n', () => ({
  useT: () => (key) => key,
  useLocale: () => ({ locale: 'en', t: (key) => key }),
}));

afterEach(cleanup);

function CurrentLocation() {
  const location = useLocation();
  return <output data-testid="location">{location.pathname}{location.search}{location.hash}</output>;
}

describe('экран радости после регистрации', () => {
  it('показывает рисующуюся галочку и кнопку «Продолжить», затем ведёт на исходную страницу', async () => {
    const { registerUser } = await import('../lib/api');
    registerUser.mockResolvedValue({});
    render(
      <MemoryRouter initialEntries={['/register?next=%2Fworld%2Frating%2Fgdp-usd']}>
        <CurrentLocation />
        <Routes>
          <Route path="/register" element={<Register />} />
          <Route path="/world/rating/gdp-usd" element={<span>destination</span>} />
        </Routes>
      </MemoryRouter>,
    );
    fireEvent.change(screen.getByLabelText('common.email'), { target: { value: 'a@b.co' } });
    fireEvent.change(screen.getByLabelText('common.password'), { target: { value: 'longpassword' } });
    fireEvent.click(screen.getAllByRole('checkbox')[0]);
    fireEvent.submit(screen.getByLabelText('common.email').closest('form'));

    expect(await screen.findByText('w5.auth.welcomeTitle')).toBeTruthy();
    expect(document.querySelector('.w5-success__tick')).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: 'w5.auth.welcomeContinue' }));
    expect(await screen.findByText('destination')).toBeTruthy();
  });

  it('волна 7: три строки выгод над формой и короткая юридическая фраза', () => {
    render(<MemoryRouter initialEntries={['/register']}><Routes><Route path="/register" element={<Register />} /></Routes></MemoryRouter>);
    const items = document.querySelectorAll('.fe-w7p-benefits li');
    expect(items).toHaveLength(3);
    expect(screen.getByText('w7p.reg.legalTerms')).toBeTruthy();
  });

  it('оба согласия оформлены одним стилем (золотой чекбокс сайта)', () => {
    render(<MemoryRouter initialEntries={['/register']}><Routes><Route path="/register" element={<Register />} /></Routes></MemoryRouter>);
    const boxes = screen.getAllByRole('checkbox');
    expect(boxes).toHaveLength(2);
    for (const box of boxes) expect(box.closest('label').className).toContain('w5-consent');
  });
});

describe('согласие на рассылку по умолчанию (решение владельца 2026-10-05)', () => {
  const fill = () => {
    fireEvent.change(screen.getByLabelText('common.email'), { target: { value: 'a@b.co' } });
    fireEvent.change(screen.getByLabelText('common.password'), { target: { value: 'longpassword' } });
    fireEvent.click(screen.getAllByRole('checkbox')[0]); // политика — явное согласие
  };
  const renderRegister = () => render(
    <MemoryRouter initialEntries={['/register']}><Routes><Route path="/register" element={<Register />} /></Routes></MemoryRouter>,
  );

  it('галочка рассылки отмечена, политика — нет', () => {
    renderRegister();
    const [policy, newsletter] = screen.getAllByRole('checkbox');
    expect(policy.checked).toBe(false);
    expect(newsletter.checked).toBe(true);
  });

  it('без правок на сервер уходит newsletter: true', async () => {
    const { registerUser } = await import('../lib/api');
    registerUser.mockClear(); registerUser.mockResolvedValue({});
    renderRegister(); fill();
    fireEvent.submit(screen.getByLabelText('common.email').closest('form'));
    await waitFor(() => expect(registerUser).toHaveBeenCalledTimes(1));
    expect(registerUser).toHaveBeenCalledWith({ email: 'a@b.co', password: 'longpassword', consent: true, newsletter: true });
  });

  it('если человек снял галочку, уходит newsletter: false', async () => {
    const { registerUser } = await import('../lib/api');
    registerUser.mockClear(); registerUser.mockResolvedValue({});
    renderRegister(); fill();
    fireEvent.click(screen.getAllByRole('checkbox')[1]);
    fireEvent.submit(screen.getByLabelText('common.email').closest('form'));
    await waitFor(() => expect(registerUser).toHaveBeenCalledTimes(1));
    expect(registerUser).toHaveBeenCalledWith(expect.objectContaining({ newsletter: false }));
  });
});

describe('email fallback from unavailable Google signup', () => {
  it('keeps next, explains the temporary fallback in English, and focuses email', async () => {
    render(
      <MemoryRouter initialEntries={['/register?next=%2Fworld%2Findicator%2Fgdp-usd']}>
        <CurrentLocation />
        <Routes><Route path="/register" element={<Register />} /></Routes>
      </MemoryRouter>,
    );

    fireEvent.click(await screen.findByRole('button', { name: 'auth.oauth.googleRegister' }));

    expect(await screen.findByText('auth.register.googleUnavailable')).toBeTruthy();
    await waitFor(() => expect(screen.getByTestId('location').textContent).toContain('google_unavailable=1'));
    expect(screen.getByTestId('location').textContent).toContain('next=%2Fworld%2Findicator%2Fgdp-usd');
    expect(screen.getByTestId('location').textContent).toContain('#email');
    expect(document.activeElement).toBe(screen.getByLabelText('common.email'));
  });
});

describe('круг 8: согласие на регистрации', () => {
  it('условия и политика открываются в новой вкладке: заполненная форма не теряется', () => {
    render(
      <MemoryRouter initialEntries={['/register']}>
        <Routes>
          <Route path="/register" element={<Register />} />
        </Routes>
      </MemoryRouter>,
    );
    for (const key of ['w7p.reg.legalTerms', 'w7p.reg.legalPrivacy']) {
      const link = screen.getByRole('link', { name: key });
      expect(link.getAttribute('target')).toBe('_blank');
      expect(link.getAttribute('rel')).toContain('noopener');
    }
  });
});

