import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, render } from '@testing-library/react';
import AnimatedCount from './AnimatedCount';

const realObserver = window.IntersectionObserver;
const realMatchMedia = window.matchMedia;

/** Наблюдатель, который сразу сообщает «блок виден» (как браузер при первом кадре над сгибом). */
class VisibleObserver {
  constructor(callback) { this.callback = callback; }
  observe(node) { queueMicrotask(() => this.callback([{ isIntersecting: true, target: node }])); }
  disconnect() {}
}

beforeEach(() => {
  vi.useFakeTimers({ toFake: ['requestAnimationFrame', 'cancelAnimationFrame', 'performance'] });
});

afterEach(() => {
  vi.useRealTimers();
  window.IntersectionObserver = realObserver;
  window.matchMedia = realMatchMedia;
});

describe('AnimatedCount', () => {
  it('без наблюдателя видимости и в тестах сразу отдаёт итоговое значение', () => {
    window.IntersectionObserver = undefined;
    const { container } = render(<AnimatedCount value={268} />);
    expect(container.textContent).toBe('268');
  });

  it('prefers-reduced-motion: сразу итог, анимации нет', () => {
    window.IntersectionObserver = VisibleObserver;
    window.matchMedia = (query) => ({ matches: /reduce/.test(query), media: query, addEventListener() {}, removeEventListener() {} });
    const { container } = render(<AnimatedCount value={268} />);
    expect(container.textContent).toBe('268');
  });

  it('один раз докручивает от стартового значения до итога', async () => {
    window.IntersectionObserver = VisibleObserver;
    window.matchMedia = (query) => ({ matches: false, media: query, addEventListener() {}, removeEventListener() {} });
    const { container } = render(<AnimatedCount value={1897} from={2026} duration={900} format={(n) => String(Math.round(n))} />);
    await act(async () => { await Promise.resolve(); });
    expect(container.textContent).toBe('2026');
    await act(async () => { vi.advanceTimersByTime(450); });
    const mid = Number(container.textContent);
    expect(mid).toBeLessThan(2026);
    expect(mid).toBeGreaterThan(1897);
    await act(async () => { vi.advanceTimersByTime(600); });
    expect(container.textContent).toBe('1897');
  });

  it('пока значения нет, ничего не рисует', () => {
    const { container } = render(<AnimatedCount value={undefined} />);
    expect(container.textContent).toBe('');
  });
});
