import { useEffect, useRef } from 'react';

/**
 * Блик-проход по «камню» результата при пересчёте (раунд 3, K8.3).
 *
 * Блок с классом `.fe-glint` (K1, styles/k1-scene.css) сам проигрывает проход один раз при появлении: lib/useLightPointer.js
 * ставит `data-fe-glint="on"`, а по окончании анимации `done`. Здесь тот же атрибут возвращается из `done` в `on`,
 * когда значение результата изменилось, и браузер проигрывает блик заново. Пока проход идёт (`on`) и до первого
 * появления (атрибута нет) ничего не делается: повтор не наслаивается на текущий.
 */
export function replayGlint(el) {
  if (!el || typeof el.getAttribute !== 'function') return false;
  if (el.getAttribute('data-fe-glint') !== 'done') return false;
  el.setAttribute('data-fe-glint', 'on');
  return true;
}

/** Хук: при смене `value` (кроме первого показа) повторяет блик на элементе из `ref`. */
export function useGlintOnChange(ref, value) {
  const first = useRef(true);
  useEffect(() => {
    if (first.current) {
      first.current = false;
      return;
    }
    replayGlint(ref.current);
  }, [ref, value]);
}
