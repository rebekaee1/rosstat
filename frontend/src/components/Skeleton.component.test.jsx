import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/react';
import { SkeletonBox, ChartSkeleton, TileSkeleton } from './Skeleton';
import { SparklineSkeleton } from './Sparkline';

describe('Skeleton', () => {
  it('SkeletonBox скрыт от скринридера', () => {
    const { container } = render(<SkeletonBox className="h-4" />);
    expect(container.firstChild.getAttribute('aria-hidden')).toBe('true');
  });

  it('ChartSkeleton по умолчанию 280px, от 640px — 390px, карточка как у реального графика', () => {
    const { container } = render(<ChartSkeleton />);
    const card = container.firstChild;
    expect(card.className).toContain('fe-chart-card');
    expect(card.getAttribute('aria-hidden')).toBe('true');
    const plot = container.querySelector('.rounded-xl');
    expect(plot.className).toContain('h-[280px]');
    expect(plot.className).toContain('sm:h-[390px]');
  });

  it('ChartSkeleton принимает фиксированную высоту', () => {
    const { container } = render(<ChartSkeleton height={480} />);
    const plot = container.querySelector('.rounded-xl');
    expect(plot.style.height).toBe('480px');
    expect(plot.className).not.toContain('h-[280px]');
  });

  it('TileSkeleton и SparklineSkeleton не попадают в дерево доступности', () => {
    const { container } = render(<><TileSkeleton /><SparklineSkeleton height={32} /></>);
    expect(container.children[0].getAttribute('aria-hidden')).toBe('true');
    expect(container.children[1].getAttribute('aria-hidden')).toBe('true');
    expect(container.children[1].style.height).toBe('32px');
  });
});
