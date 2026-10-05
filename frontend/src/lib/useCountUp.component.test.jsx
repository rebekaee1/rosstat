/** @vitest-environment jsdom */
import { afterEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, render } from '@testing-library/react';
import useCountUp, { easeOutCubic } from './useCountUp';

function Probe({ value, enabled }) {
  const shown = useCountUp(value, { durationMs: 1000, enabled });
  return <span data-testid="n">{String(Math.round(shown))}</span>;
}

/** Ручные часы requestAnimationFrame: кадры запускаем сами. */
function stubFrames({ reduced = false } = {}) {
  let queue = [];
  let id = 0;
  vi.stubGlobal('matchMedia', () => ({ matches: reduced, addEventListener() {}, removeEventListener() {} }));
  vi.stubGlobal('requestAnimationFrame', (cb) => { id += 1; queue.push([id, cb]); return id; });
  vi.stubGlobal('cancelAnimationFrame', (target) => { queue = queue.filter(([i]) => i !== target); });
  return (now) => {
    const run = queue;
    queue = [];
    run.forEach(([, cb]) => cb(now));
  };
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe('useCountUp', () => {
  it('набегает от нуля к цели и останавливается ровно на ней', () => {
    const tick = stubFrames();
    const { getByTestId } = render(<Probe value={268000} />);
    expect(getByTestId('n').textContent).toBe('0');
    act(() => tick(0));
    act(() => tick(500));
    const mid = Number(getByTestId('n').textContent);
    expect(mid).toBeGreaterThan(0);
    expect(mid).toBeLessThan(268000);
    act(() => tick(1200));
    expect(getByTestId('n').textContent).toBe('268000');
  });

  it('считает один раз: новая цель после конца счёта просто встаёт на место', () => {
    const tick = stubFrames();
    const { getByTestId, rerender } = render(<Probe value={100} />);
    act(() => tick(0));
    act(() => tick(1500));
    expect(getByTestId('n').textContent).toBe('100');
    rerender(<Probe value={250} />);
    expect(getByTestId('n').textContent).toBe('250');
  });

  it('при просьбе о меньшем движении показывает цель сразу', () => {
    stubFrames({ reduced: true });
    const { getByTestId } = render(<Probe value={55} />);
    expect(getByTestId('n').textContent).toBe('55');
  });

  it('отключённый счёт и нечисло не анимируются', () => {
    stubFrames();
    const { getByTestId, rerender } = render(<Probe value={42} enabled={false} />);
    expect(getByTestId('n').textContent).toBe('42');
    rerender(<Probe value="abc" />);
    expect(getByTestId('n').textContent).toBe('NaN');
  });

  it('замедление к концу: больше половины пути пройдено к середине времени', () => {
    expect(easeOutCubic(0)).toBe(0);
    expect(easeOutCubic(1)).toBe(1);
    expect(easeOutCubic(0.5)).toBeGreaterThan(0.5);
  });
});
