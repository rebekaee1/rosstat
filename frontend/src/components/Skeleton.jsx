import { cn } from '../lib/format';

export function SkeletonBox({ className }) {
  return <div className={cn('skeleton', className)} />;
}

export function MetricCardSkeleton() {
  return (
    <div className="p-5 rounded-[1.5rem] border border-border-subtle bg-surface">
      <SkeletonBox className="h-3 w-20 mb-4" />
      <SkeletonBox className="h-8 w-28 mb-3" />
      <SkeletonBox className="h-4 w-24" />
    </div>
  );
}

export function ChartSkeleton() {
  return (
    <div className="p-6 rounded-[2rem] border border-border-subtle bg-surface">
      <SkeletonBox className="h-5 w-48 mb-6" />
      <SkeletonBox className="h-[300px] w-full rounded-xl" />
    </div>
  );
}

export function TileSkeleton() {
  return (
    <div className="p-5 rounded-[1.5rem] border border-border-subtle bg-surface">
      <SkeletonBox className="h-3 w-16 mb-3" />
      <SkeletonBox className="h-5 w-36 mb-4" />
      <SkeletonBox className="h-8 w-24 mb-2" />
      <SkeletonBox className="h-3 w-32" />
    </div>
  );
}
