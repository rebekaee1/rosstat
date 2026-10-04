import { Link } from 'react-router-dom';
import { cn } from '../lib/format';
import '../styles/chart-controls.css';

/**
 * Контейнер для рядов `Chip` / `ChipLink`: role="group" + подпись для скринридера.
 * `nowrap` — один горизонтальный ряд с прокруткой (узкие экраны).
 * `grid` — ровная сетка равных ячеек (2 колонки на телефоне, нечётная последняя на всю ширину) вместо рваных рядов.
 */
export default function ChipGroup({ label, nowrap = false, grid = false, className, children, ...rest }) {
  return (
    <div
      role="group"
      aria-label={label || undefined}
      className={cn('fe-chip-row', nowrap && 'fe-chip-row--nowrap', grid && 'fe-chip-row--grid', className)}
      {...rest}
    >
      {children}
    </div>
  );
}

/**
 * Чип-ссылка (смена частоты, срез показателя): навигация, поэтому aria-current, а не aria-pressed.
 * Внешний вид — тот же `.fe-chip`, что у `Chip`.
 */
export function ChipLink({ active = false, className, children, ...rest }) {
  return (
    <Link
      aria-current={active ? 'page' : undefined}
      className={cn('fe-chip fe-press', active && 'is-active', className)}
      {...rest}
    >
      {children}
    </Link>
  );
}
