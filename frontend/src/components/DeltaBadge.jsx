import { cn } from '../lib/format';
import { deltaTone, deltaArrow } from '../lib/deltaTone';

/** Изменение со стрелкой и смысловым цветом; `children` — уже отформатированное значение с единицей. */
export default function DeltaBadge({ delta, polarity = 'neutral', className, children }) {
  const tone = deltaTone(delta, polarity);
  return (
    <span className={cn('fe-delta-badge', `fe-tone--${tone}`, className)}>
      <span aria-hidden="true">{deltaArrow(delta)}</span>
      {children}
    </span>
  );
}
