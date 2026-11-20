// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest';
import { restoreScrollTo } from './restoreScroll';

afterEach(() => { vi.useRealTimers(); vi.restoreAllMocks(); });

describe('restoreScrollTo (правка 16: место прокрутки при «назад»)', () => {
  it('ждёт, пока у страницы хватит высоты, и ставит прежнее место', () => {
    vi.useFakeTimers();
    const scrollTo = vi.spyOn(window, 'scrollTo').mockImplementation(() => {});
    let height = 500;
    vi.spyOn(document.documentElement, 'scrollHeight', 'get').mockImplementation(() => height);
    Object.defineProperty(window, 'innerHeight', { value: 500, configurable: true });
    restoreScrollTo(900);
    expect(scrollTo).not.toHaveBeenCalled();
    height = 2000;
    vi.advanceTimersByTime(160);
    expect(scrollTo).toHaveBeenCalledWith({ top: 900, left: 0, behavior: 'instant' });
  });

  it('касание отменяет возврат: человек уже ведёт страницу сам', () => {
    vi.useFakeTimers();
    const scrollTo = vi.spyOn(window, 'scrollTo').mockImplementation(() => {});
    vi.spyOn(document.documentElement, 'scrollHeight', 'get').mockImplementation(() => 500);
    Object.defineProperty(window, 'innerHeight', { value: 500, configurable: true });
    restoreScrollTo(900);
    window.dispatchEvent(new Event('touchstart'));
    vi.advanceTimersByTime(10_000);
    expect(scrollTo).not.toHaveBeenCalled();
  });

  it('нулевая позиция ничего не делает', () => {
    const scrollTo = vi.spyOn(window, 'scrollTo').mockImplementation(() => {});
    restoreScrollTo(0);
    expect(scrollTo).not.toHaveBeenCalled();
  });
});
