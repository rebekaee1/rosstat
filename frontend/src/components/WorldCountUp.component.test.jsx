import { afterEach, describe, expect, it, vi } from 'vitest';
import { act, render, screen } from '@testing-library/react';
import WorldCountUp from './WorldCountUp';

const format = (value) => String(Math.round(value));

afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals(); vi.useRealTimers(); });

describe('WorldCountUp', () => {
  it('starts from zero, ends on the value and exposes only the final text to screen readers', () => {
    vi.useFakeTimers();
    let now = 0;
    vi.spyOn(performance, 'now').mockImplementation(() => now);
    vi.stubGlobal('requestAnimationFrame', (callback) => setTimeout(() => callback(now), 16));
    vi.stubGlobal('cancelAnimationFrame', (id) => clearTimeout(id));
    const { container } = render(<WorldCountUp value={200} format={format} label="Значение" />);
    expect(container.querySelector('[aria-hidden="true"]').textContent).toBe('0');
    expect(screen.getByLabelText('Значение').textContent).toBe('200');
    for (let step = 0; step < 60; step += 1) {
      now += 16;
      act(() => { vi.advanceTimersByTime(16); });
    }
    expect(container.querySelector('[aria-hidden="true"]').textContent).toBe('200');
  });

  it('shows the value at once under reduced motion', () => {
    vi.stubGlobal('matchMedia', (query) => ({
      matches: query.includes('reduce'), media: query, addEventListener() {}, removeEventListener() {},
    }));
    const { container } = render(<WorldCountUp value={42} format={format} />);
    expect(container.querySelector('[aria-hidden="true"]').textContent).toBe('42');
  });

  it('renders nothing visible for a missing value', () => {
    const { container } = render(<WorldCountUp value={null} format={format} />);
    expect(container.querySelector('[aria-hidden="true"]').textContent).toBe('');
  });
  it('shows the final value at once when counting from zero is switched off', () => {
    vi.useFakeTimers();
    let now = 0;
    vi.spyOn(performance, 'now').mockImplementation(() => now);
    vi.stubGlobal('requestAnimationFrame', (callback) => setTimeout(() => callback(now), 16));
    vi.stubGlobal('cancelAnimationFrame', (id) => clearTimeout(id));
    const { container, rerender } = render(<WorldCountUp value={200} format={format} fromZero={false} />);
    expect(container.querySelector('[aria-hidden="true"]').textContent).toBe('200');
    act(() => { vi.advanceTimersByTime(48); });
    expect(container.querySelector('[aria-hidden="true"]').textContent).toBe('200');
    rerender(<WorldCountUp value={300} format={format} fromZero={false} />);
    expect(container.querySelector('[aria-hidden="true"]').textContent).not.toBe('');
  });

  it('jumps to the final value when the first frame arrives late because the page was busy', () => {
    vi.useFakeTimers();
    let now = 0;
    vi.spyOn(performance, 'now').mockImplementation(() => now);
    vi.stubGlobal('requestAnimationFrame', (callback) => setTimeout(() => callback(now), 16));
    vi.stubGlobal('cancelAnimationFrame', (id) => clearTimeout(id));
    const { container } = render(<WorldCountUp value={1000} format={format} />);
    expect(container.querySelector('[aria-hidden="true"]').textContent).toBe('0');
    now = 400;
    act(() => { vi.advanceTimersByTime(16); });
    expect(container.querySelector('[aria-hidden="true"]').textContent).toBe('1000');
  });
});
