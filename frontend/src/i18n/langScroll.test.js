// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import {
  rememberScrollForLanguageSwitch,
  restoreScrollAfterLanguageSwitch,
  takeRememberedScroll,
} from './langScroll';

function setScrollY(y) {
  Object.defineProperty(window, 'scrollY', { value: y, configurable: true });
}

function clearCookie() {
  document.cookie = 'fe_lang_scroll=; Max-Age=0; Path=/';
}

describe('сохранение прокрутки при смене языка', () => {
  beforeEach(() => {
    clearCookie();
    window.history.pushState({}, '', '/world/rating/gdp-usd');
  });
  afterEach(() => {
    clearCookie();
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it('запоминает позицию и возвращает её один раз на том же адресе', () => {
    setScrollY(640);
    expect(rememberScrollForLanguageSwitch()).toBe(true);
    expect(takeRememberedScroll()).toBe(640);
    expect(takeRememberedScroll()).toBeNull();
  });

  it('у самого верха страницы ничего не запоминает', () => {
    setScrollY(20);
    expect(rememberScrollForLanguageSwitch()).toBe(false);
    expect(takeRememberedScroll()).toBeNull();
  });

  it('на другом адресе или с якорем позицию не возвращает', () => {
    setScrollY(500);
    rememberScrollForLanguageSwitch();
    window.history.pushState({}, '', '/russia');
    expect(takeRememberedScroll()).toBeNull();

    setScrollY(500);
    window.history.pushState({}, '', '/world/rating/gdp-usd');
    rememberScrollForLanguageSwitch();
    window.history.pushState({}, '', '/world/rating/gdp-usd#rating-table');
    expect(takeRememberedScroll()).toBeNull();
  });

  it('устаревшую запись (дольше 20 секунд) игнорирует', () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2026-10-05T10:00:00Z'));
    setScrollY(500);
    rememberScrollForLanguageSwitch();
    vi.setSystemTime(new Date('2026-10-05T10:00:30Z'));
    expect(takeRememberedScroll()).toBeNull();
  });

  it('ждёт, пока у страницы хватит высоты, и только потом прокручивает', () => {
    vi.useFakeTimers();
    setScrollY(900);
    rememberScrollForLanguageSwitch();
    const scrollTo = vi.fn();
    window.scrollTo = scrollTo;
    Object.defineProperty(window, 'innerHeight', { value: 800, configurable: true });
    let height = 1000;
    Object.defineProperty(document.documentElement, 'scrollHeight', { get: () => height, configurable: true });
    const stop = restoreScrollAfterLanguageSwitch();
    expect(scrollTo).not.toHaveBeenCalled();
    height = 2400;
    vi.advanceTimersByTime(160);
    expect(scrollTo).toHaveBeenCalledWith({ top: 900, left: 0, behavior: 'instant' });
    stop();
  });
});
