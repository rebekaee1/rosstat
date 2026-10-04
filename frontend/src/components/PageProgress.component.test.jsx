import { it, expect, vi, afterEach } from 'vitest';
import { render, screen, fireEvent, cleanup, act } from '@testing-library/react';
import { MemoryRouter, Link } from 'react-router-dom';
import PageProgress from './PageProgress';

afterEach(() => { cleanup(); vi.useRealTimers(); });

it('shows after a short delay when an internal link is clicked and stays hidden otherwise', () => {
  vi.useFakeTimers();
  render(<MemoryRouter><PageProgress /><Link to="/next">next</Link><a href="https://example.com/">ext</a></MemoryRouter>);
  expect(screen.queryByTestId('page-progress')).toBeNull();
  fireEvent.click(screen.getByText('ext'));
  act(() => { vi.advanceTimersByTime(300); });
  expect(screen.queryByTestId('page-progress')).toBeNull();
});
