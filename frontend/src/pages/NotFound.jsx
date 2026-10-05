import { Link, useLocation, useNavigate } from 'react-router-dom';
import { ArrowLeft, BarChart3, Calculator, CalendarDays, Coins, Flag, Globe2, Home, Landmark, Map as MapIcon, Scale } from 'lucide-react';
import Button from '../components/Button';
import IndicatorSearch from '../components/IndicatorSearch';
import useDocumentMeta from '../lib/useMeta';
import { WORLD_RATING_TO } from '../lib/navItems';
import { suggestForPath } from '../lib/notFoundSuggest';
import { calendarPath, countryPath, regionHubPath, russiaHomePath, todayPath } from '../lib/sitePaths';
import { useLocale, useT } from '../i18n';
import '../styles/w5-pages.css';
import '../styles/w6f-pages.css';
import '../styles/z2-shell.css';

/**
 * Планета в роли нуля в «404»: вращающаяся поверхность с золотыми материками, мягкая тень сферы и кольцо-орбита
 * с точкой. Только SVG и CSS-анимация, без картинок; при prefers-reduced-motion стоит на месте.
 */
function LostPlanet() {
  // Один «тайл» материков шириной 130: три копии подряд, сдвиг на 130 даёт бесшовный круг вращения.
  const continents = (
    <>
      <path d="M14 78c10-16 32-18 44-6s6 26-8 32-30 4-38-8-4-12 2-18Z" />
      <path d="M72 120c14-8 30-2 34 12s-4 28-20 30-24-10-22-24 2-14 8-18Z" />
      <path d="M26 156c9-5 20 0 22 9s-6 18-15 18-14-9-11-16 0-9 4-11Z" />
      <path d="M92 60c9-9 24-7 28 3s-2 17-13 19-20-7-15-22Z" />
      <path d="M4 124c6-5 15-3 17 4s-4 13-13 13-8-11-4-17Z" />
    </>
  );
  return (
    <svg className="z2-nf-planet" viewBox="0 0 240 240" aria-hidden="true" focusable="false">
      <defs>
        <radialGradient id="z2NfOcean" cx="34%" cy="28%" r="80%">
          <stop offset="0%" stopColor="#ffffff" />
          <stop offset="55%" stopColor="#e8edf4" />
          <stop offset="100%" stopColor="#c3cddc" />
        </radialGradient>
        <radialGradient id="z2NfShade" cx="32%" cy="26%" r="85%">
          <stop offset="55%" stopColor="rgba(32,42,60,0)" />
          <stop offset="100%" stopColor="rgba(32,42,60,0.26)" />
        </radialGradient>
        <linearGradient id="z2NfGold" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="#e3c880" />
          <stop offset="100%" stopColor="#a67f38" />
        </linearGradient>
        <clipPath id="z2NfClip"><circle cx="120" cy="120" r="84" /></clipPath>
      </defs>
      <ellipse cx="120" cy="214" rx="64" ry="9" fill="rgba(32,42,60,0.12)" />
      <circle cx="120" cy="120" r="84" fill="url(#z2NfOcean)" />
      <g clipPath="url(#z2NfClip)">
        <g className="z2-nf-surface" fill="url(#z2NfGold)" fillOpacity="0.62" stroke="rgba(128,100,47,0.5)" strokeWidth="1">
          <g>{continents}</g>
          <g transform="translate(130 0)">{continents}</g>
          <g transform="translate(260 0)">{continents}</g>
          <g transform="translate(390 0)">{continents}</g>
        </g>
        <ellipse cx="120" cy="120" rx="84" ry="28" fill="none" stroke="rgba(32,42,60,0.1)" />
        <ellipse cx="120" cy="120" rx="30" ry="84" fill="none" stroke="rgba(32,42,60,0.1)" />
        <circle cx="120" cy="120" r="84" fill="url(#z2NfShade)" />
        <ellipse cx="92" cy="78" rx="34" ry="18" fill="rgba(255,255,255,0.4)" transform="rotate(-28 92 78)" />
      </g>
      <circle cx="120" cy="120" r="84" fill="none" stroke="rgba(32,42,60,0.18)" />
      <g className="z2-nf-orbit">
        <ellipse cx="120" cy="120" rx="112" ry="34" fill="none" stroke="#ad8a48" strokeOpacity="0.55" strokeWidth="1.6" strokeDasharray="3 6" transform="rotate(-18 120 120)" />
        <circle cx="226" cy="85" r="7" fill="#ad8a48" />
        <circle cx="226" cy="85" r="12" fill="#ad8a48" fillOpacity="0.18" />
      </g>
    </svg>
  );
}

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
 * Страница 404 внутри общей оболочки сайта (шапка и подвал рисует App): крупная золотая «404» с планетой вместо нуля,
 * поиск, золотая «На главную», подсказка по словам из адреса и популярные разделы. noindex: адреса-призраки не копим.
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
        <div className="z2-nf-code" aria-hidden="true">
          <span className="z2-nf-digit">4</span>
          <LostPlanet />
          <span className="z2-nf-digit">4</span>
        </div>
        <p className="w5-eyebrow">{t('notFound.eyebrow')}</p>
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
