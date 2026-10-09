import { describe, expect, it } from 'vitest';
import { planViewportFit } from './useKeepInViewport';

const view = { width: 820, height: 1000, top: 120, anchorTop: 400, gap: 8, bottomClear: 0 };

describe('planViewportFit (круг 11, G, U12)', () => {
  it('панель внутри окна не двигается', () => {
    expect(planViewportFit({ left: 300, right: 540, top: 440, bottom: 600 }, view)).toEqual({ dx: 0, flipUp: false, scrollBy: 0 });
  });

  it('вылезла за левый край: сдвиг вправо до отступа 12 px', () => {
    expect(planViewportFit({ left: -60, right: 180, top: 440, bottom: 600 }, view).dx).toBe(72);
  });

  it('вылезла за правый край: сдвиг влево', () => {
    expect(planViewportFit({ left: 700, right: 940, top: 440, bottom: 600 }, view).dx).toBe(-132);
  });

  it('не хватает места снизу, а сверху достаточно: ставим над кнопкой', () => {
    const plan = planViewportFit({ left: 300, right: 540, top: 880, bottom: 1040 }, { ...view, anchorTop: 872 });
    expect(plan.flipUp).toBe(true);
    expect(plan.scrollBy).toBe(0);
  });

  it('не хватает места ни снизу, ни сверху: прокрутка страницы на недостающее', () => {
    const plan = planViewportFit({ left: 300, right: 540, top: 150, bottom: 1030 }, { ...view, anchorTop: 140 });
    expect(plan.flipUp).toBe(false);
    expect(plan.scrollBy).toBe(42);
  });

  it('нижняя панель и плашки сокращают рабочую высоту окна', () => {
    const plan = planViewportFit({ left: 300, right: 540, top: 700, bottom: 960 }, { ...view, bottomClear: 100, anchorTop: 692 });
    expect(plan.flipUp).toBe(true);
  });
});
