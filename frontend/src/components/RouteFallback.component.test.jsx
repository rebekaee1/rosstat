import { it, expect, afterEach, vi } from 'vitest';
import { render, screen, cleanup, act } from '@testing-library/react';
import RouteFallback from './RouteFallback';
import { LocaleProvider } from '../i18n';

afterEach(() => { cleanup(); vi.useRealTimers(); });

it('shows a layout skeleton with a caption while the route chunk loads', () => {
  render(<LocaleProvider locale="ru"><RouteFallback /></LocaleProvider>);
  expect(screen.getAllByRole('status')[0].getAttribute('aria-busy')).toBe('true');
  expect(screen.getByTestId('loading-note').textContent).toContain('Загружаем данные');
  expect(screen.queryByRole('button', { name: /Обновить/ })).toBeNull();
});

it('the skeleton is visible at once (no delayed fade-in) and is shaped like cards: header, value tiles, chart', () => {
  render(<LocaleProvider locale="ru"><RouteFallback /></LocaleProvider>);
  const skeleton = document.querySelector('.fe-route-skel');
  expect(skeleton).toBeTruthy();
  // Раньше каркас стартовал с задержкой 0.15 с и первые мгновения казался пустой страницей.
  expect(skeleton.style.getPropertyValue('--fe-delay')).toBe('');
  expect(skeleton.className).not.toContain('fe-reveal');
  expect(skeleton.querySelectorAll('.fe-route-skel__tiles > div')).toHaveLength(3);
  expect(skeleton.querySelectorAll('.skeleton').length).toBeGreaterThanOrEqual(8);
});

it('never prints the server-rendered text for a human: only the skeleton, even when a snapshot exists', () => {
  window.__feSsrSnapshot = '<div class="seo-page"><h1>Key rate</h1></div>';
  render(<LocaleProvider locale="ru"><RouteFallback /></LocaleProvider>);
  expect(document.querySelector('.fe-ssr-hold')).toBeNull();
  expect(document.body.textContent).not.toContain('Key rate');
  delete window.__feSsrSnapshot;
});

it('offers a refresh button after the wait gets long', () => {
  vi.useFakeTimers();
  render(<LocaleProvider locale="ru"><RouteFallback /></LocaleProvider>);
  act(() => { vi.advanceTimersByTime(5100); });
  expect(screen.getByRole('button', { name: /Обновить/ })).toBeTruthy();
});
