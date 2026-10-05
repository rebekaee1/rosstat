import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { LocaleContext } from '../i18n/localeContext';
import LocalePreviewBanner from '../i18n/LocalePreviewBanner';
import LocaleSwitcher from './LocaleSwitcher';

afterEach(cleanup);

function withLocale(ui, value) {
  return render(
    <LocaleContext.Provider
      value={{ locale: 'en', t: (key) => key, isPreview: false, setPreviewLocale: () => {}, switchLanguage: () => {}, ...value }}
    >
      {ui}
    </LocaleContext.Provider>,
  );
}

describe('волна 7: переключатель языка без флага', () => {
  it('кнопка показывает кружок с кодом языка, а не флаг страны', () => {
    const { container } = withLocale(<LocaleSwitcher />, { locale: 'en' });
    expect(container.querySelector('svg[viewBox="0 0 16 12"]')).toBeNull();
    const button = screen.getByRole('button', { name: /nav.language/ });
    expect(button.textContent).toContain('EN');
    fireEvent.click(button);
    // В списке у каждого языка тот же кружок: RU и EN.
    expect(screen.getAllByText('RU').length).toBeGreaterThan(0);
  });
});

describe('волна 7: плашка предпросмотра языка свёрнута в иконку', () => {
  it('не показывается вне режима предпросмотра', () => {
    const { container } = withLocale(<LocalePreviewBanner />, { isPreview: false });
    expect(container.firstChild).toBeNull();
  });

  it('в режиме предпросмотра сначала только иконка; по нажатию раскрывается текст и выход', () => {
    const exit = vi.fn();
    withLocale(<LocalePreviewBanner />, { isPreview: true, setPreviewLocale: exit });
    expect(screen.queryByRole('button', { name: /preview.exit/ })).toBeNull();
    fireEvent.click(screen.getByTestId('locale-preview-toggle'));
    fireEvent.click(screen.getByRole('button', { name: /preview.exit/ }));
    expect(exit).toHaveBeenCalledWith(null);
    // Свернуть обратно.
    fireEvent.click(screen.getByRole('button', { name: 'w7p.preview.close' }));
    expect(screen.getByTestId('locale-preview-toggle')).toBeTruthy();
  });
});
