import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, fireEvent, waitFor } from '@testing-library/react';
import RegisterNudge from './RegisterNudge';
import { mockApiGet, renderPage } from '../test/renderPage';
import { isDownloadablePath, NUDGE_ACTIONS_KEY, shouldOfferNudge } from '../lib/registerNudge';

beforeEach(() => {
  window.localStorage.clear();
  window.sessionStorage.clear();
});
afterEach(() => vi.restoreAllMocks());

const DATA_PAGE = '/russia/indicator/cpi';

function renderNudge(user, route = DATA_PAGE, { actions = 2 } = {}) {
  if (actions) window.sessionStorage.setItem(NUDGE_ACTIONS_KEY, String(actions));
  mockApiGet([['/auth/me', { user }]]);
  return renderPage(<RegisterNudge />, { path: '*', route });
}

async function findCard() {
  return waitFor(() => {
    const el = document.querySelector('aside.fe-nudge-m');
    expect(el).toBeTruthy();
    return el;
  });
}

describe('RegisterNudge (карточка на телефоне)', () => {
  it('одинокая «Зарегистрироваться ✕» заменена карточкой: значок, выгода одной фразой, кнопка и закрытие', async () => {
    renderNudge(null);
    const card = await findCard();
    expect(card.querySelector('.fe-nudge-m__icon')).toBeTruthy();
    expect(card.textContent.length).toBeGreaterThan(20);
    const cta = card.querySelector('a[href*="/register"]');
    expect(cta).toBeTruthy();
  });

  it('заголовок про выгоду и одна короткая фраза, без «рассылки» как преимущества', async () => {
    renderNudge(null);
    const card = await findCard();
    expect(card.querySelector('.fe-nudge-m__title').textContent).toBe('Скачивайте данные бесплатно');
    expect(card.querySelector('.fe-nudge-m__sub').textContent).toBe('Зарегистрируйтесь — это займёт минуту.');
    expect(card.textContent).not.toMatch(/рассылк/i);
  });

  it('закрытие запоминается и карточка исчезает', async () => {
    renderNudge(null);
    const card = await findCard();
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

describe('RegisterNudge (волна 6: не просим регистрацию раньше времени)', () => {
  it('не показывается, пока человек не сделал второе действие', async () => {
    renderNudge(null, DATA_PAGE, { actions: 0 });
    await act(async () => { await Promise.resolve(); });
    expect(document.querySelector('aside.fe-nudge-m')).toBeNull();
    expect(document.querySelector('[data-testid="nudge-fab"]')).toBeNull();
  });

  it('не показывается на информационных страницах и в календаре, даже после нескольких действий', async () => {
    for (const route of ['/about', '/methodology', '/privacy', '/russia/calendar', '/russia/category/prices']) {
      const { unmount } = renderNudge(null, route, { actions: 5 });
      await act(async () => { await Promise.resolve(); });
      expect(document.querySelector('aside.fe-nudge-m'), route).toBeNull();
      unmount();
    }
  });

  it('первая попытка скачать показывает приглашение сразу', async () => {
    renderNudge(null, DATA_PAGE, { actions: 0 });
    act(() => { window.dispatchEvent(new CustomEvent('fe:download-limit')); });
    await findCard();
  });

  it('на планшете и компьютере свёрнутый вид — маленькая кнопка-значок, зона нажатия на месте, по нажатию раскрывается', async () => {
    renderNudge(null);
    const fab = await waitFor(() => {
      const el = document.querySelector('[data-testid="nudge-fab"]');
      expect(el).toBeTruthy();
      return el;
    });
    expect(fab.getAttribute('aria-label')).toBe('Скачивание — после регистрации');
    expect(fab.textContent.trim()).toBe('');
    fireEvent.click(fab);
    expect(document.querySelector('.fe-nudge-desk a[href*="/register"]')).toBeTruthy();
    fireEvent.click(document.querySelector('.fe-nudge-desk button[aria-label="Свернуть"]'));
    expect(document.querySelector('[data-testid="nudge-fab"]')).toBeTruthy();
  });
});

describe('lib/registerNudge', () => {
  it('различает страницы, где есть что скачать', () => {
    for (const path of ['/russia/indicator/cpi', '/germany/indicator/gdp', '/currencies/indicator/usd', '/world/rating/gdp-usd', '/compare', '/russia/region/moscow/grp']) {
      expect(isDownloadablePath(path), path).toBe(true);
    }
    for (const path of ['/', '/about', '/methodology', '/russia/calendar', '/germany', '/russia', '/calculator']) {
      expect(isDownloadablePath(path), path).toBe(false);
    }
  });

  it('shouldOfferNudge: после двух действий или первой попытки скачать, и только на странице с данными', () => {
    expect(shouldOfferNudge({ actions: 1, pathname: '/compare' })).toBe(false);
    expect(shouldOfferNudge({ actions: 2, pathname: '/compare' })).toBe(true);
    expect(shouldOfferNudge({ actions: 0, downloadAttempted: true, pathname: '/compare' })).toBe(true);
    expect(shouldOfferNudge({ actions: 9, pathname: '/about' })).toBe(false);
    expect(shouldOfferNudge({ actions: 2, pathname: '/about', requireDownloadable: false })).toBe(true);
  });
});
