import { it, expect, afterEach } from 'vitest';
import { render, screen, cleanup } from '@testing-library/react';
import RouteFallback, { SsrHandoffDone } from './RouteFallback';

afterEach(() => { cleanup(); delete window.__feSsrSnapshot; });

it('shows a layout skeleton when there is no server-rendered page to hold', () => {
  render(<RouteFallback />);
  expect(screen.getByRole('status').getAttribute('aria-busy')).toBe('true');
  expect(document.querySelector('.fe-ssr-hold')).toBeNull();
});

it('the skeleton is visible at once (no delayed fade-in) and is shaped like cards: header, value tiles, chart', () => {
  render(<RouteFallback />);
  const skeleton = document.querySelector('.fe-route-skel');
  expect(skeleton).toBeTruthy();
  // Раньше каркас стартовал с задержкой 0.15 с и первые мгновения казался пустой страницей.
  expect(skeleton.style.getPropertyValue('--fe-delay')).toBe('');
  expect(skeleton.className).not.toContain('fe-reveal');
  expect(skeleton.querySelectorAll('.fe-route-skel__tiles > div')).toHaveLength(3);
  expect(skeleton.querySelectorAll('.skeleton').length).toBeGreaterThanOrEqual(8);
});

it('keeps the server-rendered page on screen while the route chunk loads, then lets go of it', () => {
  window.__feSsrSnapshot = '<div class="seo-page"><h1>Key rate</h1></div>';
  render(<RouteFallback />);
  expect(document.querySelector('.fe-ssr-hold h1').textContent).toBe('Key rate');
  cleanup();
  render(<SsrHandoffDone />);
  expect(window.__feSsrSnapshot).toBeNull();
  cleanup();
  render(<RouteFallback />);
  expect(document.querySelector('.fe-ssr-hold')).toBeNull();
});
