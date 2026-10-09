import { describe, it, expect, vi, afterEach } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import ChartDownloadMenu from './ChartDownloadMenu';
import { LocaleProvider } from '../i18n';

afterEach(() => { vi.restoreAllMocks(); });

function mockPhone(matches) {
  window.matchMedia = vi.fn().mockImplementation((query) => ({
    matches: matches && /max-width: 639px/.test(query),
    media: query,
    addEventListener: () => {},
    removeEventListener: () => {},
  }));
}

describe('ChartDownloadMenu (круг 11)', () => {
  it('на компьютере меню стоит в пределах окна и плотное, лишние форматы можно скрыть', () => {
    mockPhone(false);
    const onCsv = vi.fn();
    render(<LocaleProvider><ChartDownloadMenu formats={['csv', 'excel']} onCsv={onCsv} label="Скачать данные" /></LocaleProvider>);
    fireEvent.click(screen.getByRole('button', { name: /Скачать данные/ }));
    const menu = screen.getByRole('menu');
    expect(menu.className).toContain('fe-w6g-solid-panel');
    expect(screen.queryByRole('menuitem', { name: /PNG/ })).toBeNull();
    fireEvent.click(screen.getByRole('menuitem', { name: /CSV/ }));
    expect(onCsv).toHaveBeenCalledTimes(1);
    expect(screen.queryByRole('menu')).toBeNull();
  });

  it('на телефоне меню открывается нижним листом, а не выпадающим окном у края', () => {
    mockPhone(true);
    const onPng = vi.fn();
    render(<LocaleProvider><ChartDownloadMenu onPng={onPng} /></LocaleProvider>);
    fireEvent.click(screen.getByRole('button', { name: /Скачать/ }));
    expect(screen.queryByRole('menu')).toBeNull();
    const sheet = screen.getByRole('dialog');
    expect(sheet.className).toContain('fe-bsheet');
    fireEvent.click(screen.getByRole('button', { name: /PNG/ }));
    expect(onPng).toHaveBeenCalledTimes(1);
    expect(screen.queryByRole('dialog')).toBeNull();
  });
});
