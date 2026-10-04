import { Link } from 'react-router-dom';
import { ArrowRight, GitCompare } from 'lucide-react';
import { relatedIndicatorCardCopy } from '../lib/indicatorVariants';
import { russiaIndicatorDisplay } from '../lib/russiaHomeCards';
import { formatDate, formatValueWithUnit, resolveDateFormat } from '../lib/format';
import { russiaIndicatorPath } from '../lib/sitePaths';
import { track, events } from '../lib/track';
import { useLocale, useT } from '../i18n';
import '../styles/indicator-russia.css';

/**
 * «Похожие индикаторы»: у каждой карточки понятное название, которое не повторяется («Ставки по кредитам
 * юрлицам, до 1 года», а не «До 1 года» трижды), и текущее значение с единицей и датой.
 */
export default function RelatedIndicators({ code, category, items }) {
  const t = useT();
  const { locale } = useLocale();
  if (!items?.length) return null;

  return (
    <section data-block="related" className="fe-related">
      <div className="fe-related__head">
        <h2 className="fe-related__title">{t('indicator.related')}</h2>
        <Link
          to={`/compare?a=${code}`}
          onClick={() => track(events.RELATED_LINK_CLICK, { from: code, to: 'compare', surface: 'indicator-cta' })}
          className="fe-related__compare fe-press"
        >
          <GitCompare className="h-4 w-4" aria-hidden="true" />
          {t('common.compare')}
        </Link>
      </div>
      <div className="fe-related__grid">
        {items.map((rel) => {
          const card = relatedIndicatorCardCopy(rel.code, rel.name, rel.unit);
          const display = russiaIndicatorDisplay(rel);
          const date = rel.current_date
            ? formatDate(rel.current_date, resolveDateFormat({ frequency: rel.frequency }), locale)
            : null;
          return (
            <Link
              key={rel.code}
              to={russiaIndicatorPath(rel.code)}
              onClick={() => track(events.RELATED_INDICATOR_CLICK, {
                from: code,
                to: rel.code,
                indicatorCategory: category,
                surface: 'indicator-related',
              })}
              className="fe-rel-card fe-press group"
            >
              <div className="min-w-0 flex-1">
                <p className="fe-rel-card__title">{card.title}</p>
                {card.subtitle && card.subtitle !== '%' && (
                  <p className="fe-rel-card__sub">{card.subtitle}</p>
                )}
                {display && (
                  <p className="fe-rel-card__value">
                    <span className="fe-rel-card__num">{formatValueWithUnit(display.value, display.unit)}</span>
                    {date && date !== '—' ? <span className="fe-rel-card__date">{date}</span> : null}
                  </p>
                )}
              </div>
              <ArrowRight className="fe-rel-card__arrow" aria-hidden="true" />
            </Link>
          );
        })}
      </div>
    </section>
  );
}
