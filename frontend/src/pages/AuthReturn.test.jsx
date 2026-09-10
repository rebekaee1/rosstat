// @vitest-environment jsdom
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter, Routes, Route, useLocation } from 'react-router-dom';
import { describe, it, expect, vi } from 'vitest';
import Login from './Login';
import Register from './Register';
vi.mock('../lib/useMeta', () => ({ default: () => {} }));
vi.mock('../context/authContext', () => ({ useAuth: () => ({ setUser: vi.fn() }) }));
vi.mock('../lib/api', () => ({ loginUser: vi.fn(async () => ({})), registerUser: vi.fn(async () => ({})) }));
vi.mock('../lib/track', () => ({ track: vi.fn(), events: {} }));
vi.mock('../i18n', () => ({ useT: () => key => key }));
vi.mock('../components/OAuthButtons', () => ({ default: ({ next }) => <output data-testid="oauth-next">{next}</output> }));
function Destination() { const l = useLocation(); return <output data-testid="destination">{l.pathname + l.search + l.hash}</output>; }
describe('email and OAuth share selected return destination', () => {
  for (const [page, Component] of [['login', Login], ['register', Register]]) {
    it(page, async () => {
      const next = '/indicator/cpi?mode=inflation&year=2025#chart';
      render(<MemoryRouter initialEntries={[`/${page}?next=${encodeURIComponent(next)}`]}><Routes><Route path={`/${page}`} element={<Component />} /><Route path="/indicator/cpi" element={<Destination />} /></Routes></MemoryRouter>);
      expect(screen.getByTestId('oauth-next').textContent).toBe(next);
      fireEvent.change(screen.getByLabelText('common.email'), { target: { value: 'test@example.com' } });
      fireEvent.change(screen.getByLabelText('common.password'), { target: { value: 'testpassword' } });
      if (page === 'register') fireEvent.click(screen.getAllByRole('checkbox')[0]);
      fireEvent.submit(screen.getByLabelText('common.email').closest('form'));
      await waitFor(() => expect(screen.getByTestId('destination').textContent).toBe(next));
    });
  }
});
