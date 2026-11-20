import { formatDate } from '../lib/format';
import { formatDeltaWithUnit } from '../lib/deltaText';
import { formatPercentChangeFine } from '../lib/indicatorSummary';
import { splitUnit } from '../lib/countryFlag';
import { useLocale, useT } from '../i18n';
import DeltaBadge from './DeltaBadge';
import '../styles/r6b-pulse.css';

/**
 * R6-B. Полоса под названием на телефоне: изменение (на компьютере его показывает блок справа, на телефоне блок скрыт
 * и число стояло без изменения). Прогноз тут не показывается.
 * Круг наблюдателей 20.11.2026 (№15, пункт 2 «что убрать»): липкая плашка с числом при прокрутке и чипы соседних рядов убраны.
 */
export default function R6bPulseStrip({
  summary, polarity = 'neutral', deltaSuffix = '', dateFormat,
}) {
  const t = useT();
  const { locale } = useLocale();
  let delta = null;
  if (summary?.seasonal) {
    // Сезонный ряд: то же одно сравнение, что в шапке на компьютере (с тем же периодом прошлого года).
    const yoy = summary.sameYear;
    const pctText = yoy ? formatPercentChangeFine(yoy.pct, locale) : null;
    if (yoy) {
      delta = pctText == null ? (
        <p className="r6b-pulse__delta" data-testid="r6b-delta">
          <DeltaBadge delta={0}>{t('w6e.delta.flat')}</DeltaBadge>
        </p>
      ) : (
        <p className="r6b-pulse__delta" data-testid="r6b-delta">
          <DeltaBadge delta={yoy.pct} polarity={polarity}>{pctText}</DeltaBadge>
          <span className="r6b-pulse__since">{t('kt1_delta_sameYear')}</span>
        </p>
      );
    }
  } else if (summary?.prev) {
    const { kind, shown, changeAbs, changePct, prev } = summary;
    const useAbs = kind === 'rate';
    const unitText = splitUnit(shown.unit).short;
    const abs = useAbs
      ? formatDeltaWithUnit(changeAbs, unitText.startsWith('%') ? '%' : unitText, { digits: shown.digits, locale })
      : null;
    const pctText = useAbs ? null : formatPercentChangeFine(changePct, locale);
    const known = useAbs ? changeAbs != null : changePct != null;
    if (known) {
      const flat = useAbs ? abs.flat : pctText == null;
      delta = flat ? (
        <p className="r6b-pulse__delta" data-testid="r6b-delta">
          <DeltaBadge delta={0}>{t('w6e.delta.flat')}</DeltaBadge>
          <span className="r6b-pulse__since">{t('r6b.flatSince', { date: formatDate(prev.date, dateFormat, locale) })}</span>
        </p>
      ) : (
        <p className="r6b-pulse__delta" data-testid="r6b-delta">
          <DeltaBadge delta={useAbs ? changeAbs : changePct} polarity={polarity}>
            {useAbs ? abs.text : pctText}
          </DeltaBadge>
          {deltaSuffix ? <span className="r6b-pulse__since">{deltaSuffix}</span> : null}
        </p>
      );
    }
  }
  if (!delta) return null;
  return <div className="r6b-pulse">{delta}</div>;
}
