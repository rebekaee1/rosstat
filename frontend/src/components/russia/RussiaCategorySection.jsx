// Раздел России: компактные строки по 44 px, сначала пять главных, остальное по кнопке «Показать ещё».
import { useState } from 'react';
import { Link } from 'react-router-dom';
import { ChevronDown } from 'lucide-react';
import {
  russiaIndicatorChange,
  russiaIndicatorDisplay,
  RUSSIA_CATEGORY_PREVIEW,
} from '../../lib/russiaHomeCards';
import { resolveDateFormat } from '../../lib/format';
import { indicatorPolarity } from '../../lib/deltaTone';
import { formatDeltaWithUnit } from '../../lib/deltaText';
import { periodPhrase } from '../../lib/periodPhrase';
import { describeChange, indicatorsCountText } from '../../lib/countryKeyFigures';
import { russiaIndicatorPath } from '../../lib/sitePaths';
import { useLocale, useT } from '../../i18n';
import DeltaBadge from '../DeltaBadge';
import { FreqBadges } from '../country/CountryIndicatorRow';
import '../../styles/z5-country.css';

function formatNumber(value, locale) {
  return value.toLocaleString(locale === 'en' ? 'en-US' : 'ru-RU', {
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  });
}

function changeUnit(unit) {
  const text = String(unit || '').trim();
  if (/^%/.test(text)) return '%';
  if (/^(индекс|index)/i.test(text)) return 'индекс';
  return text.length <= 14 ? text : '';
}

/** Строка показателя: название, значение с единицей, изменение, период. Смысл изменения словами — в подсказке. */
export function RussiaIndicatorRow({ indicator }) {
  const t = useT();
  const { locale } = useLocale();
  const display = russiaIndicatorDisplay(indicator);
  const changeNum = russiaIndicatorChange(indicator);
  const title = locale === 'en' && indicator.name_en ? indicator.name_en : indicator.name;
  const polarity = indicatorPolarity(indicator.name, indicator.name_en, indicator.code);
  const delta = changeNum != null ? formatDeltaWithUnit(changeNum, display?.unit, { locale }) : null;
  const meaning = changeNum != null
    ? describeChange({
      change: changeNum, unit: changeUnit(display?.unit), frequency: indicator.frequency, locale, t,
    })
    : '';
  const date = periodPhrase(t, indicator.current_date, resolveDateFormat({ frequency: indicator.frequency }), locale) || '';
  // Стрелка без основания непонятна: рядом словами «к прошлому месяцу / кварталу / году» (круг 11, U18).
  const vsKey = ['weekly', 'monthly', 'quarterly', 'annual'].includes(indicator.frequency)
    ? `c11f.ru.vs.${indicator.frequency}`
    : 'c11f.ru.vs.default';
  return (
    <Link to={russiaIndicatorPath(indicator.code)} className="z5-ru-row fe-press group">
      <span className="z5-ru-row__title">{title}</span>
      <span className="z5-ru-row__value">
        <b>{display ? formatNumber(display.value, locale) : '—'}</b>
        {display?.unit ? <small>{display.unit}</small> : null}
      </span>
      <span className="z5-ru-row__delta" title={meaning || undefined}>
        {delta && !delta.flat ? <span className="z5-ru-row__vs">{t(vsKey)}</span> : null}
        {delta && (delta.flat
          ? <DeltaBadge delta={0}>{t('w3.tele.noChange')}</DeltaBadge>
          : <DeltaBadge delta={changeNum} polarity={polarity}>{delta.text}</DeltaBadge>)}
      </span>
      <span className="z5-ru-row__date">
        <FreqBadges item={indicator} t={t} />
        {date}
      </span>
    </Link>
  );
}

export default function RussiaCategorySection({ group, label, expandAll = false }) {
  const t = useT();
  const { locale } = useLocale();
  const [open, setOpen] = useState(false);
  const total = group.indicators.length;
  const showAll = open || expandAll || total <= RUSSIA_CATEGORY_PREVIEW + 1;
  const rows = showAll ? group.indicators : group.indicators.slice(0, RUSSIA_CATEGORY_PREVIEW);
  const hidden = total - rows.length;
  return (
    <section id={`cat-${group.category.slug}`} className="z5-section scroll-mt-24" data-testid="russia-section">
      <div className="mb-3 flex items-end justify-between gap-3 sm:mb-4 sm:gap-4">
        <div className="min-w-0">
          <h2 className="z5-section-title font-display font-bold text-text-primary">{label}</h2>
        </div>
        <span className="z5-section-count">{indicatorsCountText(group.count, locale, t)}</span>
      </div>
      <div className="z5-ru-rows">
        {rows.map((ind) => <RussiaIndicatorRow key={ind.code} indicator={ind} />)}
      </div>
      {total > RUSSIA_CATEGORY_PREVIEW + 1 && (
        <button
          type="button"
          className="z5-more-btn fe-press"
          aria-expanded={showAll}
          onClick={() => setOpen((value) => !value)}
        >
          {hidden > 0 ? t('z5.ru.showMore', { n: hidden }) : t('z5.ru.showLess')}
          <ChevronDown size={15} aria-hidden="true" className={showAll ? 'z5-more-btn__chev z5-more-btn__chev--up' : 'z5-more-btn__chev'} />
        </button>
      )}
    </section>
  );
}
