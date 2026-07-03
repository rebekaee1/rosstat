/**
 * Тесты чистой логики behavior.js (иерархический путь элемента).
 * Среда vitest — node (без jsdom), поэтому DOM-узлы имитируются минимальным
 * интерфейсом: tagName / id / classList / getAttribute / parentElement / children.
 */
import { describe, it, expect } from 'vitest';
import { _elementPath } from './behavior';

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
