import { act, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import { LocaleProvider } from '../i18n';
import MobileDock from './MobileDock';

async function scrollTo(y) {
  Object.defineProperty(window, 'scrollY', { value: y, configurable: true });
  await act(async () => {
    window.dispatchEvent(new Event('scroll'));
    await new Promise((resolve) => { setTimeout(resolve, 40); });
  });
}

function renderDock(route = '/') {
  return render(
    <MemoryRouter initialEntries={[route]}>
      <LocaleProvider locale="ru">
        <MobileDock />
        <input data-testid="field" type="search" />
        <input data-testid="range" type="range" />
        <input data-testid="tick" type="checkbox" />
      </LocaleProvider>
    </MemoryRouter>,
  );
}

afterEach(() => {
  Object.defineProperty(window, 'scrollY', { value: 0, configurable: true });
  document.documentElement.style.removeProperty('--fe-dock-h');
  document.documentElement.style.removeProperty('--fe-dock-reserve');
  delete document.documentElement.dataset.feDock;
});

describe('MobileDock, круг 11 G (U29): не мешает вводу и бегунку', () => {
  it('пока фокус в текстовом поле, панель спрятана; после ухода фокуса возвращается', async () => {
    renderDock();
    const dock = screen.getByRole('navigation', { name: 'Основные разделы' });
    await scrollTo(400);
    await scrollTo(300);
    expect(dock.getAttribute('data-visible')).toBe('true');
    const field = screen.getByTestId('field');
    act(() => { field.focus(); });
    expect(dock.getAttribute('data-visible')).toBe('false');
    expect(document.documentElement.style.getPropertyValue('--fe-dock-h')).toBe('0px');
    act(() => { field.blur(); });
    await act(async () => { await new Promise((resolve) => { setTimeout(resolve, 220); }); });
    expect(dock.getAttribute('data-visible')).toBe('true');
  });

  it('флажок и кнопки панель не прячут: прячет только ввод текста', async () => {
    renderDock();
    const dock = screen.getByRole('navigation', { name: 'Основные разделы' });
    await scrollTo(400);
    await scrollTo(300);
    act(() => { screen.getByTestId('tick').focus(); });
    expect(dock.getAttribute('data-visible')).toBe('true');
  });

  it('палец на бегунке прячет панель и возвращает её через 0,6 с после отпускания', async () => {
    renderDock();
    const dock = screen.getByRole('navigation', { name: 'Основные разделы' });
    await scrollTo(400);
    await scrollTo(300);
    const range = screen.getByTestId('range');
    act(() => { fireEvent.pointerDown(range); });
    expect(dock.getAttribute('data-visible')).toBe('false');
    act(() => { fireEvent.pointerUp(range); });
    expect(dock.getAttribute('data-visible')).toBe('false');
    await act(async () => { await new Promise((resolve) => { setTimeout(resolve, 700); }); });
    expect(dock.getAttribute('data-visible')).toBe('true');
  });

  it('«Страны» в панели подсвечены по адресу #countries', () => {
    render(
      <MemoryRouter initialEntries={['/#countries']}>
        <LocaleProvider locale="ru"><MobileDock /></LocaleProvider>
      </MemoryRouter>,
    );
    const dock = screen.getByRole('navigation', { name: 'Основные разделы' });
    const current = [...dock.querySelectorAll('[aria-current="page"]')].map((n) => n.textContent);
    expect(current).toEqual(['Страны']);
  });
});
