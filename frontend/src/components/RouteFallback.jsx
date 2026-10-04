import { useEffect, useLayoutEffect, useState } from 'react';
import { SkeletonBox } from './Skeleton';
import { useT } from '../i18n';

/**
 * Что видно, пока подгружается чанк страницы: тонкая полоса прогресса сверху и каркас страницы
 * (крошка, шапка, два блока) вместо одного маленького прямоугольника — контент не «прыгает» при появлении.
 */
/** Ставится внутри Suspense после Routes: срабатывает, когда страница реально смонтирована. */
export function SsrHandoffDone() {
  useLayoutEffect(() => { window.__feSsrSnapshot = null; }, []);
  return null;
}

export default function RouteFallback() {
  const t = useT();
  const [held] = useState(() => (typeof window !== 'undefined' ? window.__feSsrSnapshot : null));
  const [slow, setSlow] = useState(false);
  useEffect(() => {
    const timer = setTimeout(() => setSlow(true), 4000);
    return () => clearTimeout(timer);
  }, []);
  if (held) {
    return (
      <>
        <span className="fe-page-progress" aria-hidden="true" />
        <div className="fe-ssr-hold" dangerouslySetInnerHTML={{ __html: held }} />
      </>
    );
  }
  return (
    <div className="mx-auto w-full max-w-7xl px-4 pt-24 pb-16 md:px-8 md:pt-28" role="status" aria-busy="true" aria-live="polite">
      <span className="fe-page-progress" aria-hidden="true" />
      <span className={slow ? 'mb-4 block text-sm text-text-secondary' : 'sr-only'}>{slow ? t('route.slow') : '…'}</span>
      <div className="fe-reveal" style={{ '--fe-delay': '0.15s' }} aria-hidden="true">
        <SkeletonBox className="mb-6 h-3 w-40 rounded" />
        <div className="mb-6 rounded-[1.5rem] border border-border-subtle bg-surface p-6">
          <SkeletonBox className="mb-4 h-3 w-24 rounded" />
          <SkeletonBox className="mb-3 h-9 w-3/4 max-w-xl rounded-lg" />
          <SkeletonBox className="h-4 w-1/2 max-w-md rounded" />
        </div>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <SkeletonBox className="h-28 rounded-[1.5rem]" />
          <SkeletonBox className="h-28 rounded-[1.5rem]" />
        </div>
      </div>
    </div>
  );
}
