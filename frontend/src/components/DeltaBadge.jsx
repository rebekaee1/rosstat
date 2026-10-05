import { cn } from '../lib/format';
import { deltaTone, deltaArrow } from '../lib/deltaTone';

// Стрелки-треугольники читаются мгновенно и не зависят от шрифта; «ровно» — короткое тире.
const GLYPH = { '↗': '▲', '↘': '▼', '→': '–' };

/**
 * Изменение со стрелкой ▲▼ на мягкой цветной плашке: цвет задаёт смысл (хорошо, плохо, нейтрально).
 * `children` — уже отформатированное значение с единицей. `plain` убирает плашку (для плотных таблиц).
 */
export default function DeltaBadge({ delta, polarity = 'neutral', plain = false, className, children }) {
  const tone = deltaTone(delta, polarity);
  const arrow = deltaArrow(delta);
  return (
    <span className={cn('fe-delta-badge', `fe-tone--${tone}`, plain && 'fe-delta-badge--plain', className)}>
      <span aria-hidden="true">{GLYPH[arrow] || arrow}</span>
      {children}
    </span>
  );
}
