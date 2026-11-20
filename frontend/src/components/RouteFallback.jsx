import { useEffect, useState } from 'react';
import { SkeletonBox } from './Skeleton';
import LoadingNote from './LoadingNote';
import { isLanguageSwitchLanding } from '../i18n/langScroll';

/**
 * Серверная разметка страницы, снятая ДО первого рендера React (createRoot стирает #root).
 * Модуль выполняется при импорте приложения, раньше mountApp, поэтому #root ещё не тронут.
 * Берём только настоящую страницу (есть h1 и заметный объём), не пустую оболочку.
 */
function readServerMarkup() {
  try {
    if (typeof document === 'undefined') return null;
    const root = document.getElementById('root');
    if (!root || !root.querySelector('h1')) return null;
    const html = root.innerHTML;
    return html.length > 400 ? html : null;
  } catch {
    return null;
  }
}
let serverMarkup = readServerMarkup();

/** Загрузка после возврата назад/вперёд или смены языка: заставку и каркас не показываем. */
function readReturnLanding() {
  try {
    if (typeof performance !== 'undefined' && performance.getEntriesByType) {
      const nav = performance.getEntriesByType('navigation')[0];
      if (nav && nav.type === 'back_forward') return true;
    }
  } catch { /* нет Navigation Timing */ }
  return isLanguageSwitchLanding();
}
let returnLanding = readReturnLanding();

/**
 * Что видно, пока подгружается чанк страницы. Правка 16:
 * 1. Страница пришла с сервера с содержимым: пока чанк едет, остаётся эта же разметка (без «Загружаем…» и каркаса).
 * 2. Возврат назад, смена языка (`quiet`): ничего не рисуем, только держим высоту, чтобы место прокрутки не терялось.
 * 3. Иначе (переход внутри сайта на ещё не загруженную страницу): полоса прогресса, подпись «Загружаем данные…»
 *    (через 5 с кнопка «Обновить») и каркас страницы (крошка, шапка, плитки, график).
 */
export default function RouteFallback({ quiet = false }) {
  const [held] = useState(() => serverMarkup);
  const [startedQuiet] = useState(() => returnLanding);
  useEffect(() => () => { serverMarkup = null; returnLanding = false; }, []);

  if (held) {
    return (
      <div
        className="fe-container fe-route-shell fe-ssr-hold pt-24 md:pt-28"
        data-testid="ssr-hold"
        aria-hidden="true"
        inert
        dangerouslySetInnerHTML={{ __html: held }}
      />
    );
  }
  if (quiet || startedQuiet) {
    return <div className="fe-route-shell" data-testid="route-quiet" aria-busy="true" />;
  }
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
