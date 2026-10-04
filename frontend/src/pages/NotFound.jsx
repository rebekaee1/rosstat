import { Link } from 'react-router-dom';
import Button from '../components/Button';
import IndicatorSearch from '../components/IndicatorSearch';
import useDocumentMeta from '../lib/useMeta';
import { WORLD_RATING_TO } from '../lib/navItems';
import { calendarPath, regionHubPath, todayPath } from '../lib/sitePaths';
import { useT } from '../i18n';

/**
 * Страница 404: объясняет, что произошло, даёт поиск и ссылки на главные разделы.
 * noindex, чтобы поисковики не накапливали несуществующие адреса.
 */
export default function NotFound() {
  const t = useT();
  useDocumentMeta({
    title: t('notFound.metaTitle'),
    description: t('notFound.metaDesc'),
    path: '/404',
    robots: 'noindex, follow',
  });

  const links = [
    { to: '/', labelKey: 'notFound.link.home' },
    { to: todayPath(), labelKey: 'notFound.link.today' },
    { to: regionHubPath(), labelKey: 'notFound.link.regions' },
    { to: WORLD_RATING_TO, labelKey: 'notFound.link.worldRating' },
    { to: '/compare', labelKey: 'notFound.link.compare' },
    { to: calendarPath(), labelKey: 'notFound.link.calendar' },
  ];

  return (
    <div className="fe-data-page mx-auto max-w-3xl px-4 pb-24 pt-28">
      <p className="mb-3 font-mono text-[11px] font-semibold uppercase tracking-[0.3em] text-champagne-ink">
        {t('notFound.eyebrow')}
      </p>
      <h1 className="mb-4 font-display text-3xl font-bold leading-tight text-text-primary md:text-4xl">
        {t('notFound.title')}
      </h1>
      <p className="mb-8 leading-relaxed text-text-secondary">
        {t('notFound.body')}
      </p>

      <div className="mb-8">
        <IndicatorSearch variant="inline" inlinePlaceholder={t('pgui.notFound.searchPlaceholder')} />
      </div>

      <ul className="mb-10 grid gap-2.5 sm:grid-cols-2">
        {links.map((item) => (
          <li key={item.to}>
            <Button as={Link} to={item.to} variant="secondary" className="w-full whitespace-normal">
              {t(item.labelKey)}
            </Button>
          </li>
        ))}
      </ul>

      <Button as={Link} to="/" variant="primary">
        {t('common.backHome')}
      </Button>
    </div>
  );
}
