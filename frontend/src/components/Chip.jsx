import { forwardRef } from 'react';
import { cn } from '../lib/format';

/**
 * Единая «пилюля»-переключатель (режимы показателя, частота, диапазон графика).
 * `active` → aria-pressed и заливка; цель нажатия 44 px на сенсорных экранах без раздувания вида на компьютере.
 */
const Chip = forwardRef(function Chip({ active = false, className, children, type = 'button', ...rest }, ref) {
  return (
    <button
      ref={ref}
      type={type}
      aria-pressed={active}
      className={cn('fe-chip fe-press', active && 'is-active', className)}
      {...rest}
    >
      {children}
    </button>
  );
});

export default Chip;
