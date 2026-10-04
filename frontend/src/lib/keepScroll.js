// Переключение «Список / Карта» и смена показателя меняют адрес, а общий ScrollToTop бросает страницу
// в начало. Эти переходы — в пределах одного экрана, поэтому запоминаем позицию и возвращаем её.
import { useEffect } from 'react';
import { useLocation } from 'react-router-dom';

let pendingY = null;

/** Вызвать перед navigate(): после смены адреса прокрутка вернётся на то же место. */
export function rememberScroll() {
  if (typeof window !== 'undefined') pendingY = window.scrollY;
}

/** Хук страницы: восстанавливает запомненную позицию после смены pathname. */
export function useRestoreScroll() {
  const { pathname } = useLocation();
  useEffect(() => {
    if (pendingY == null) return undefined;
    const y = pendingY;
    pendingY = null;
    // Кадр не отменяем: общий ScrollToTop срабатывает в том же коммите, наш возврат идёт после него.
    requestAnimationFrame(() => {
      window.scrollTo({ top: y, left: 0, behavior: 'instant' });
    });
    return undefined;
  }, [pathname]);
}
