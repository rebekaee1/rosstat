// Боковая навигация страны: главные темы с золотой точкой, остальные в «Ещё темы», ниже «Прогноз ВВП» и «Похожие страны».
import { Link } from 'react-router-dom';
import { ChevronDown, TrendingUp } from 'lucide-react';
import Chip from '../Chip';
import CountryFlag from '../CountryFlag';
import {
  compactCount, indicatorsCountText, isMainTopic, topicDisplayName,
} from '../../lib/countryKeyFigures';
import { countryPath, indicatorPath } from '../../lib/sitePaths';
import { countryPublicName } from '../../lib/homeWorkbench';
import { useT } from '../../i18n';
import '../../styles/z5-country.css';

/** Столько тем видно сразу; если тем немного больше, лишний «Ещё» не нужен. */
const VISIBLE_TOPICS = 6;

function TopicChip({ cat, active, onPick, locale, t, compact = false }) {
  const count = cat.indicators.length;
  const exact = indicatorsCountText(count, locale, t);
  return (
    <Chip
      active={active}
      onClick={() => onPick(cat.name)}
      aria-current={active ? 'true' : undefined}
      className={compact ? 'z5-topic z5-topic--chip' : 'z5-topic w-full justify-between! gap-4 px-3.5 py-2.5 text-left text-sm!'}
    >
      <span className="z5-topic__name">
        {isMainTopic(cat) ? <i className="z5-dot" aria-hidden="true" /> : null}
        <span className="min-w-0 truncate">{topicDisplayName(cat, locale)}</span>
      </span>
      <span className="z5-topic__count" title={exact}>{compactCount(count, locale)}</span>
    </Chip>
  );
}

export function SimilarCountries({ countries, locale, className = '' }) {
  const t = useT();
  if (!countries?.length) return null;
  return (
    <section className={`z5-similar ${className}`} aria-label={t('z5.similar.title')}>
      <h3 className="z5-aside-title">{t('z5.similar.title')}</h3>
      <div className="z5-similar__chips">
        {countries.map((country) => (
          <Link key={country.slug} to={countryPath(country.slug)} className="z5-similar__chip fe-press">
            <CountryFlag code={country.code} />
            <span>{countryPublicName(country, locale)}</span>
          </Link>
        ))}
      </div>
    </section>
  );
}

export function GdpForecastCard({ slug, item }) {
  const t = useT();
  if (!item?.indicator_code) return null;
  return (
    <Link to={indicatorPath(slug, item.indicator_code)} className="z5-forecast fe-press">
      <span className="z5-forecast__icon" aria-hidden="true"><TrendingUp size={18} /></span>
      <span className="z5-forecast__text">
        <strong>{t('z5.forecast.title')}</strong>
        <small>{t('z5.forecast.body')}</small>
      </span>
    </Link>
  );
}

export default function CountryTopicNav({
  categories, active, onPick, locale, children,
}) {
  const t = useT();
  const split = categories.length > VISIBLE_TOPICS + 1;
  const main = split ? categories.slice(0, VISIBLE_TOPICS) : categories;
  const rest = split ? categories.slice(VISIBLE_TOPICS) : [];
  const activeInRest = rest.some((cat) => cat.name === active);
  return (
    <aside className="z5-topics hidden min-w-0 lg:sticky lg:top-24 lg:block lg:max-h-[calc(100vh-7rem)] lg:self-start lg:overflow-y-auto">
      <h3 className="z5-aside-title">{t('world.country.themes')}</h3>
      <div className="z5-topics__list">
        {main.map((cat) => (
          <TopicChip key={cat.name} cat={cat} active={active === cat.name} onPick={onPick} locale={locale} t={t} />
        ))}
      </div>
      {rest.length > 0 && (
        <details className="z5-more" open={activeInRest || undefined}>
          <summary className="z5-more__summary">
            <span>{t('z5.topics.more')}</span>
            <ChevronDown size={15} aria-hidden="true" className="z5-more__chevron" />
          </summary>
          <div className="z5-more__chips">
            {rest.map((cat) => (
              <TopicChip key={cat.name} cat={cat} active={active === cat.name} onPick={onPick} locale={locale} t={t} compact />
            ))}
          </div>
        </details>
      )}
      {children}
    </aside>
  );
}
