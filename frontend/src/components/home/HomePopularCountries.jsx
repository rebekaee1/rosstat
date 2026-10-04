import { useMemo } from 'react';
import { Link } from 'react-router-dom';
import { ArrowDown } from 'lucide-react';
import { countryFlag, POPULAR_COUNTRY_SLUGS } from '../../lib/countryFlag';
import { countryPublicName } from '../../lib/homeWorkbench';
import { countryPath, russiaHomePath } from '../../lib/sitePaths';
import { useWorldCountries } from '../../lib/worldApi';
import { track, events } from '../../lib/track';
import { useLocale, useT } from '../../i18n';
import { SkeletonBox } from '../Skeleton';
import '../../styles/shell.css';

/**
 * Ряд «Популярные страны» под поиском: флаг и название, одно касание до страны.
 * Нужен, чтобы каталог стран был рядом с началом страницы, а не после планеты.
 * Только страны, которые реально есть в каталоге; пока ответ не пришёл — каркас той же высоты.
 */
export default function HomePopularCountries() {
  const t = useT();
  const { locale } = useLocale();
  const { data, isLoading } = useWorldCountries();

  const popular = useMemo(() => {
    const bySlug = new Map((data?.countries || []).map((country) => [country.slug, country]));
    const order = POPULAR_COUNTRY_SLUGS[locale === 'en' ? 'en' : 'ru'];
    return order.map((slug) => bySlug.get(slug)).filter(Boolean);
  }, [data, locale]);

  if (!isLoading && popular.length < 3) return null;

  return (
    <nav
      data-block="home-popular-countries"
      className="fe-popular fe-reveal"
      style={{ '--fe-delay': '0.12s' }}
      aria-label={t('homehero.popular.title')}
    >
      <p className="fe-popular__title">{t('homehero.popular.title')}</p>
      <ul className="fe-popular__row fe-fade-x scrollbar-hide">
        {isLoading && popular.length === 0
          ? [0, 1, 2, 3, 4].map((i) => (
            <li key={i} aria-hidden="true"><SkeletonBox className="h-11 w-28 rounded-xl" /></li>
          ))
          : popular.map((country) => {
            const flag = countryFlag(country.code);
            const name = countryPublicName(country, locale);
            return (
              <li key={country.slug}>
                <Link
                  to={country.slug === 'russia' ? russiaHomePath() : countryPath(country.slug)}
                  onClick={() => track(events.HOME_COUNTRIES_CTA, { target: 'popular-country', code: country.code })}
                  className="fe-popular__chip fe-press"
                >
                  {flag ? <span className="fe-popular__flag" aria-hidden="true">{flag}</span> : null}
                  {name}
                </Link>
              </li>
            );
          })}
        <li>
          <Link
            to="/#countries"
            onClick={() => track(events.HOME_COUNTRIES_CTA, { target: 'popular-all' })}
            className="fe-popular__chip fe-popular__chip--all fe-press"
          >
            {t('homehero.popular.all')}
            <ArrowDown size={14} aria-hidden="true" />
          </Link>
        </li>
      </ul>
    </nav>
  );
}
