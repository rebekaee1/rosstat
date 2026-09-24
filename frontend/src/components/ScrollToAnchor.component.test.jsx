import { afterEach, it, expect, vi } from 'vitest';
import { render, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import ScrollToAnchor from './ScrollToAnchor';

afterEach(() => vi.restoreAllMocks());
it('reaches a chart that is mounted only after its data request', async () => {
  const scroll = vi.fn();
  const { container, unmount } = render(<MemoryRouter initialEntries={['/germany#chart']}><ScrollToAnchor /><main /></MemoryRouter>);
  const chart = document.createElement('section');
  chart.id = 'chart';
  chart.scrollIntoView = scroll;
  container.querySelector('main').append(chart);
  await waitFor(() => expect(scroll).toHaveBeenCalledOnce());
  container.querySelector('main').append(document.createElement('p'));
  expect(scroll).toHaveBeenCalledOnce();
  unmount();
});
it('cleans up pending navigation when the route is unmounted', async () => {
  const scroll = vi.fn();
  const { unmount } = render(<MemoryRouter initialEntries={['/germany#chart']}><ScrollToAnchor /></MemoryRouter>);
  unmount();
  const chart = document.createElement('section');
  chart.id = 'chart'; chart.scrollIntoView = scroll;
  document.body.append(chart);
  await Promise.resolve();
  expect(scroll).not.toHaveBeenCalled();
  chart.remove();
});
