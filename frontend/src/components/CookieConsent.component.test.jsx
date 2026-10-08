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
  window.sessionStorage.clear();
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
    // Два переключателя понятными словами; «необходимые» — строка текста, а не отключаемый флажок.
    const [analytics, ads] = within(body).getAllByRole('switch');
    expect(within(body).getAllByRole('switch')).toHaveLength(2);
    expect(within(body).queryAllByRole('checkbox')).toHaveLength(0);
    expect(analytics.checked).toBe(true);
    expect(ads.checked).toBe(true);
    expect(within(body).getByText(translate('shell3.cookie.analytics', undefined, locale))).toBeTruthy();
    expect(within(body).getByText(translate('shell3.cookie.ads', undefined, locale))).toBeTruthy();
    expect(body.contains(actions)).toBe(false);
    expect(within(body).getByRole('link', { name: translate('cookie.privacyShort', undefined, locale) }).getAttribute('href')).toBe('/privacy');
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
    const [analytics, ads] = screen.getAllByRole('switch');
    expect(analytics.checked).toBe(false);
    expect(ads.checked).toBe(false);
    fireEvent.click(screen.getByRole('button', { name: 'Принять все' }));
    expect(screen.queryByRole('dialog')).toBeNull();

    act(() => window.dispatchEvent(new Event(CONSENT_OPEN_EVENT)));
    expect(screen.getAllByRole('switch').every((toggle) => toggle.checked)).toBe(true);
    fireEvent.click(screen.getByRole('button', { name: 'Сохранить выбор' }));
    expect(track).toHaveBeenCalledTimes(2);
  });

  it('does not replace a saved opt-out when settings are dismissed', () => {
    window.localStorage.setItem(CONSENT_KEY, JSON.stringify({ v: CONSENT_VERSION, analytics: false, ads: false }));
    renderConsent();
    act(() => window.dispatchEvent(new Event(CONSENT_OPEN_EVENT)));
    const [analytics, ads] = screen.getAllByRole('switch');
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

  it('compact banner: one short text and the decision buttons in view (accept, only necessary, settings), no title row', () => {
    renderConsent();
    const dialog = screen.getByRole('dialog');
    expect(within(dialog).queryByText(translate('cookie.title', undefined, 'ru'))).toBeNull();
    expect(within(dialog).getAllByRole('button').map((b) => b.textContent.trim()).filter(Boolean)).toEqual(['Хорошо', 'Только необходимые', 'Настроить']);
    expect(translate('cookie.summary', undefined, 'ru').length).toBeLessThan(90);
    // Сами категории и длинный текст — только после «Настроить».
    expect(within(dialog).queryAllByRole('checkbox')).toHaveLength(0);
  });

  it('короткая панель настроек: без названий сервисов, предотмечено по прежнему решению (подразумеваемое согласие)', () => {
    renderConsent();
    fireEvent.click(screen.getByRole('button', { name: 'Настроить' }));
    const dialog = screen.getByRole('dialog');
    const text = dialog.textContent;
    expect(text).toContain('Статистика посещаемости');
    expect(text).toContain('Реклама');
    expect(text).not.toMatch(/Яндекс|Метрик|РСЯ|Yandex/i);
    expect(within(dialog).getAllByRole('switch').every((toggle) => toggle.checked)).toBe(true);
    // Не на весь экран: высота ограничена, а прокручивается только тело.
    expect(dialog.firstElementChild.className).toMatch(/max-h-\[min\(30rem/);
  });

  it.each(['ru', 'en'])('компактная плашка: один текст, значок-шестерёнка вместо слова, ширина по содержимому до 416 px (%s)', (locale) => {
    renderConsent(locale);
    const dialog = screen.getByRole('dialog');
    const panel = dialog.firstElementChild;
    expect(panel.className).toContain('fe-cookie-panel');
    expect(panel.className).toContain('sm:max-w-[26rem]');
    expect(panel.className).toContain('sm:w-fit');
    // Круг 8: текст один на все ширины (двух вариантов «длинный/короткий» больше нет).
    expect(dialog.querySelector('.fe-cookie-compact__text').textContent).toContain(translate('cookie.summary', undefined, locale));
    expect(dialog.querySelector('.fe-cookie-compact__long')).toBeNull();
    // «Настроить» остаётся именем кнопки для скринридера и подсказкой, на глаз это значок.
    const gear = within(dialog).getByRole('button', { name: translate('cookie.customize', undefined, locale) });
    expect(gear.className).toContain('fe-cookie-gear');
    expect(gear.getAttribute('title')).toBe(translate('cookie.customize', undefined, locale));
    expect(gear.querySelector('svg')).toBeTruthy();
    expect(gear.querySelector('.fe-cookie-gear__label')).toBeTruthy();
  });

  it('молчание не считается согласием: плашка не закрывается сама', () => {
    vi.useFakeTimers();
    try {
      renderConsent();
      act(() => { vi.advanceTimersByTime(60_000); });
      expect(screen.getByRole('dialog')).toBeTruthy();
      expect(getConsent()).toBeNull();
      expect(track).not.toHaveBeenCalled();
    } finally {
      vi.useRealTimers();
    }
  });

  it('settings offer a direct refusal: only necessary cookies', () => {
    renderConsent();
    fireEvent.click(screen.getByRole('button', { name: 'Настроить' }));
    fireEvent.click(screen.getByRole('button', { name: 'Только необходимые' }));

    expect(screen.queryByRole('dialog')).toBeNull();
    expect(getConsent()).toMatchObject({ analytics: false, ads: false });
    expect(track).toHaveBeenCalledExactlyOnceWith('consent_update', {
      action: 'necessary_only', analytics: 0, ads: 0, policy_version: CONSENT_VERSION,
    });
  });

  it('круг 8, S1: «Только необходимые» стоит на виду рядом с «Хорошо» и записывает отказ без захода в настройки', () => {
    renderConsent();
    fireEvent.click(screen.getByRole('button', { name: 'Только необходимые' }));
    expect(screen.queryByRole('dialog')).toBeNull();
    expect(getConsent()).toMatchObject({ analytics: false, ads: false });
    expect(track).toHaveBeenCalledExactlyOnceWith('consent_update', {
      action: 'necessary_only', analytics: 0, ads: 0, policy_version: CONSENT_VERSION,
    });
  });

  it('keeps the dialog absent on admin pages', () => {
    renderConsent('ru', '/admin/bi');
    expect(screen.queryByRole('dialog')).toBeNull();
    expect(document.querySelector('[data-analytics-overlay]')).toBeNull();
  });
});

describe('круг 8, S1: после первой прокрутки плашка прячется на любой ширине и не возвращается до конца сессии', () => {
  const realMatchMedia = window.matchMedia;
  async function scrollTo(y) {
    Object.defineProperty(window, 'scrollY', { value: y, configurable: true });
    await act(async () => {
      window.dispatchEvent(new Event('scroll'));
      await new Promise((resolve) => { setTimeout(resolve, 40); });
    });
  }
  afterEach(() => {
    window.matchMedia = realMatchMedia;
    Object.defineProperty(window, 'scrollY', { value: 0, configurable: true });
  });
  const phone = () => {
    window.matchMedia = (query) => ({
      matches: query.includes('max-width: 639px'), media: query, addEventListener() {}, removeEventListener() {},
    });
  };

  it('телефон: после прокрутки плашка спрятана целиком, плавающего значка нет; согласие не записано и не отправлено', async () => {
    phone();
    renderConsent();
    expect(screen.getByRole('dialog')).toBeTruthy();
    await scrollTo(120);
    expect(screen.queryByRole('dialog')).toBeNull();
    // Значок на странице не плавает: он ложился на цифры и кнопки.
    expect(document.querySelector('.fe-cookie-fab')).toBeNull();
    expect(screen.queryByRole('button', { name: 'Настройки cookie' })).toBeNull();
    // Молчание не согласие: ни записи выбора, ни события.
    expect(getConsent()).toBeNull();
    expect(track).not.toHaveBeenCalled();
  });

  it('вернувшись наверх страницы, посетитель плашку не видит (она уже была показана); выбор не записан; настройки открываются из меню', async () => {
    phone();
    renderConsent();
    await scrollTo(120);
    expect(screen.queryByRole('dialog')).toBeNull();
    await scrollTo(0);
    expect(screen.queryByRole('dialog')).toBeNull();
    expect(getConsent()).toBeNull();
    expect(window.sessionStorage.getItem('fe:consent:snooze')).toBe('1');
  });

  it('в новой вкладке сессии (хранилище очищено) плашка показывается снова', async () => {
    renderConsent();
    await scrollTo(120);
    expect(screen.queryByRole('dialog')).toBeNull();
    cleanup();
    window.sessionStorage.clear();
    await scrollTo(0);
    renderConsent();
    expect(screen.getByRole('dialog')).toBeTruthy();
  });

  it('настройки из меню или подвала (событие) раскрываются и после прокрутки', async () => {
    phone();
    renderConsent();
    await scrollTo(120);
    expect(screen.queryByRole('dialog')).toBeNull();
    act(() => { window.dispatchEvent(new Event(CONSENT_OPEN_EVENT)); });
    expect(screen.getByRole('dialog')).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Сохранить выбор' })).toBeTruthy();
  });

  it('компьютер и планшет: плашка тоже сворачивается после прокрутки, значка вместо неё нет', async () => {
    renderConsent();
    await scrollTo(400);
    expect(screen.queryByRole('dialog')).toBeNull();
    expect(screen.queryByRole('button', { name: 'Настройки cookie' })).toBeNull();
    expect(getConsent()).toBeNull();
  });

  it('открытые настройки не сворачиваются', async () => {
    phone();
    renderConsent();
    fireEvent.click(screen.getByRole('button', { name: 'Настроить' }));
    await scrollTo(400);
    expect(screen.getByRole('dialog')).toBeTruthy();
  });
});

