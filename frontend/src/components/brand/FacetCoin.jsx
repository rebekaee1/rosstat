import { cn } from '../../lib/format';
import '../../styles/k2-brand.css';

/**
 * Иконка категории (круг 6, зона P): простой круг L2 с иконкой графитового цвета. Прежняя «грань-монета» (шестигранный камень
 * с бликом и тенью) снята как «игровая» (принцип владельца 2). Имя компонента и свойства прежние: `tone` принимается и
 * игнорируется, чтобы вызовы не менялись; `size` — диаметр круга в px; `children` — иконка.
 */
// eslint-disable-next-line no-unused-vars
export default function FacetCoin({ tone, size = 44, children, className }) {
  return (
    <span className={cn('fe-coin', className)} style={{ '--fe-coin-size': `${size}px` }}>
      <span className="fe-coin__icon" aria-hidden="true">{children}</span>
    </span>
  );
}
