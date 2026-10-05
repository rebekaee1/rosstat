import { SkeletonBox } from './Skeleton';
import { useT } from '../i18n';
import '../styles/chart-controls.css';
import '../styles/z4-indicator.css';

/**
 * Скелетон карточки графика: та же оболочка (`.fe-panel .fe-chart-card`, радиус и отступы), тот же класс плота
 * (`.z4-plot`: высота зависит от высоты окна, как у самого графика) и та же полоса выбора периода под плотом.
 * Поэтому после загрузки страница не «прыгает», а серый блок не короче и не длиннее готового графика.
 */
export default function ChartSectionSkeleton() {
  const t = useT();

  return (
    <div className="fe-panel fe-chart-card" data-chart-skeleton="true">
      <span className="sr-only" role="status">{t('chart.loadingAria')}</span>
      <div aria-hidden="true">
        <div className="fe-chart-toolbar mb-5 flex flex-wrap items-center justify-between gap-3">
          <SkeletonBox className="h-5 w-48 max-w-full" />
          <SkeletonBox className="fe-chart-skel-controls w-44 rounded-xl" />
        </div>
        <div className="fe-chart-plot z4-plot relative rounded-xl">
          <SkeletonBox className="h-full w-full rounded-xl" />
        </div>
        <SkeletonBox className="z4-skel-brush mt-1.5 w-full rounded-[10px]" />
        <SkeletonBox className="mt-4 ml-auto h-3 w-32" />
      </div>
    </div>
  );
}
