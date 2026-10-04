import { formatValue, unitSuffix, unitDigits } from '../lib/format';
import { formatDeltaWithUnit } from '../lib/deltaText';
import { useLocale, useT } from '../i18n';
import DeltaBadge from './DeltaBadge';
import '../styles/indicator-russia.css';

/**
 * Карточка одного значения на странице индикатора: подпись, число с единицей, изменение, дата.
 *
 * `change` — абсолютное изменение (в единицах показателя), `pctChange` — изменение в процентах (для индексов);
 * `polarity` — смысл роста ('up-good' | 'up-bad' | 'neutral', см. lib/deltaTone.js): цвет изменения зависит от него,
 * а не от знака. Изменение, равное нулю при показанной точности, выводится как «без изменений».
 *
 * Число всегда сразу точное; рамка мягко появляется средствами CSS (`.fe-reveal`, задержка ≤ 200 мс,
 * начальное состояние задаёт CSS). При `prefers-reduced-motion` анимации нет.
 */
export default function TelemetryCard({
  label, value, unit, change, pctChange, meta, delay = 0,
  deltaSuffix,
  valueDigits,
  polarity = 'neutral',
}) {
  const t = useT();
  const { locale } = useLocale();
  const resolvedDelta = deltaSuffix ?? t('w3.tele.delta.prevMonth');
  const digits = valueDigits ?? unitDigits(unit);
  const hasChange = change != null && Number.isFinite(Number(change));
  const shown = hasChange
    ? (pctChange != null
      ? formatDeltaWithUnit(pctChange, unit, { pct: true, locale })
      : formatDeltaWithUnit(change, unit, { digits, locale }))
    : null;
  const valueText = String(formatValue(value, digits));

  return (
    <div
      style={{ '--i': Math.min(delay, 5), '--fe-delay': 'calc(var(--i) * 40ms)', '--fe-duration': '0.4s', '--fe-rise': '12px' }}
      className="fe-reveal fe-reveal--free fe-tele"
    >
      <p className="fe-tele__label">{label}</p>

      <p className="fe-tele__value">
        <span className={valueText.length > 12 ? 'fe-tele__num fe-tele__num--long' : 'fe-tele__num'}>
          {valueText}
        </span>
        {unitSuffix(unit) ? <span className="fe-tele__unit">{unitSuffix(unit)}</span> : null}
      </p>

      {(shown || meta) && (
        <div className="fe-tele__foot">
          {shown && (
            shown.flat ? (
              <p className="fe-tele__delta">
                <DeltaBadge delta={0}>{t('w3.tele.noChange')}</DeltaBadge>
              </p>
            ) : (
              <p className="fe-tele__delta">
                <DeltaBadge delta={pctChange ?? change} polarity={polarity}>{shown.text}</DeltaBadge>
                <span className="fe-tele__vs">{resolvedDelta}</span>
              </p>
            )
          )}
          {meta ? <p className="fe-tele__meta">{meta}</p> : null}
        </div>
      )}
    </div>
  );
}
