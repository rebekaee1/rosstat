import { forwardRef } from 'react';
import { cn } from '../lib/format';
import { chipTitleFor } from '../lib/chipLabel';

/** Строковая подпись чипа: до двух строк по словам, без обрезки посреди слова (стили `.fe-chip__label`). */
export function ChipLabel({ children }) {
  return typeof children === 'string' ? <span className="fe-chip__label">{children}</span> : children;
}

/**
 * Единая «пилюля»-переключатель (режимы показателя, частота, диапазон графика).
 * `active` → aria-pressed и заливка; цель нажатия 44 px на сенсорных экранах без раздувания вида на компьютере.
 * Длинная подпись переносится на вторую строку; полное имя доступно в `title`.
 */
const Chip = forwardRef(function Chip({ active = false, className, children, type = 'button', title, ...rest }, ref) {
  return (
    <button
      ref={ref}
      type={type}
      aria-pressed={active}
      title={chipTitleFor(children, title)}
      className={cn('fe-chip fe-press', active && 'is-active', className)}
      {...rest}
    >
      <ChipLabel>{children}</ChipLabel>
    </button>
  );
});

export default Chip;
