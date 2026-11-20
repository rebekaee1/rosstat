/**
 * Возврат прокрутки при переходе «назад/вперёд» внутри сайта (правка 16).
 * Страница под курсором может быть ещё не дорисована (чанк, данные), поэтому ждём, пока у документа хватит высоты,
 * и только тогда ставим прежнее место. Касание, колесо или клавиша отменяют возврат: человек уже сам ведёт страницу.
 * Возвращает функцию отмены.
 */
export function restoreScrollTo(y, { tries = 40, step = 150 } = {}) {
  if (typeof window === 'undefined' || !(y > 0)) return () => {};
  let n = 0;
  let timer = 0;
  let stopped = false;
  const stop = () => {
    stopped = true;
    window.clearTimeout(timer);
    window.removeEventListener('wheel', stop);
    window.removeEventListener('touchstart', stop);
    window.removeEventListener('keydown', stop);
  };
  window.addEventListener('wheel', stop, { passive: true, once: true });
  window.addEventListener('touchstart', stop, { passive: true, once: true });
  window.addEventListener('keydown', stop, { once: true });
  const tick = () => {
    if (stopped) return;
    const max = Math.max(0, document.documentElement.scrollHeight - window.innerHeight);
    if (max >= y - 4 || n >= tries) {
      window.scrollTo({ top: Math.min(y, max), left: 0, behavior: 'instant' });
      stop();
      return;
    }
    n += 1;
    timer = window.setTimeout(tick, step);
  };
  tick();
  return stop;
}
