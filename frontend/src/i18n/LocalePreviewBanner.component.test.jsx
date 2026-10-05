import { afterEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { LocaleContext } from './localeContext';
import LocalePreviewBanner from './LocalePreviewBanner';

afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

function renderBanner() {
  return render(
    <LocaleContext.Provider value={{ locale: 'ru', t: (key) => key, isPreview: true, setPreviewLocale: () => {} }}>
      <LocalePreviewBanner />
    </LocaleContext.Provider>,
  );
}

describe('значок предпросмотра языка не мешает чтению', () => {
  it('стоит у правого края над плашкой cookie и полупрозрачный', () => {
    renderBanner();
    const toggle = screen.getByTestId('locale-preview-toggle');
    expect(toggle.className).toContain('right-2');
    expect(toggle.className).toContain('opacity-55');
    expect(toggle.style.bottom).toContain('--fe-cookie-h');
    expect(toggle.getAttribute('data-hidden')).toBe('false');
  });

  it('прячется во время прокрутки и возвращается через полсекунды после остановки', () => {
    vi.useFakeTimers();
    renderBanner();
    const toggle = screen.getByTestId('locale-preview-toggle');
    act(() => { fireEvent.scroll(window); });
    expect(toggle.getAttribute('data-hidden')).toBe('true');
    act(() => { vi.advanceTimersByTime(700); });
    expect(toggle.getAttribute('data-hidden')).toBe('false');
  });
});
