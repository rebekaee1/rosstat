// Подсказка «Коснитесь графика — увидите значения» (состояние — lib/useChartTouchHint.js)
// и легенда графика: цветной штрих + подпись.
import { Hand } from 'lucide-react';
import { useT } from '../i18n';
import '../styles/w5-tools.css';

export default function ChartTouchHint({ visible }) {
  const t = useT();
  if (!visible) return null;
  return (
    <p className="w5-touch-hint" role="note">
      <Hand className="w5-touch-hint__icon" aria-hidden="true" />
      {t('w5.chart.touchHint')}
    </p>
  );
}

/** items — [{ color, label, dashed }]. */
export function ChartLegend({ items }) {
  return (
    <ul className="w5-legend">
      {items.map((item) => (
        <li key={item.label} className="w5-legend__item">
          <span
            className={item.dashed ? 'w5-legend__swatch w5-legend__swatch--dashed' : 'w5-legend__swatch'}
            style={{ '--w5-swatch': item.color }}
            aria-hidden="true"
          />
          {item.label}
        </li>
      ))}
    </ul>
  );
}
