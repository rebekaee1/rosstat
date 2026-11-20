import { useMemo } from 'react';
import { formatDate } from '../lib/format';
import { glueDate, periodPhrase } from '../lib/periodPhrase';
import { formatDeltaWithUnit } from '../lib/deltaText';
import { formatPercentChangeFine } from '../lib/indicatorSummary';
import { splitUnit } from '../lib/countryFlag';
import { useLocale, useT } from '../i18n';
import DeltaBadge from './DeltaBadge';
import Sparkline from './Sparkline';
import { SkeletonBox } from './Skeleton';
import WorldCountUp from './WorldCountUp';
import { sparkValues } from '../lib/sparkValues';
import '../styles/z4-indicator.css';
import '../styles/k5-pages.css';

/**
 * Главное число страницы показателя в правой части шапки: крупное значение (золотой акцент), изменение к прошлому
 * значению и мини-график за десять лет. Заменяет строку «США: 30,8 трлн $ за 2025 год» на компьютере; на телефоне
 * остаётся строка под названием (её рисует WorldHeroLine), а блок скрыт стилями.
 *
 * `summary` — результат buildIndicatorSummary; `points` — тот же ряд для мини-графика.
 * `liveChangePct` (круг 13, Биткоин) — изменение живой котировки к цене 24 часа назад, ровно то, что показывает лента курсов: когда оно
 * задано, шапка показывает его с подписью `deltaSuffix` вместо расчёта «к значению предыдущего дня» (две базы давали «0,0 %» против «+0,6 %»).
 */
export default function IndicatorHeroValue({
  summary,
  points,
  dateFormat,
  polarity = 'neutral',
  frequency,
  deltaSuffix = '',
  liveChangePct = null,
  loading = false,
}) {
  const t = useT();
  const { locale } = useLocale();
  const spark = useMemo(() => sparkValues(points), [points]);

  if (!summary) {
    if (!loading) return null;
    return (
      <div className="z4-hv z4-hv--loading" aria-hidden="true" data-testid="indicator-hero-value">
        <SkeletonBox className="z4-hv__skel-label" />
        <SkeletonBox className="z4-hv__skel-value" />
        <SkeletonBox className="z4-hv__skel-delta" />
      </div>
    );
  }

  const {
    kind, shown, last, prev, estimate, changeAbs, changePct, fmt,
  } = summary;
  const unitParts = splitUnit(shown.unit);
  // «198,0 индекс» читается как ошибка: слово «индекс» не единица, оно стоит тихой строкой под числом (круг 11, U15).
  const plainIndex = /^(индекс|index)$/i.test(unitParts.short);
  const dateText = (date) => glueDate(formatDate(date, dateFormat, locale));
  const label = estimate ? t('w6e.tile.estimate', { date: dateText(last.date) }) : t('w2.ind.now');
  const when = estimate ? '' : periodPhrase(t, last.date, dateFormat, locale);

  // Изменение к прошлому значению: у процентов в пунктах, у остальных в процентах; нулевое после округления: «без изменений».
  let delta = null;
  if (liveChangePct != null && Number.isFinite(Number(liveChangePct))) {
    const liveText = formatPercentChangeFine(liveChangePct, locale);
    delta = liveText == null ? (
      <p className="z4-hv__delta"><DeltaBadge delta={0}>{t('w6e.delta.flat')}</DeltaBadge></p>
    ) : (
      <p className="z4-hv__delta">
        <DeltaBadge delta={Number(liveChangePct)} polarity={polarity}>{liveText}</DeltaBadge>
        {deltaSuffix ? <span className="z4-hv__since">{deltaSuffix}</span> : null}
      </p>
    );
  } else if (summary.seasonal && frequency !== 'annual') {
    // Сезонный ряд (поездки, ночёвки, траты по месяцам и кварталам): одно сравнение, с тем же периодом прошлого года.
    // «К прошлому кварталу» давало «+38 %» там, где это лето, а не рост. Нет точки год назад: изменения не показываем.
    const yoy = summary.sameYear;
    if (yoy) {
      // Проценты (загрузка мест): разница в пунктах, а не процент от процента.
      const rate = kind === 'rate';
      const abs = rate
        ? formatDeltaWithUnit(last.value - yoy.from.value, unitParts.short.startsWith('%') ? '%' : unitParts.short, { digits: shown.digits, locale })
        : null;
      const pctText = rate ? null : formatPercentChangeFine(yoy.pct, locale);
      const flat = rate ? abs.flat : pctText == null;
      delta = flat ? (
        <p className="z4-hv__delta"><DeltaBadge delta={0}>{t('w6e.delta.flat')}</DeltaBadge></p>
      ) : (
        <p className="z4-hv__delta">
          <DeltaBadge delta={rate ? last.value - yoy.from.value : yoy.pct} polarity={polarity}>{rate ? abs.text : pctText}</DeltaBadge>
          <span className="z4-hv__since">{t('kt1_delta_sameYear')}</span>
        </p>
      );
    }
  } else if (prev) {
    const useAbs = kind === 'rate';
    const unitText = unitParts.short;
    const abs = useAbs
      ? formatDeltaWithUnit(changeAbs, unitText.startsWith('%') ? '%' : unitText, { digits: shown.digits, locale })
      : null;
    const pctText = useAbs ? null : formatPercentChangeFine(changePct, locale);
    const known = useAbs ? changeAbs != null : changePct != null;
    if (known) {
      const flat = useAbs ? abs.flat : pctText == null;
      const since = frequency === 'annual'
        ? t('w6e.delta.toYear', { date: formatDate(prev.date, 'annual', locale) })
        : deltaSuffix;
      delta = flat ? (
        <p className="z4-hv__delta"><DeltaBadge delta={0}>{t('w6e.delta.flat')}</DeltaBadge></p>
      ) : (
        <p className="z4-hv__delta">
          <DeltaBadge delta={useAbs ? changeAbs : changePct} polarity={polarity}>
            {useAbs ? abs.text : pctText}
          </DeltaBadge>
          {since ? <span className="z4-hv__since">{since}</span> : null}
        </p>
      );
    }
  }

  const trendUp = spark.length > 1 ? spark[spark.length - 1] >= spark[0] : true;

  return (
    <div className="z4-hv fe-glint" data-testid="indicator-hero-value">
      <p className="z4-hv__label">
        <span className="k5-signal" aria-hidden="true" />
        <span>{label}</span>
        {when ? <span className="z4-hv__when">{when}</span> : null}
      </p>
      <div className="z4-hv__row">
        <p
          className={String(shown.text || '').length > 8 ? 'z4-hv__value z4-hv__value--long' : 'z4-hv__value'}
          style={{ '--z4-hv-len': Math.max(4, String(shown.text || '').length) }}
        >
          <WorldCountUp value={last.value} format={fmt} className="z4-hv__num" />
          {/* Место переноса: длинная единица («руб. за 10 000») уходит под число, а не обрезается. */}
          {unitParts.short && !plainIndex ? <><wbr /><span className="z4-hv__unit">{unitParts.short}</span></> : null}
        </p>
        {spark.length > 1 ? (
          <div className="z4-hv__spark" aria-hidden="true">
            <Sparkline points={spark} trend={trendUp ? 'up' : 'down'} sentiment="neutral" height={54} />
          </div>
        ) : null}
      </div>
      {plainIndex ? <p className="z4-hv__basis">{unitParts.short}</p> : null}
      {delta}
    </div>
  );
}
