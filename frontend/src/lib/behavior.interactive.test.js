// 18.11.2026: клик считается «в некликабельное» (dead), если цель не входит в список управляющих элементов.
// Дорожка рамки периода под графиком — рабочее управление (перенос и перетаскивание окна), но без кнопки и ссылки:
// за 17.11 шесть человек пользовались ею, и Пульс записал 24 клика «в пустоту».
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';

const here = dirname(fileURLToPath(import.meta.url));
const behavior = readFileSync(join(here, 'behavior.js'), 'utf8');
const brush = readFileSync(join(here, '..', 'components', 'ChartBrush.jsx'), 'utf8');

describe('список управляющих элементов для признака dead', () => {
  const selector = behavior.match(/const INTERACTIVE = '([^']+)'/)?.[1] || '';

  it('включает ползунки и явную пометку data-interactive', () => {
    expect(selector.split(',')).toEqual(expect.arrayContaining(['[role="slider"]', '[data-interactive]']));
  });

  it('прежние элементы на месте', () => {
    expect(selector.split(',')).toEqual(expect.arrayContaining(['a', 'button', 'input', 'select', 'label', '[role="button"]', '[onclick]']));
  });

  it('дорожка рамки периода помечена как управление', () => {
    expect(brush).toMatch(/className="fe-brush__track"\s+data-interactive=""\s+onPointerDown=\{jump\}/);
  });
});
