import { afterEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { LocaleContext } from '../i18n/localeContext';
import LocaleSwitcher from './LocaleSwitcher';

afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

function renderSwitcher(switchLanguage) {
  const t = (key) => key;
  return render(
    <LocaleContext.Provider value={{ locale: 'ru', t, isPreview: false, setPreviewLocale() {}, switchLanguage }}>
      <LocaleSwitcher />
    </LocaleContext.Provider>,
  );
}

describe('LocaleSwitcher: ожидание смены языка (круг 9, S9)', () => {
  it('после выбора другого языка кнопка показывает ожидание, не нажимается и сообщает об этом скринридеру', () => {
    const switchLanguage = vi.fn();
    renderSwitcher(switchLanguage);
    const trigger = screen.getByRole('button', { name: /nav\.language/ });
    expect(trigger.getAttribute('data-switching')).toBeNull();
    fireEvent.click(trigger);
    fireEvent.click(screen.getAllByRole('menuitem')[1]);
    expect(switchLanguage).toHaveBeenCalledWith('en');
    const busy = screen.getByRole('button', { name: 'c9a.locale.switching' });
    expect(busy.getAttribute('data-switching')).toBe('true');
    expect(busy.getAttribute('aria-busy')).toBe('true');
  });

  it('выбор текущего языка ничего не меняет и ожидания не включает', () => {
    const switchLanguage = vi.fn();
    renderSwitcher(switchLanguage);
    fireEvent.click(screen.getByRole('button', { name: /nav\.language/ }));
    fireEvent.click(screen.getAllByRole('menuitem')[0]);
    expect(switchLanguage).not.toHaveBeenCalled();
    expect(screen.getByRole('button', { name: /nav\.language/ }).getAttribute('data-switching')).toBeNull();
  });

  it('если переход не состоялся, ожидание снимается само через 12 секунд', () => {
    vi.useFakeTimers();
    renderSwitcher(vi.fn());
    fireEvent.click(screen.getByRole('button', { name: /nav\.language/ }));
    fireEvent.click(screen.getAllByRole('menuitem')[1]);
    expect(screen.getByRole('button', { name: 'c9a.locale.switching' })).toBeTruthy();
    act(() => { vi.advanceTimersByTime(12100); });
    expect(screen.getByRole('button', { name: /nav\.language/ }).getAttribute('data-switching')).toBeNull();
  });
});
