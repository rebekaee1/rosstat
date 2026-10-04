import { Link } from 'react-router-dom';
import { ArrowRight } from 'lucide-react';
import { formatValue, resolveDateFormat, cn, isCpiIndex } from '../lib/format';
import { FOCUS_RING_SURFACE } from '../lib/uiTokens';
import { track, events } from '../lib/track';
import { russiaIndicatorPath } from '../lib/sitePaths';
import { useLocale, useT } from '../i18n';
import { findCategoryByApiLabel } from '../lib/categories';
import { indicatorPolarity } from '../lib/deltaTone';
import { formatDeltaWithUnit } from '../lib/deltaText';
import { periodPhrase } from '../lib/periodPhrase';
import DeltaBadge from './DeltaBadge';
import '../styles/indicator-russia.css';

/**
 * Listing-карточка индикатора. Используется и на главной (где это
 * `home_indicator_click`), и на /russia/category/:slug (где это `category_tile_click`).
 * `surface` различает источник клика — нужен для funnel-анализа в Метрике
 * (Webvisor показывает category→indicator как отдельную ось, без surface
 * мы потеряем контекст).
 *
 * Для человека: название, число с единицей, изменение со смыслом и подписью периода («+0,24 руб. за день»),
 * дата словами. На странице категории подпись категории не повторяется на каждой плитке.
 */
export default function IndicatorTile({ indicator, delay = 0, displayOverride, surface = 'home' }) {
  const t = useT();
  const { locale } = useLocale();

  // Hero override от бэка: для индекс-индикаторов (ИПП, ИЦП, цены на жильё)
  // «первая цифра» карточки = изменение г/г %, а не уровень индекса. Так число
  // на карточке каталога совпадает с тем, что пользователь видит при первом
  // входе на страницу (там по умолчанию режим «год к году»).
  const hasHero = !displayOverride && indicator.hero_value != null;
  // Для индекс-карточек (hero = Г/г %) бейдж изменения = ускорение Г/г в п.п.
  // (hero_change), а не дельта уровня индекса.
  const rawChange = displayOverride ? displayOverride.change
    : hasHero ? indicator.hero_change
      : indicator.change;
  const changeNum = rawChange != null ? Number(rawChange) : null;
  const isActive = indicator.is_active;
  const displayVal = displayOverride
    ? displayOverride.value
    : hasHero
      ? indicator.hero_value
      : isCpiIndex(indicator.code)
        ? (indicator.current_value != null ? Number(indicator.current_value) - 100 : null)
        : indicator.current_value;
  const displayUnit = hasHero || displayOverride ? (indicator.hero_unit || '%') : indicator.unit;
  const dateFmt = resolveDateFormat({ frequency: indicator.frequency });
  const polarity = indicatorPolarity(indicator.name, indicator.name_en, indicator.code);
  const title = locale === 'en' && indicator.name_en ? indicator.name_en : indicator.name;
  const categoryName = (locale === 'en'
    ? findCategoryByApiLabel(indicator.category_ru || indicator.category)?.nameEn
    : null) || indicator.category || t('tile.metric');

  const change = changeNum != null && Number.isFinite(changeNum)
    ? formatDeltaWithUnit(changeNum, displayUnit, { locale })
    : null;
  const periodKey = hasHero ? 'year' : indicator.frequency;
  const perText = ['daily', 'weekly', 'monthly', 'quarterly', 'annual', 'year'].includes(periodKey)
    ? t(`w3.tile.per.${periodKey}`)
    : t('w3.tele.delta.prevValue');
  const date = periodPhrase(t, indicator.current_date, dateFmt, locale);

  const handleClick = () => {
    if (!isActive) return;
    const event = surface === 'category' ? events.CATEGORY_TILE_CLICK : events.HOME_INDICATOR_CLICK;
    track(event, {
      indicator: indicator.code,
      indicatorCategory: indicator.category,
      surface,
    });
  };

  return (
    <Link
      style={isActive ? { '--i': Math.min(delay, 5), '--fe-duration': '0.4s', '--fe-rise': '12px' } : undefined}
      to={isActive ? russiaIndicatorPath(indicator.code) : '#'}
      onClick={handleClick}
      aria-disabled={isActive ? undefined : true}
      className={cn(
        FOCUS_RING_SURFACE,
        'fe-tile group',
        isActive
          ? 'fe-reveal fe-reveal--free fe-reveal--stagger fe-press'
          : 'fe-tile--pending',
      )}
    >
      <div className="fe-tile__top">
        <div className="min-w-0">
          {surface !== 'category' && <p className="fe-tile__cat">{categoryName}</p>}
          <h3 className="fe-tile__title">{title}</h3>
        </div>
        {isActive ? (
          <span className="fe-tile__go" aria-hidden="true"><ArrowRight className="h-3.5 w-3.5" /></span>
        ) : (
          <span className="fe-tile__soon">{t('tile.pending')}</span>
        )}
      </div>

      <div className="fe-tile__body">
        <p className="fe-tile__value">
          <span className={String(formatValue(displayVal)).length > 12 ? 'fe-tile__num fe-tile__num--long' : 'fe-tile__num'}>
            {formatValue(displayVal)}
          </span>
          {displayUnit ? <span className="fe-tile__unit">{displayUnit}</span> : null}
        </p>

        <div className="fe-tile__foot">
          {change && (
            change.flat ? (
              <DeltaBadge delta={0}>{t('w3.tele.noChange')}</DeltaBadge>
            ) : (
              <span className="fe-tile__delta">
                <DeltaBadge delta={changeNum} polarity={polarity}>{change.text}</DeltaBadge>
                <span className="fe-tile__vs">{perText}</span>
              </span>
            )
          )}
          {date && <span className="fe-tile__date">{date}</span>}
        </div>
      </div>
    </Link>
  );
}
