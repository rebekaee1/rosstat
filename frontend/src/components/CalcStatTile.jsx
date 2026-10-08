// Итоговые плитки калькуляторов: сетка 2 в ряд, плитки одной ширины и высоты (на телефоне
// не «лесенка»); нечётная последняя растягивается на весь ряд, чтобы не оставалось дыры.
// Подпись — обычным регистром, значение — крупно, цифры одной ширины (tabular-nums).
import { cn } from '../lib/format';
import { revealStyle } from '../lib/calcUi';
import '../styles/w5-tools.css';

export function CalcStatTile({ label, value, accent = false, index = 0, className }) {
  return (
    <div style={{ ...revealStyle(index + 4), '--w5-chars': Math.max(4, String(value ?? '').length) }} className={cn('w5-tile fe-reveal fe-reveal--free', accent && 'w5-tile--accent', className)}>
      <p className="w5-tile__label">{label}</p>
      <p className="w5-tile__value">{value}</p>
    </div>
  );
}

export function CalcStatGrid({ children, className }) {
  return <div className={cn('w5-tiles', className)}>{children}</div>;
}
