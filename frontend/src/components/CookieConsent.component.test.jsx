import { act, cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import { LocaleProvider } from '../i18n';
import { translate } from '../i18n/messages';
import { CONSENT_KEY, CONSENT_OPEN_EVENT, CONSENT_VERSION, getConsent } from '../lib/consent';
import { track } from '../lib/track';
import CookieConsent from './CookieConsent';

vi.mock('../lib/track', () => ({
  track: vi.fn(),
  events: { CONSENT_UPDATE: 'consent_update' },
}));

function renderConsent(locale = 'ru', path = '/') {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <LocaleProvider locale={locale}>
        <CookieConsent />
      </LocaleProvider>
    </MemoryRouter>,
  );
}

beforeEach(() => {
  window.localStorage.clear();
  window.__feApplyConsent = vi.fn();
  vi.mocked(track).mockReset();
});

afterEach(() => {
  cleanup();
  delete window.__feApplyConsent;
  vi.restoreAllMocks();
});

describe('cookie choices remain usable when measurement fails', () => {
  it.each(['ru', 'en'])('closes on one acceptance and saves the choice first (%s)', (locale) => {
    renderConsent(locale);
    expect(screen.getByText(translate('cookie.summary', undefined, locale))).toBeTruthy();
    expect(screen.queryByText(translate('cookie.bodyBefore', undefined, locale))).toBeNull();
    expect(screen.getByRole('link', { name: translate('cookie.privacyShort', undefined, locale) }).getAttribute('href')).toBe('/privacy');
    vi.mocked(track).mockImplementation(() => {
      expect(getConsent()).toMatchObject({ v: CONSENT_VERSION, analytics: true, ads: true });
    });

    fireEvent.click(screen.getByRole('button', { name: translate('cookie.accept', undefined, locale) }));

    expect(screen.queryByRole('dialog')).toBeNull();
    expect(window.__feApplyConsent).toHaveBeenCalledOnce();
    expect(track).toHaveBeenCalledExactlyOnceWith('consent_update', {
      action: 'accept_all', analytics: 1, ads: 1, policy_version: CONSENT_VERSION,
    });
  });

  it('persists and closes when applying trackers throws', () => {
    window.__feApplyConsent.mockImplementation(() => { throw new Error('tracker unavailable'); });
    renderConsent();

    fireEvent.click(screen.getByRole('button', { name: 'Хорошо' }));

    expect(screen.queryByRole('dialog')).toBeNull();
    expect(getConsent()).toMatchObject({ analytics: true, ads: true });
    expect(track).toHaveBeenCalledOnce();
  });

  it('does not commit twice when two clicks arrive before the dialog unmounts', () => {
    renderConsent();
    const accept = screen.getByRole('button', { name: 'Хорошо' });
    act(() => {
      fireEvent.click(accept);
      fireEvent.click(accept);
    });

    expect(screen.queryByRole('dialog')).toBeNull();
    expect(window.__feApplyConsent).toHaveBeenCalledOnce();
    expect(track).toHaveBeenCalledOnce();
  });

  it('closes when recording consent throws', () => {
    vi.mocked(track).mockImplementation(() => { throw new Error('measurement unavailable'); });
    renderConsent();

    fireEvent.click(screen.getByRole('button', { name: 'Хорошо' }));

    expect(screen.queryByRole('dialog')).toBeNull();
    expect(getConsent()).toMatchObject({ analytics: true, ads: true });
  });

  it('still closes if storage and both tracker paths fail', () => {
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => { throw new Error('storage blocked'); });
    window.__feApplyConsent.mockImplementation(() => { throw new Error('tracker unavailable'); });
    vi.mocked(track).mockImplementation(() => { throw new Error('measurement unavailable'); });
    renderConsent();

    fireEvent.click(screen.getByRole('button', { name: 'Хорошо' }));

    expect(screen.queryByRole('dialog')).toBeNull();
    expect(window.__feApplyConsent).toHaveBeenCalledOnce();
    expect(track).toHaveBeenCalledOnce();
  });

  it.each(['ru', 'en'])('keeps category controls and save outside the long details scroll (%s)', (locale) => {
    renderConsent(locale);
    fireEvent.click(screen.getByRole('button', { name: translate('cookie.customize', undefined, locale) }));

    const dialog = screen.getByRole('dialog');
    const body = dialog.querySelector('[data-consent-scroll-body]');
    const actions = dialog.querySelector('[data-consent-actions]');
    const [necessary, analytics, ads] = within(body).getAllByRole('checkbox');
    expect(necessary.disabled).toBe(true);
    expect(necessary.checked).toBe(true);
    expect(body.contains(actions)).toBe(false);
    expect(within(body).getByRole('link', { name: translate('cookie.privacyLink', undefined, locale) }).getAttribute('href')).toBe('/privacy');
    fireEvent.click(analytics);
    fireEvent.click(ads);
    fireEvent.click(within(actions).getByRole('button', { name: translate('cookie.save', undefined, locale) }));

    expect(screen.queryByRole('dialog')).toBeNull();
    expect(getConsent()).toMatchObject({ analytics: false, ads: false });
    expect(track).toHaveBeenCalledExactlyOnceWith('consent_update', {
      action: 'custom', analytics: 0, ads: 0, policy_version: CONSENT_VERSION,
    });
  });

  it('reopens the saved choices after closing', () => {
    window.localStorage.setItem(CONSENT_KEY, JSON.stringify({ v: CONSENT_VERSION, analytics: false, ads: false }));
    renderConsent();
    expect(screen.queryByRole('dialog')).toBeNull();

    act(() => window.dispatchEvent(new Event(CONSENT_OPEN_EVENT)));
    const [, analytics, ads] = screen.getAllByRole('checkbox');
    expect(analytics.checked).toBe(false);
    expect(ads.checked).toBe(false);
    fireEvent.click(screen.getByRole('button', { name: 'Принять все' }));
    expect(screen.queryByRole('dialog')).toBeNull();

    act(() => window.dispatchEvent(new Event(CONSENT_OPEN_EVENT)));
    expect(screen.getAllByRole('checkbox').every((checkbox) => checkbox.checked)).toBe(true);
    fireEvent.click(screen.getByRole('button', { name: 'Сохранить выбор' }));
    expect(track).toHaveBeenCalledTimes(2);
  });

  it('does not replace a saved opt-out when settings are dismissed', () => {
    window.localStorage.setItem(CONSENT_KEY, JSON.stringify({ v: CONSENT_VERSION, analytics: false, ads: false }));
    renderConsent();
    act(() => window.dispatchEvent(new Event(CONSENT_OPEN_EVENT)));
    const [, analytics, ads] = screen.getAllByRole('checkbox');
    fireEvent.click(analytics);
    fireEvent.click(ads);

    fireEvent.click(screen.getByRole('button', { name: translate('common.close', undefined, 'ru') }));

    expect(screen.queryByRole('dialog')).toBeNull();
    expect(getConsent()).toMatchObject({ analytics: false, ads: false });
    expect(track).toHaveBeenCalledExactlyOnceWith('consent_update', {
      action: 'dismiss', analytics: 0, ads: 0, policy_version: CONSENT_VERSION,
    });
  });

  it('publishes actual panel visibility and clears it on close and unmount', () => {
    const notifications = [];
    const listen = (event) => notifications.push(event.detail);
    window.addEventListener('fe:analytics-overlay:change', listen);
    try {
      const { unmount } = renderConsent();
      const panel = document.querySelector('[data-analytics-overlay="cookie-consent"]');
      expect(panel.getAttribute('data-fe-attention-occluder')).toBe('cookie-consent');
      expect(notifications.at(-1)).toEqual({ id: 'cookie-consent', visible: true, expanded: false });
      fireEvent.click(screen.getByRole('button', { name: 'Настроить' }));
      expect(notifications.at(-1)).toEqual({ id: 'cookie-consent', visible: true, expanded: true });
      fireEvent.click(screen.getByRole('button', { name: 'Сохранить выбор' }));
      expect(notifications.at(-1)).toEqual({ id: 'cookie-consent', visible: false, expanded: false });
      unmount();
      expect(notifications.at(-1)).toEqual({ id: 'cookie-consent', visible: false, expanded: false });
    } finally {
      window.removeEventListener('fe:analytics-overlay:change', listen);
    }
  });

  it('keeps the dialog absent on admin pages', () => {
    renderConsent('ru', '/admin/bi');
    expect(screen.queryByRole('dialog')).toBeNull();
    expect(document.querySelector('[data-analytics-overlay]')).toBeNull();
  });
});
