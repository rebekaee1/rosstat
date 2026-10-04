import { useState } from 'react';
import { Link } from 'react-router-dom';
import { cn } from '../lib/format';
import { useT } from '../i18n';
import { splitChipOverflow } from '../lib/chipOverflow';
import Chip from './Chip';
import '../styles/chart-controls.css';
import '../styles/x2-indicator.css';

/**
 * Контейнер для рядов `Chip` / `ChipLink`: role="group" + подпись для скринридера.
 * `nowrap` — один горизонтальный ряд с прокруткой (узкие экраны).
 * `grid` — ровная сетка равных ячеек (2 колонки на телефоне, нечётная последняя на всю ширину) вместо рваных рядов.
 * `dense` — компактный ряд коротких подписей: чипы по ширине текста, строки добиты до края (без рваного хвоста).
 */
export default function ChipGroup({ label, nowrap = false, grid = false, dense = false, className, children, ...rest }) {
  return (
    <div
      role="group"
      aria-label={label || undefined}
      className={cn('fe-chip-row', nowrap && 'fe-chip-row--nowrap', grid && 'fe-chip-row--grid', dense && 'fe-chip-row--dense', className)}
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

/**
 * Ряд чипов с короткой первой строкой и «Ещё режимы» для редких вариантов.
 * Когда чипов не больше `limit`, ведёт себя как обычный `ChipGroup`.
 */
export function OverflowChipGroup({
  items, isActive, renderChip, limit = 6, label, grid = false, dense = false, moreLabel, className,
}) {
  const t = useT();
  const [open, setOpen] = useState(false);
  const { shown, hidden } = splitChipOverflow(items, isActive, limit);
  const list = open ? items : shown;
  return (
    <ChipGroup label={label} grid={grid} dense={dense} className={className}>
      {list.map(renderChip)}
      {hidden.length > 0 && (
        <Chip
          active={false}
          aria-pressed={undefined}
          aria-expanded={open}
          className="fe-chip--more"
          onClick={() => setOpen((v) => !v)}
        >
          {open ? t('x2.picker.less') : `${moreLabel || t('x2.picker.more')} (${hidden.length})`}
        </Chip>
      )}
    </ChipGroup>
  );
}
