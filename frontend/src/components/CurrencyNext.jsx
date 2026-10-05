// «Что посмотреть дальше» на странице курса: соседние курсы, нефть и сравнение. Вместо тупика
// «Другие показатели», когда у курса нет прогноза.
import { Link } from 'react-router-dom';
import { ArrowRight, GitCompare } from 'lucide-react';
import { pairTitle } from '../lib/currencyRates';
import { comparePath, russiaIndicatorPath } from '../lib/sitePaths';
import { track, events } from '../lib/track';
import { useLocale, useT } from '../i18n';
import '../styles/w6-g.css';

const NEXT_CODES = ['eur-rub', 'cny-rub', 'usd-rub', 'brent'];

export default function CurrencyNext({ code }) {
  const t = useT();
  const { locale } = useLocale();
  const items = NEXT_CODES.filter((item) => item !== code).slice(0, 3);
  const compareWith = items.find((item) => item !== 'brent') || 'eur-rub';
  return (
    <section data-block="currency-next" className="fe-w6g-next" aria-label={t('w6g.cur.nextTitle')}>
      <h2 className="fe-w6g-next__title">{t('w6g.cur.nextTitle')}</h2>
      <div className="fe-w6g-next__grid">
        {items.map((item) => (
          <Link
            key={item}
            to={russiaIndicatorPath(item)}
            className="fe-panel fe-press fe-w6g-next__card"
            onClick={() => track(events.RELATED_LINK_CLICK, { from: code, to: item, surface: 'currency-next' })}
          >
            <span>{item === 'brent' ? t('w6g.cur.brent') : pairTitle(item, locale, item)}</span>
            <ArrowRight size={16} aria-hidden="true" />
          </Link>
        ))}
        <Link
          to={`${comparePath()}?codes=${encodeURIComponent([code, compareWith].join(','))}`}
          className="fe-panel fe-press fe-w6g-next__card"
          onClick={() => track(events.RELATED_LINK_CLICK, { from: code, to: 'compare', surface: 'currency-next' })}
        >
          <span className="fe-w6g-next__icon"><GitCompare size={16} aria-hidden="true" /> {t('w6g.cur.compare')}</span>
          <ArrowRight size={16} aria-hidden="true" />
        </Link>
      </div>
    </section>
  );
}
