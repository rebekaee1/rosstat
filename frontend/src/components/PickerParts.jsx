import { cn } from '../lib/format';
import '../styles/indicator-russia.css';

const SOFT = { '--fe-duration': '0.3s', '--fe-rise': '8px' };

/**
 * Общая оболочка переключателей показа (режим, частота, состав). `compact` — тело без карточки:
 * его вкладывает родитель, у которого карточка своя.
 */
export function PickerCard({ compact = false, className, children }) {
  if (compact) return children;
  return (
    <section className={cn('fe-reveal fe-reveal--free fe-pick-card', className)} style={SOFT}>
      {children}
    </section>
  );
}

/** Подпись блока: обычный регистр, не «капс с разрядкой». */
export function PickerLabel({ children, className }) {
  return <p className={cn('fe-pick-label', className)}>{children}</p>;
}

/** Одна строка-пояснение под выбранным вариантом. */
export function PickerHint({ children }) {
  if (!children) return null;
  return <p className="fe-pick-hint" role="note">{children}</p>;
}
