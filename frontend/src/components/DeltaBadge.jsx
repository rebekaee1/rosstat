import { cn } from '../lib/format';
import { deltaTone, deltaArrow } from '../lib/deltaTone';
import '../styles/c10c-delta.css';

// Стрелки-треугольники читаются мгновенно и не зависят от шрифта; «ровно» — короткое тире.
const GLYPH = { '↗': '▲', '↘': '▼', '→': '–' };

/**
 * Изменение на нейтральной стеклянной плашке (круг 6) с маркером ▲▼: цвет маркера задаёт смысл (хорошо, плохо, нейтрально),
 * сама плашка не заливается цветом. Круг 10 (Г3): число с явным знаком «+» или «−» тоже окрашено в цвет смысла (c10c-delta.css).
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
