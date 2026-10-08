// Подпись деления оси X, которая не вылезает за край графика: крайние подписи прижимаются внутрь.
// Круг 8 (C4): у Brent последняя подпись «29 сентября» резалась краем карточки, у курса валют первая «Oct» наезжала на подпись оси Y.
import { CHART_THEME } from '../lib/chartTheme';

/** Оценка ширины подписи: цифра и буква ≈ 6,7 px при шрифте 12. */
function labelWidth(text, fontSize) {
  return String(text ?? '').length * fontSize * 0.56;
}

/**
 * Подпись для `<XAxis tick={<EdgeAwareTick … />}>`. Recharts подставляет x, y, payload, index.
 * @param {number} minX левый край области подписей (обычно ширина оси Y)
 * @param {number} maxX правый край (ширина графика минус правое поле)
 * @param {(value: string) => string} [format] как печатать значение
 */
export default function EdgeAwareTick({
  x, y, payload, minX = 0, maxX = Infinity, format, fontSize = CHART_THEME.tickSize,
}) {
  if (!Number.isFinite(x) || !Number.isFinite(y)) return null;
  const text = format ? format(payload?.value) : String(payload?.value ?? '');
  const half = labelWidth(text, fontSize) / 2;
  let anchor = 'middle';
  if (x - half < minX) anchor = 'start';
  else if (x + half > maxX) anchor = 'end';
  return (
    <text
      x={x}
      y={y}
      dy={12}
      textAnchor={anchor}
      fill={CHART_THEME.axis}
      fontSize={fontSize}
      fontFamily={CHART_THEME.font}
    >
      {text}
    </text>
  );
}
