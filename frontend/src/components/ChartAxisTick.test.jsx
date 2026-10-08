/** @vitest-environment jsdom */
import { describe, expect, it } from 'vitest';
import { render } from '@testing-library/react';
import EdgeAwareTick from './ChartAxisTick';

function anchorOf(props) {
  const { container } = render(<svg><EdgeAwareTick y={10} payload={{ value: '29 сентября 2026' }} {...props} /></svg>);
  return container.querySelector('text').getAttribute('text-anchor');
}

describe('EdgeAwareTick', () => {
  it('середина графика подписана по центру', () => {
    expect(anchorOf({ x: 200, minX: 40, maxX: 400 })).toBe('middle');
  });
  it('последняя подпись у правого края прижата внутрь, а не обрезана', () => {
    expect(anchorOf({ x: 395, minX: 40, maxX: 400 })).toBe('end');
  });
  it('первая подпись не заезжает на ось Y', () => {
    expect(anchorOf({ x: 42, minX: 40, maxX: 400 })).toBe('start');
  });
});
