import { describe, expect, it } from 'vitest';
import { isSliderElement, isTextEntryElement, keyboardOpenBySize } from './dockSuppress';

const el = (html) => {
  const host = document.createElement('div');
  host.innerHTML = html;
  return host.firstElementChild;
};

describe('dockSuppress (круг 11, G)', () => {
  it('ввод текста: поля, textarea, select; кнопки, флажки и бегунки не считаются', () => {
    expect(isTextEntryElement(el('<input>'))).toBe(true);
    expect(isTextEntryElement(el('<input type="search">'))).toBe(true);
    expect(isTextEntryElement(el('<input type="number">'))).toBe(true);
    expect(isTextEntryElement(el('<textarea></textarea>'))).toBe(true);
    expect(isTextEntryElement(el('<select></select>'))).toBe(true);
    expect(isTextEntryElement(el('<input type="checkbox">'))).toBe(false);
    expect(isTextEntryElement(el('<input type="range">'))).toBe(false);
    expect(isTextEntryElement(el('<input type="radio">'))).toBe(false);
    expect(isTextEntryElement(el('<button></button>'))).toBe(false);
    expect(isTextEntryElement(null)).toBe(false);
  });

  it('бегунок: range, role=slider, ручка диапазона графика и их потомки', () => {
    expect(isSliderElement(el('<input type="range">'))).toBe(true);
    expect(isSliderElement(el('<div role="slider"></div>'))).toBe(true);
    const host = el('<div class="recharts-brush-traveller"><span></span></div>');
    expect(isSliderElement(host.firstElementChild)).toBe(true);
    expect(isSliderElement(el('<div></div>'))).toBe(false);
  });

  it('клавиатура открыта, когда видимая область ниже окна больше чем на 140 px', () => {
    expect(keyboardOpenBySize(800, 480)).toBe(true);
    expect(keyboardOpenBySize(800, 700)).toBe(false);
    expect(keyboardOpenBySize(800, undefined)).toBe(false);
  });
});
