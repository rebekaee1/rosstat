// «Было / стало»: два столбика, высота которых пропорциональна сумме. Видно сразу, во сколько раз изменилась
// покупательная способность, ещё до чтения чисел. Подписи под столбиками: год и сумма с валютой.
import { cn } from '../lib/format';
import '../styles/w6-g.css';

/**
 * before / after: { label, value, text }. Больший столбик занимает всю высоту, меньший пропорционально
 * (но не ниже 12 %, чтобы был виден). `emphasis` помечает столбик, ради которого строился расчёт.
 */
export default function CalcBeforeAfter({ before, after, ariaLabel }) {
  const max = Math.max(Number(before.value) || 0, Number(after.value) || 0) || 1;
  const height = (value) => `${Math.max(12, Math.round(((Number(value) || 0) / max) * 100))}%`;
  const bars = [
    { ...before, tone: 'was' },
    { ...after, tone: 'now' },
  ];
  return (
    <figure className="fe-w6g-ba" role="img" aria-label={ariaLabel}>
      {bars.map((bar) => (
        <div key={bar.tone} className="fe-w6g-ba__col">
          <span className="fe-w6g-ba__value">{bar.text}</span>
          <div className="fe-w6g-ba__track" aria-hidden="true">
            <div className={cn('fe-w6g-ba__bar', `fe-w6g-ba__bar--${bar.tone}`)} style={{ height: height(bar.value) }} />
          </div>
          <span className="fe-w6g-ba__label">{bar.label}</span>
        </div>
      ))}
    </figure>
  );
}
