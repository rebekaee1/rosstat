import { Link, useLocation, useNavigate } from 'react-router-dom';
import { ArrowLeft, BarChart3, Calculator, CalendarDays, Coins, Flag, Globe2, Home, Landmark, Map as MapIcon, Scale } from 'lucide-react';
import Button from '../components/Button';
import IndicatorSearch from '../components/IndicatorSearch';
import FacetMark from '../components/brand/FacetMark';
import LightSeam from '../components/brand/LightSeam';
import useDocumentMeta from '../lib/useMeta';
import { WORLD_RATING_TO } from '../lib/navItems';
import { suggestForPath } from '../lib/notFoundSuggest';
import { calendarPath, countryPath, regionHubPath, russiaHomePath, todayPath } from '../lib/sitePaths';
import { useLocale, useT } from '../i18n';
import '../styles/w5-pages.css';
import '../styles/w6f-pages.css';
import '../styles/z2-shell.css';
import '../styles/k2-brand.css';

/** Популярные разделы чипами (то же меню, что на сервере: страны и рейтинг первыми, у англоязычных ещё США). */
function popularSections(locale) {
  const items = [
    { to: WORLD_RATING_TO, icon: Globe2, titleKey: 'notFound.link.worldRating' },
    { to: '/compare', icon: Scale, titleKey: 'w5.nf.compare' },
    { to: '/currencies', icon: Coins, titleKey: 'shell3.nav.currencies' },
    { to: '/calculator', icon: Calculator, titleKey: 'w5.nf.calculators' },
    { to: todayPath(), icon: BarChart3, titleKey: 'w5.nf.today' },
    { to: regionHubPath(), icon: MapIcon, titleKey: 'w5.nf.regions' },
    { to: calendarPath(), icon: CalendarDays, titleKey: 'w5.nf.calendar' },
  ];
  if (locale === 'en') {
    items.splice(1, 0, { to: countryPath('united-states'), icon: Flag, titleKey: 'nav.unitedStates' });
  } else {
    items.splice(1, 0, { to: russiaHomePath(), icon: Landmark, titleKey: 'nav.russia' });
  }
  return items;
}

/**
 * Страница 404 внутри общей оболочки сайта (шапка и подвал рисует App): светлая сцена, золотые «4» из толстого стекла,
 * хрустальный глобус с осколками между ними (картинка, качается, вокруг кружит искра), поиск, золотая «На главную»,
 * подсказка по словам из адреса и популярные разделы. noindex: адреса-призраки не копим.
 */
export default function NotFound() {
  const t = useT();
  const { locale } = useLocale();
  const { pathname } = useLocation();
  const navigate = useNavigate();
  const guesses = suggestForPath(pathname);
  const sections = popularSections(locale);
  const goBack = () => {
    if (window.history.length > 1) navigate(-1);
    else navigate('/');
  };
  useDocumentMeta({
    title: t('notFound.metaTitle'),
    description: t('notFound.metaDesc'),
    path: '/404',
    robots: 'noindex, follow',
  });

  return (
    <div className="fe-data-page z2-nf mx-auto px-4 pb-24 pt-28">
      <div className="z2-nf-hero fe-reveal">
        <div className="z2-nf-code fe-nf-code" aria-hidden="true">
          <span className="z2-nf-digit fe-nf-digit" data-d="4">4</span>
          <span className="fe-nf-globe">
            <span className="fe-nf-caustic" />
            <img
              className="fe-nf-globe__img"
              src="/brand/404-shards.webp"
              width="1200"
              height="1200"
              alt=""
              decoding="async"
              draggable="false"
            />
            <span className="fe-nf-spark" />
          </span>
          <span className="z2-nf-digit fe-nf-digit" data-d="4">4</span>
        </div>
        <p className="w5-eyebrow fe-eyebrow-facet">
          <FacetMark size={10} />
          {t('notFound.eyebrow')}
        </p>
        <h1 className="z2-nf-title">{t('w5.nf.title')}</h1>
        <p className="z2-nf-body">{t('w5.nf.body')}</p>
      </div>

      <div className="fe-reveal mx-auto max-w-xl" style={{ '--fe-delay': '0.08s' }}>
        <IndicatorSearch variant="inline" inlinePlaceholder={t('pgui.notFound.searchPlaceholder')} />
      </div>

      <div className="z2-nf-actions fe-reveal" style={{ '--fe-delay': '0.14s' }}>
        <Button as={Link} to="/" variant="primary" className="z2-nf-home">
          <Home className="h-4 w-4" aria-hidden="true" />
          {t('common.backHome')}
        </Button>
        <Button type="button" variant="secondary" onClick={goBack}>
          <ArrowLeft className="h-4 w-4" aria-hidden="true" />
          {t('w6f.nf.back')}
        </Button>
      </div>

      {guesses.length > 0 && (
        <div className="fe-reveal mb-8" data-nf-guess style={{ '--fe-delay': '0.2s' }}>
          <p className="z2-nf-section-title">{t('w6f.nf.guess')}</p>
          <LightSeam variant="arrow" className="mb-3" />
          <ul className="w6f-nf-chips">
            {guesses.map((g) => (
              <li key={g.to}>
                <Link to={g.to} className="w6f-nf-chip w6f-nf-chip--strong fe-press">{t(g.labelKey)}</Link>
              </li>
            ))}
          </ul>
        </div>
      )}

      <h2 className="z2-nf-section-title">{t('w5.nf.popular')}</h2>
      <LightSeam variant="arrow" className="mb-3" />
      <ul className="w6f-nf-chips">
        {sections.map(({ to, icon: Icon, titleKey }) => (
          <li key={to}>
            <Link to={to} className="w6f-nf-chip fe-press">
              <Icon className="h-4 w-4 shrink-0 text-champagne-ink" aria-hidden="true" />
              {t(titleKey)}
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}
