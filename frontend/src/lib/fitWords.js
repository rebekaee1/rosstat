/**
 * Круг 13, V4: длинное слово в узкой колонке («Великобритания» в списке стран) не рвётся посреди слова.
 * Перенос идёт только по пробелам и дефисам (CSS `overflow-wrap: normal`); если одно слово всё равно шире колонки, кегль
 * уменьшается шагом 0,5 px до `min`, а если и тогда не помещается, остаётся однострочное многоточие (полное название лежит в `title`).
 */
export function fitWordsInBoxes(boxes, { min = 11, step = 0.5 } = {}) {
  const over = (el) => el.scrollWidth > el.clientWidth + 0.5;
  for (const el of boxes) {
    if (!el) continue;
    el.style.fontSize = '';
    el.style.display = '';
    el.style.whiteSpace = '';
    el.style.textOverflow = '';
    if (!over(el)) continue;
    const base = parseFloat(getComputedStyle(el).fontSize) || 15;
    let size = base;
    while (size - step >= min && over(el)) {
      size -= step;
      el.style.fontSize = `${size}px`;
    }
    if (over(el)) {
      el.style.display = 'block';
      el.style.whiteSpace = 'nowrap';
      el.style.textOverflow = 'ellipsis';
    }
  }
}
