import { Link } from 'react-router-dom';
import { BarChart3, Calculator, CalendarDays, Globe2, Map as MapIcon, Scale } from 'lucide-react';
import Button from '../components/Button';
import IndicatorSearch from '../components/IndicatorSearch';
import useDocumentMeta from '../lib/useMeta';
import { WORLD_RATING_TO } from '../lib/navItems';
import { calendarPath, regionHubPath, todayPath } from '../lib/sitePaths';
import { useT } from '../i18n';
import '../styles/w5-pages.css';

/** Маленькая планета с орбитой: «здесь пока ничего нет». Только SVG, без картинок. */
function LostPlanet() {
  return (
    <svg className="w5-planet" viewBox="0 0 120 120" aria-hidden="true" focusable="false">
      <defs>
        <radialGradient id="w5PlanetFill" cx="35%" cy="30%" r="75%">
          <stop offset="0%" stopColor="#ffffff" />
          <stop offset="60%" stopColor="#E6EAF0" />
          <stop offset="100%" stopColor="#CAD2DE" />
        </radialGradient>
      </defs>
      <circle cx="60" cy="60" r="34" fill="url(#w5PlanetFill)" stroke="rgba(32,42,60,0.16)" />
      <ellipse cx="60" cy="60" rx="34" ry="12" fill="none" stroke="rgba(32,42,60,0.12)" />
      <ellipse cx="60" cy="60" rx="13" ry="34" fill="none" stroke="rgba(32,42,60,0.12)" />
      <path d="M44 48c6-6 14-4 18 1s-2 9-9 9-12-2-9-10Z" fill="rgba(173,138,72,0.28)" />
      <path d="M66 70c5-3 11-1 11 4s-6 7-11 5-3-7 0-9Z" fill="rgba(173,138,72,0.22)" />
      <g className="w5-planet__orbit">
        <ellipse cx="60" cy="60" rx="52" ry="17" fill="none" stroke="#AD8A48" strokeOpacity="0.55" strokeWidth="1.5" strokeDasharray="3 5" transform="rotate(-18 60 60)" />
        <circle cx="105" cy="45" r="4.5" fill="#AD8A48" />
      </g>
    </svg>
  );
}

const SECTIONS = [
  { to: WORLD_RATING_TO, icon: Globe2, titleKey: 'notFound.link.worldRating', hintKey: 'w5.nf.hint.rating' },
  { to: '/compare', icon: Scale, titleKey: 'w5.nf.compare', hintKey: 'w5.nf.hint.compare' },
  { to: regionHubPath(), icon: MapIcon, titleKey: 'w5.nf.regions', hintKey: 'w5.nf.hint.regions' },
  { to: todayPath(), icon: BarChart3, titleKey: 'w5.nf.today', hintKey: 'w5.nf.hint.today' },
  { to: calendarPath(), icon: CalendarDays, titleKey: 'w5.nf.calendar', hintKey: 'w5.nf.hint.calendar' },
  { to: '/calculator', icon: Calculator, titleKey: 'w5.nf.calculators', hintKey: 'w5.nf.hint.calculators' },
];

/**
 * Страница 404 внутри общей оболочки сайта (шапка и подвал рисует App): дружелюбный заголовок,
 * маленькая планета, поиск и шесть популярных разделов. noindex — адреса-призраки не копим.
 */
export default function NotFound() {
  const t = useT();
  useDocumentMeta({
    title: t('notFound.metaTitle'),
    description: t('notFound.metaDesc'),
    path: '/404',
    robots: 'noindex, follow',
  });

  return (
    <div className="fe-data-page mx-auto max-w-3xl px-4 pb-24 pt-28">
      <div className="w5-nf-hero fe-reveal">
        <LostPlanet />
        <p className="w5-eyebrow">{t('notFound.eyebrow')}</p>
        <h1 className="font-display text-3xl font-bold leading-tight text-text-primary md:text-4xl">
          {t('w5.nf.title')}
        </h1>
        <p className="max-w-md leading-relaxed text-text-secondary">{t('w5.nf.body')}</p>
      </div>

      <div className="fe-reveal mx-auto mb-10 max-w-xl" style={{ '--fe-delay': '0.08s' }}>
        <IndicatorSearch variant="inline" inlinePlaceholder={t('pgui.notFound.searchPlaceholder')} />
      </div>

      <h2 className="mb-3 text-base font-semibold text-text-primary">{t('w5.nf.popular')}</h2>
      <ul className="w5-nf-grid">
        {SECTIONS.map(({ to, icon: Icon, titleKey, hintKey }, index) => (
          <li key={to} className="fe-reveal" style={{ '--fe-delay': `${Math.min(0.12 + index * 0.03, 0.2).toFixed(2)}s` }}>
            <Link to={to} className="w5-nf-card fe-press">
              <Icon className="w5-nf-card__icon" aria-hidden="true" />
              <span className="w5-nf-card__title">{t(titleKey)}</span>
              <span className="w5-nf-card__hint">{t(hintKey)}</span>
            </Link>
          </li>
        ))}
      </ul>

      <div className="mt-10 flex justify-center">
        <Button as={Link} to="/" variant="primary">
          {t('common.backHome')}
        </Button>
      </div>
    </div>
  );
}
