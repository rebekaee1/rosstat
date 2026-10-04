import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, screen, waitFor } from '@testing-library/react';
import RegisterNudge from './RegisterNudge';
import { mockApiGet, renderPage } from '../test/renderPage';

beforeEach(() => window.localStorage.clear());
afterEach(() => vi.restoreAllMocks());

function renderNudge(user, route = '/russia/today') {
  mockApiGet([['/auth/me', { user }]]);
  return renderPage(<RegisterNudge />, { path: '*', route });
}

describe('RegisterNudge (карточка на телефоне)', () => {
  it('одинокая «Зарегистрироваться ✕» заменена карточкой: значок, выгода одной фразой, кнопка и закрытие', async () => {
    renderNudge(null);
    const card = await screen.findByLabelText('Зачем регистрироваться');
    expect(card.textContent).toContain('Скачивайте данные в Excel и CSV');
    const cta = screen.getAllByRole('link', { name: 'Зарегистрироваться' })[0];
    expect(cta.getAttribute('href')).toContain('/register');
    expect(cta.className).toContain('fe-btn');
    expect(card.querySelector('.fe-nudge-card__icon')).toBeTruthy();
  });

  it('закрытие запоминается и карточка исчезает', async () => {
    renderNudge(null);
    const card = await screen.findByLabelText('Зачем регистрироваться');
    fireEvent.click(card.querySelector('button[aria-label="Закрыть"]'));
    await waitFor(() => expect(screen.queryByLabelText('Зачем регистрироваться')).toBeNull());
    expect(window.localStorage.getItem('fe_nudge_dismissed')).toBe('1');
  });

  it('на главной, входе, регистрации и в кабинете не показывается', () => {
    for (const route of ['/', '/login', '/register', '/account']) {
      const { unmount } = renderNudge(null, route);
      expect(screen.queryByLabelText('Зачем регистрироваться')).toBeNull();
      unmount();
    }
  });
});
