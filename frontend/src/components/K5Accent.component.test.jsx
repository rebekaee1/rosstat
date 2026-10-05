// K5: золотое слово-акцент не меняет текст заголовка; осколок пустого места декоративен.
import { describe, expect, it } from 'vitest';
import { render } from '@testing-library/react';
import AccentTitle, { EmptyShard } from './K5Accent';
import { splitAccent } from '../lib/k5Accent';

describe('AccentTitle', () => {
  it('заворачивает последнее слово в .k5-accent, textContent прежний', () => {
    const { container } = render(<h1><AccentTitle text="Валовой внутренний продукт в текущих ценах" /></h1>);
    const accent = container.querySelector('.k5-accent');
    expect(accent?.textContent).toBe('ценах');
    expect(container.querySelector('h1').textContent).toBe('Валовой внутренний продукт в текущих ценах');
  });

  it('знаки в конце остаются вне акцента', () => {
    expect(splitAccent('ВВП (текущие цены)')).toEqual({ head: 'ВВП (текущие ', word: 'цены', tail: ')' });
    expect(splitAccent('Что дальше?')).toEqual({ head: 'Что ', word: 'дальше', tail: '?' });
  });

  it('одно слово и короткий хвост остаются без акцента', () => {
    expect(splitAccent('Инфляция')).toBeNull();
    expect(splitAccent('Цены на ТВ')).toBeNull();
    const { container } = render(<h1><AccentTitle text="Инфляция" /></h1>);
    expect(container.querySelector('.k5-accent')).toBeNull();
    expect(container.textContent).toBe('Инфляция');
  });

  it('пустой текст не падает', () => {
    const { container } = render(<h1><AccentTitle text="" /></h1>);
    expect(container.textContent).toBe('');
  });
});

describe('EmptyShard', () => {
  it('рисуется как скрытая от скринридера иконка заданного размера', () => {
    const { container } = render(<EmptyShard size={72} />);
    const svg = container.querySelector('svg.k5-shard');
    expect(svg).toBeTruthy();
    expect(svg.getAttribute('aria-hidden')).toBe('true');
    expect(svg.getAttribute('width')).toBe('72');
  });
});
