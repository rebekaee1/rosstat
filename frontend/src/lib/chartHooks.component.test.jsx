/** @vitest-environment jsdom */
import { useRef } from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { usePrefersReducedMotion, useTouchTooltip } from './chartHooks';

const realMatchMedia = window.matchMedia;

function mockMedia(matchesFor) {
  window.matchMedia = (query) => ({
    matches: matchesFor(query),
    media: query,
    addEventListener() {},
    removeEventListener() {},
    addListener() {},
    removeListener() {},
  });
}

afterEach(() => {
  cleanup();
  window.matchMedia = realMatchMedia;
  vi.restoreAllMocks();
});

function TooltipProbe() {
  const ref = useRef(null);
  const touch = useTouchTooltip(ref);
  return (
    <div>
      <div ref={ref} data-testid="chart" onPointerDownCapture={touch.onPointerDownCapture} />
      <button type="button">outside</button>
      <output data-testid="active">{JSON.stringify(touch.tooltipProps)}</output>
    </div>
  );
}

describe('useTouchTooltip', () => {
  it('leaves hover behaviour alone on a fine pointer', () => {
    mockMedia(() => false);
    render(<TooltipProbe />);
    expect(screen.getByTestId('active').textContent).toBe('{}');
    fireEvent.pointerDown(screen.getByTestId('chart'));
    expect(screen.getByTestId('active').textContent).toBe('{}');
  });

  it('on touch: hidden until the chart is touched, hidden again by a touch outside', () => {
    mockMedia((q) => q === '(pointer: coarse)');
    render(<TooltipProbe />);
    // active=false → Recharts never shows the tooltip
    expect(screen.getByTestId('active').textContent).toBe('{"active":false}');

    fireEvent.pointerDown(screen.getByTestId('chart'));
    expect(screen.getByTestId('active').textContent).toBe('{}');

    // Касание внутри графика не закрывает подсказку.
    fireEvent.pointerDown(screen.getByTestId('chart'));
    expect(screen.getByTestId('active').textContent).toBe('{}');

    fireEvent.pointerDown(screen.getByText('outside'));
    expect(screen.getByTestId('active').textContent).toBe('{"active":false}');
  });

  it('on touch: Escape closes the tooltip', () => {
    mockMedia((q) => q === '(pointer: coarse)');
    render(<TooltipProbe />);
    fireEvent.pointerDown(screen.getByTestId('chart'));
    expect(screen.getByTestId('active').textContent).toBe('{}');
    act(() => { fireEvent.keyDown(document, { key: 'Escape' }); });
    expect(screen.getByTestId('active').textContent).toBe('{"active":false}');
  });
});

describe('useTouchTooltip: прокрутка страницы (круг 9, C5)', () => {
  it('on touch: a real scroll of the page closes the tooltip, a tiny jitter does not', () => {
    mockMedia((q) => q === '(pointer: coarse)');
    render(<TooltipProbe />);
    fireEvent.pointerDown(screen.getByTestId('chart'));
    expect(screen.getByTestId('active').textContent).toBe('{}');
    act(() => { window.scrollY = 10; fireEvent.scroll(window); });
    expect(screen.getByTestId('active').textContent).toBe('{}');
    act(() => { window.scrollY = 120; fireEvent.scroll(window); });
    expect(screen.getByTestId('active').textContent).toBe('{"active":false}');
    window.scrollY = 0;
  });
});

describe('usePrefersReducedMotion', () => {
  function Reduced() {
    return <output data-testid="reduced">{String(usePrefersReducedMotion())}</output>;
  }

  it('reports the media query', () => {
    mockMedia((q) => q === '(prefers-reduced-motion: reduce)');
    render(<Reduced />);
    expect(screen.getByTestId('reduced').textContent).toBe('true');
    cleanup();
    mockMedia(() => false);
    render(<Reduced />);
    expect(screen.getByTestId('reduced').textContent).toBe('false');
  });
});
