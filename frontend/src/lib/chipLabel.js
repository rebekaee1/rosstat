/**
 * Подпись чипа: до двух строк, лишнее скрывается многоточием. Чтобы полное имя не терялось,
 * длинная строковая подпись дублируется в `title` (подсказка при наведении).
 */
export const CHIP_TITLE_MIN_LENGTH = 22;

/** Значение `title` для чипа: явный title побеждает; для длинной строки подставляется она сама. */
export function chipTitleFor(children, title) {
  if (title !== undefined) return title;
  if (typeof children !== 'string') return undefined;
  const text = children.trim();
  return text.length >= CHIP_TITLE_MIN_LENGTH ? text : undefined;
}
