/**
 * Тесты чистой логики behavior.js (иерархический путь элемента).
 * Среда vitest — node (без jsdom), поэтому DOM-узлы имитируются минимальным
 * интерфейсом: tagName / id / classList / getAttribute / parentElement / children.
 */
import { describe, it, expect } from 'vitest';
import { _elementPath, isAutomationUa, createAttentionClock } from './behavior';

function el(tag, { id = '', classes = [], attrs = {}, parent = null } = {}) {
  const node = {
    nodeType: 1,
    tagName: tag.toUpperCase(),
    id,
    classList: classes,
    parentElement: parent,
    children: [],
    getAttribute: (name) => attrs[name] ?? null,
  };
  if (parent) parent.children.push(node);
  return node;
}

describe('elementPath', () => {
  it('останавливается на id — выше не поднимается', () => {
    const root = el('div', { id: 'chart-panel' });
    const btn = el('button', { classes: ['forecast-btn'], parent: root });
    expect(_elementPath(btn)).toBe('div#chart-panel > button.forecast-btn');
  });

  it('предпочитает data-track и aria-label шумным классам', () => {
    const wrap = el('nav', { attrs: { 'aria-label': 'Главное меню' } });
    const link = el('a', { attrs: { 'data-track': 'nav-cpi' }, parent: wrap });
    expect(_elementPath(link)).toBe('nav[Главное меню] > a[nav-cpi]');
  });

  it('отбрасывает tailwind-утилиты, берёт смысловые классы', () => {
    const div = el('div', { classes: ['px-6', 'hover:bg-red', 'chart-card', 'flex'] });
    expect(_elementPath(div)).toBe('div.chart-card');
  });

  it('нумерует одинаковые сиблинги через nth-of-type', () => {
    const ul = el('ul');
    el('li', { parent: ul });
    const second = el('li', { parent: ul });
    el('li', { parent: ul });
    expect(_elementPath(second)).toBe('ul > li:nth-of-type(2)');
  });

  it('ограничивает глубину и длину пути', () => {
    let parent = null;
    let node = null;
    for (let i = 0; i < 12; i++) {
      node = el('div', { classes: [`level-${i}`], parent });
      parent = node;
    }
    const path = _elementPath(node);
    expect(path.split(' > ').length).toBeLessThanOrEqual(6);
    expect(path.length).toBeLessThanOrEqual(380);
  });
});

describe('isAutomationUa', () => {
  it('webdriver — всегда автоматизация', () => {
    expect(isAutomationUa('Mozilla/5.0 Chrome/145', true)).toBe(true);
  });

  it('HeadlessChrome и Cursor — шум', () => {
    expect(isAutomationUa('Mozilla/5.0 HeadlessChrome/145.0.0.0')).toBe(true);
    expect(isAutomationUa('Mozilla/5.0 Cursor/3.18.25 Chrome/144 Electron/40')).toBe(true);
  });

  it('обычный Chrome — не шум', () => {
    expect(isAutomationUa('Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/145.0.0.0')).toBe(false);
  });
});

describe('attention clock', () => {
  it('does not turn a passive 2.8-second load into input activity', () => {
    const clock = createAttentionClock();
    clock.reset(0, true);
    expect(clock.snapshot(2800)).toEqual({ active_ms: 0, visible_ms: 2800 });
    clock.input(3000, false, true);
    expect(clock.snapshot(5000)).toEqual({ active_ms: 0, visible_ms: 2200 });
  });

  it('counts trusted visible activity, caps inactivity and never double counts dwell', () => {
    const clock = createAttentionClock();
    clock.reset(0, true);
    clock.input(1000, true, true);
    expect(clock.snapshot(5000)).toEqual({ active_ms: 4000, visible_ms: 5000 });
    expect(clock.snapshot(30000)).toEqual({ active_ms: 11000, visible_ms: 25000 });
    expect(clock.snapshot(30000)).toEqual({ active_ms: 0, visible_ms: 0 });
  });

  it('excludes hidden time and does not treat focus as user input', () => {
    const clock = createAttentionClock();
    clock.reset(0, true);
    clock.input(1000, true, true);
    clock.visibility(2000, false);
    clock.input(3000, true, false);
    clock.visibility(10000, true);
    expect(clock.snapshot(12000)).toEqual({ active_ms: 1000, visible_ms: 4000 });
    clock.reset(12000, false);
    expect(clock.snapshot(20000)).toEqual({ active_ms: 0, visible_ms: 0 });
  });
});
