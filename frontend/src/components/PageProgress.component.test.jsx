import { it, expect, vi, afterEach } from 'vitest';
import { render, screen, fireEvent, cleanup, act } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { LocaleProvider } from '../i18n';
import PageProgress from './PageProgress';
import { navLabelFor } from '../lib/navLabel';

afterEach(() => { cleanup(); vi.useRealTimers(); });

function renderProgress(children) {
  return render(
    <MemoryRouter>
      <LocaleProvider locale="ru">
        <PageProgress />
        {children}
      </LocaleProvider>
    </MemoryRouter>,
  );
}

it('stays hidden for an external link', () => {
  vi.useFakeTimers();
  renderProgress(<a href="https://example.com/" onClick={(e) => e.preventDefault()}>ext</a>);
  expect(screen.queryByTestId('page-progress')).toBeNull();
  fireEvent.click(screen.getByText('ext'));
  act(() => { vi.advanceTimersByTime(300); });
  expect(screen.queryByTestId('page-progress')).toBeNull();
  expect(screen.queryByTestId('nav-hint')).toBeNull();
});

it('answers an internal tap at once with the bar and an "Opening: name" pill', () => {
  renderProgress(<a href="/germany" onClick={(e) => e.preventDefault()}>Германия</a>);
  fireEvent.click(screen.getByText('Германия'));
  expect(screen.getByTestId('page-progress')).toBeTruthy();
  expect(screen.getByTestId('nav-hint').textContent).toBe('Открываем: Германия');
});

it('falls back to a generic line when the tapped link has no readable name, and lets go after 8 s', () => {
  vi.useFakeTimers();
  renderProgress(<a href="/germany" onClick={(e) => e.preventDefault()}><svg aria-hidden="true" /></a>);
  fireEvent.click(document.querySelector('a'));
  expect(screen.getByTestId('nav-hint').textContent).toBe('Открываем страницу…');
  act(() => { vi.advanceTimersByTime(8100); });
  expect(screen.queryByTestId('nav-hint')).toBeNull();
});

it('prefers data-nav-label and shortens long link text', () => {
  const a = document.createElement('a');
  a.setAttribute('data-nav-label', 'Инфляция');
  a.textContent = 'что-то совсем другое';
  expect(navLabelFor(a)).toBe('Инфляция');
  const long = document.createElement('a');
  long.textContent = 'Очень длинное название показателя, которое не помещается в маленькую плашку';
  expect(navLabelFor(long).length).toBeLessThanOrEqual(44);
  expect(navLabelFor(long).endsWith('…')).toBe(true);
});
