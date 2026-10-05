import { afterEach, describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import CountUp from './CountUp';

afterEach(() => vi.restoreAllMocks());

const format = (n) => `${Math.round(n)}`;

describe('CountUp', () => {
  it('итоговый текст лежит в разметке сразу (поиск, скринридер, печать)', () => {
    render(<CountUp value={268} format={format} group="t-static" />);
    expect(screen.getByText('268')).toBeTruthy();
  });

  it('в экране: набегает от нуля и приходит к итоговому тексту; повторно в той же группе не играет', () => {
    const frames = [];
    vi.spyOn(window, 'requestAnimationFrame').mockImplementation((callback) => { frames.push(callback); return frames.length; });
    vi.spyOn(window, 'cancelAnimationFrame').mockImplementation(() => {});
    vi.spyOn(Element.prototype, 'getBoundingClientRect').mockReturnValue({
      width: 60, height: 30, top: 100, bottom: 130, left: 0, right: 60, x: 0, y: 100, toJSON: () => ({}),
    });
    const { container, unmount } = render(<CountUp value={100} format={format} group="t-play" text="100" />);
    expect(container.textContent).toBe('0');
    const run = (time) => frames.splice(0).forEach((callback) => callback(time));
    run(16);
    run(466);
    expect(Number(container.textContent)).toBeGreaterThan(0);
    run(2000);
    expect(container.textContent).toBe('100');
    unmount();
    // Группа уже сыграла: второй экземпляр показывает итог сразу.
    const second = render(<CountUp value={100} format={format} group="t-play" text="100" />);
    expect(second.container.textContent).toBe('100');
  });

  it('«уменьшить движение»: счёта нет, сразу итог', () => {
    vi.spyOn(window, 'matchMedia').mockImplementation((query) => ({ matches: /reduce/.test(query), addEventListener() {}, removeEventListener() {} }));
    vi.spyOn(Element.prototype, 'getBoundingClientRect').mockReturnValue({
      width: 60, height: 30, top: 100, bottom: 130, left: 0, right: 60, x: 0, y: 100, toJSON: () => ({}),
    });
    const { container } = render(<CountUp value={55} format={format} group="t-reduced" />);
    expect(container.textContent).toBe('55');
  });
});
