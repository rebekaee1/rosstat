import { SkeletonBox } from './Skeleton';
import LoadingNote from './LoadingNote';

/**
 * Что видно, пока подгружается чанк страницы: тонкая полоса прогресса сверху, подпись «Загружаем данные…»
 * (через 8 с к ней добавляется кнопка «Обновить») и каркас страницы (крошка, шапка, два блока):
 * контент не «прыгает» при появлении. Серверный текст человеку не показываем, роботам он остаётся в HTML.
 */
export default function RouteFallback() {
  return (
    <div className="fe-container fe-route-shell pt-24 md:pt-28" role="status" aria-busy="true" aria-live="polite">
      <span className="fe-page-progress" aria-hidden="true" />
      <LoadingNote className="mb-4" />
      {/* Каркас виден сразу (без задержки появления) и повторяет форму страницы: крошка, шапка, плитки значений, график. */}
      <div className="fe-route-skel" aria-hidden="true">
        <SkeletonBox className="mb-5 h-3 w-40 rounded" />
        <div className="fe-glass mb-4 rounded-[1.5rem] p-5 md:p-6">
          <SkeletonBox className="mb-4 h-3 w-24 rounded" />
          <SkeletonBox className="mb-3 h-9 w-3/4 max-w-xl rounded-lg" />
          <SkeletonBox className="h-4 w-1/2 max-w-md rounded" />
        </div>
        <div className="fe-route-skel__tiles mb-4">
          {[0, 1, 2].map((i) => (
            <div
              key={i}
              className={`fe-glass rounded-[1.5rem] p-4 ${i === 2 ? 'hidden md:block' : ''}`}
            >
              <SkeletonBox className="mb-3 h-3 w-20 rounded" />
              <SkeletonBox className="mb-2 h-8 w-24 rounded-lg" />
              <SkeletonBox className="h-3 w-16 rounded" />
            </div>
          ))}
        </div>
        <SkeletonBox className="h-64 w-full rounded-[1.5rem] sm:h-80" />
      </div>
    </div>
  );
}
