/** @vitest-environment jsdom */
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import useSearchTracking from './useSearchTracking';

vi.mock('./track', () => ({
  track: vi.fn(),
  events: { SEARCH_QUERY: 'search_query' },
}));

import { track } from './track';

describe('useSearchTracking', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    track.mockClear();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('после debounce шлёт search_query с q/results/context при длине ≥2', () => {
    renderHook(() => useSearchTracking('compare-country', 'гер', 4));

    expect(track).not.toHaveBeenCalled();
    act(() => {
      vi.advanceTimersByTime(899);
    });
    expect(track).not.toHaveBeenCalled();

    act(() => {
      vi.advanceTimersByTime(1);
    });
    expect(track).toHaveBeenCalledTimes(1);
    expect(track).toHaveBeenCalledWith('search_query', {
      q: 'гер',
      results: 4,
      context: 'compare-country',
    });
  });

  it('не шлёт при query короче minLen', () => {
    renderHook(() => useSearchTracking('world-concept-picker', 'а', 2));
    act(() => {
      vi.advanceTimersByTime(1000);
    });
    expect(track).not.toHaveBeenCalled();
  });
});
