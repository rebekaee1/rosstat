import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, waitFor } from '@testing-library/react';
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
    const card = await waitFor(() => {
      const el = document.querySelector('aside.fe-nudge-m');
      expect(el).toBeTruthy();
      return el;
    });
    expect(card.querySelector('.fe-nudge-m__icon')).toBeTruthy();
    expect(card.textContent.length).toBeGreaterThan(20);
    const cta = card.querySelector('a[href*="/register"]');
    expect(cta).toBeTruthy();
  });

  it('закрытие запоминается и карточка исчезает', async () => {
    renderNudge(null);
    const card = await waitFor(() => {
      const el = document.querySelector('aside.fe-nudge-m');
      expect(el).toBeTruthy();
      return el;
    });
    fireEvent.click(card.querySelector('button[aria-label="Закрыть"]'));
    await waitFor(() => expect(document.querySelector('aside.fe-nudge-m')).toBeNull());
    expect(window.localStorage.getItem('fe_nudge_dismissed')).toBe('1');
  });

  it('на главной, входе, регистрации и в кабинете не показывается', () => {
    for (const route of ['/', '/login', '/register', '/account']) {
      const { unmount } = renderNudge(null, route);
      expect(document.querySelector('aside.fe-nudge-m')).toBeNull();
      unmount();
    }
  });
});
