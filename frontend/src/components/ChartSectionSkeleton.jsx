import { useLayoutEffect, useRef, useState } from 'react';
import { SkeletonBox } from './Skeleton';
import { chartPlotHeight } from './chartLayout';
import { useT } from '../i18n';
import '../styles/chart-controls.css';

/**
 * Скелетон карточки графика: та же оболочка (`.fe-panel .fe-chart-card`, радиус и отступы) и та же высота плота
 * (280/390 по ширине, как у IndicatorChart), чтобы после загрузки страница не «прыгала».
 */
export default function ChartSectionSkeleton() {
  const t = useT();
  const plotRef = useRef(null);
  const [plotWidth, setPlotWidth] = useState(0);

  useLayoutEffect(() => {
    const el = plotRef.current;
    if (!el) return undefined;
    setPlotWidth(el.getBoundingClientRect().width);
    if (typeof ResizeObserver === 'undefined') return undefined;
    const ro = new ResizeObserver((entries) => {
      const w = entries[0]?.contentRect?.width;
      if (w) setPlotWidth(w);
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  return (
    <div className="fe-panel fe-chart-card" data-chart-skeleton="true">
      <span className="sr-only" role="status">{t('chart.loadingAria')}</span>
      <div aria-hidden="true">
        <div className="fe-chart-toolbar mb-5 flex flex-wrap items-center justify-between gap-3">
          <SkeletonBox className="h-5 w-48 max-w-full" />
          <SkeletonBox className="fe-chart-skel-controls w-44 rounded-xl" />
        </div>
        <div ref={plotRef} className="fe-chart-plot relative rounded-xl" style={{ height: chartPlotHeight(plotWidth) }}>
          <SkeletonBox className="h-full w-full rounded-xl" />
        </div>
        <SkeletonBox className="mt-4 ml-auto h-3 w-32" />
      </div>
    </div>
  );
}
