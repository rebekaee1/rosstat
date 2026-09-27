// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { mountWhenCssReady } from './mountWhenCssReady';

beforeEach(() => {
  document.head.innerHTML = '';
  vi.useFakeTimers();
});

afterEach(() => {
  vi.useRealTimers();
  document.head.innerHTML = '';
});

describe('SSR stylesheet handoff', () => {
  it('mounts an ordinary SPA shell immediately', () => {
    const mount = vi.fn();
    mountWhenCssReady(mount);
    expect(mount).toHaveBeenCalledOnce();
  });

  it('keeps SSR visible until every stylesheet loads, then mounts once', () => {
    document.head.innerHTML = '<link data-fe-css media="print"><link data-fe-css media="print">';
    const links = [...document.querySelectorAll('link[data-fe-css]')];
    const mount = vi.fn();
    mountWhenCssReady(mount);
    expect(mount).not.toHaveBeenCalled();
    links[0].dispatchEvent(new Event('load'));
    expect(mount).not.toHaveBeenCalled();
    links[1].dispatchEvent(new Event('load'));
    expect(mount).toHaveBeenCalledOnce();
    vi.runAllTimers();
    expect(mount).toHaveBeenCalledOnce();
  });

  it('mounts after a CSS error or timeout so navigation remains usable', () => {
    document.head.innerHTML = '<link data-fe-css media="print">';
    const link = document.querySelector('link[data-fe-css]');
    const mount = vi.fn();
    mountWhenCssReady(mount, { timeoutMs: 100 });
    link.dispatchEvent(new Event('error'));
    expect(mount).toHaveBeenCalledOnce();
    vi.runAllTimers();
    expect(mount).toHaveBeenCalledOnce();

    const second = vi.fn();
    mountWhenCssReady(second, { timeoutMs: 100 });
    vi.advanceTimersByTime(100);
    expect(second).toHaveBeenCalledOnce();
  });
});
