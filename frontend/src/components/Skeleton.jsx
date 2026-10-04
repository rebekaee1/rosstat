import { cn } from '../lib/format';

/** Декоративная заглушка: скринридеру не нужна, о состоянии сообщает обёртка (aria-busy / role="status"). */
export function SkeletonBox({ className, style }) {
  return <div className={cn('skeleton', className)} style={style} aria-hidden="true" />;
}

/**
 * Каркас графика. Радиус и поля — как у настоящей карточки (`.fe-panel.fe-chart-card`), высота плота —
 * как у IndicatorChart (280 на узком, 390 от 640px), чтобы при подмене на график страница не прыгала.
 * `height` задаёт фиксированную высоту плота (px) на любой ширине.
 */
export function ChartSkeleton({ height }) {
  const fixed = Number.isFinite(height) && height > 0;
  return (
    <div className="fe-panel fe-chart-card" aria-hidden="true">
      <SkeletonBox className="mb-5 h-5 w-48 max-w-full" />
      <SkeletonBox
        className={cn('w-full rounded-xl', !fixed && 'h-[280px] sm:h-[390px]')}
        style={fixed ? { height } : undefined}
      />
    </div>
  );
}

export function TileSkeleton() {
  return (
    <div className="p-5 rounded-[1.5rem] border border-border-subtle bg-surface" aria-hidden="true">
      <SkeletonBox className="h-3 w-16 mb-3" />
      <SkeletonBox className="h-5 w-36 mb-4" />
      <SkeletonBox className="h-8 w-24 mb-2" />
      <SkeletonBox className="h-3 w-32" />
    </div>
  );
}
