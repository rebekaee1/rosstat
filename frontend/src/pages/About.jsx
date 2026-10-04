import SourceLink from '../components/SourceLink';
import useDocumentMeta from '../lib/useMeta';
import { getPageSeo } from '../lib/pageMeta';
import { useLocale, useT } from '../i18n';
import { track, events } from '../lib/track';
import { footerSourceLinks } from '../lib/footerNav';
import Breadcrumbs from '../components/Breadcrumbs';
import { toolTrail } from '../lib/breadcrumbs';

export default function About() {
  const { locale } = useLocale();
  const t = useT();
  const seo = getPageSeo('about', locale);
  useDocumentMeta({
    title: seo.title,
    description: seo.description,
    path: seo.path,
  });

  return (
    <div className="fe-data-page max-w-3xl mx-auto px-4 md:px-8 pt-24 md:pt-28 pb-20 md:pb-24">
      <Breadcrumbs items={toolTrail(seo.h1, seo.path)} className="mb-6" />
      <article className="fe-panel fe-reading prose prose-sm max-w-none p-5 sm:p-8">
        <p className="text-[11px] uppercase tracking-[0.3em] text-champagne-ink font-semibold mb-4">
          {t('about.eyebrow')}
        </p>
        <h1 className="font-display text-3xl md:text-4xl font-bold text-text-primary mb-6 leading-tight">
          {seo.h1}
        </h1>
        <p className="text-text-secondary leading-relaxed mb-4">
          {t('about.intro.p1')}
        </p>
        <p className="text-text-secondary leading-relaxed mb-6">
          {t('about.intro.p2before')}
          {' '}
          {footerSourceLinks(locale).map((item, i, items) => {
            const link = (
              <SourceLink
                key={item.key}
                href={item.href}
                className="text-champagne-ink hover:underline"
              >
                {t(item.key)}
              </SourceLink>
            );
            const andWord = locale === 'en' ? 'and' : 'и';
            if (i === 0) return link;
            if (i === items.length - 1) {
              return <span key={item.key}> {andWord} {link}</span>;
            }
            return <span key={item.key}>, {link}</span>;
          })}
          {' '}
          {t('about.intro.p2after')}
          {' '}
          <strong className="text-text-primary">{t('about.intro.forecast')}</strong>
          {' '}
          {t('about.intro.p2end')}
        </p>

        <h2 className="text-xl font-semibold text-text-primary mt-10 mb-3">{t('about.audienceTitle')}</h2>
        <ul className="list-disc pl-5 text-text-secondary space-y-2 mb-6">
          <li>{t('about.audience.1')}</li>
          <li>{t('about.audience.2')}</li>
          <li>{t('about.audience.3')}</li>
          <li>{t('about.audience.4')}</li>
          <li>
            {t('about.audience.5before')}
            {' '}
            <strong className="text-text-primary">{t('about.audience.5strong')}</strong>
            {t('about.audience.5after')}
          </li>
        </ul>

        <h2 className="text-xl font-semibold text-text-primary mt-10 mb-3">{t('about.diffTitle')}</h2>
        <ul className="list-disc pl-5 text-text-secondary space-y-2 mb-6">
          <li>
            <strong className="text-text-primary">{t('about.diff.1strong')}</strong>
            {' '}
            {t('about.diff.1')}
          </li>
          <li>
            <strong className="text-text-primary">{t('about.diff.2strong')}</strong>
            {' '}
            {t('about.diff.2')}
          </li>
        </ul>

        <h2 className="text-xl font-semibold text-text-primary mt-10 mb-3">{t('about.trustTitle')}</h2>
        <p className="text-text-secondary leading-relaxed mb-4">
          {t('about.trust.1before')}
          {' '}
          <strong className="text-text-primary">{t('about.trust.1strong')}</strong>
          {' '}
          {t('about.trust.1after')}
        </p>
        <p className="text-text-secondary leading-relaxed">
          {t('about.trust.2')}
          {' '}
          <a href="mailto:rebeka.ee@yandex.ru" className="text-champagne-ink hover:underline" onClick={() => track(events.CONTACT_EMAIL)}>
            rebeka.ee@yandex.ru
          </a>
          .
        </p>

        <h2 id="credits" className="mt-10 mb-3 scroll-mt-28 text-xl font-semibold text-text-primary">{t('about.creditsTitle')}</h2>
        <p className="text-sm leading-relaxed text-text-secondary">
          {t('about.creditsBody')}
          {' '}
          <a href="https://www.solarsystemscope.com/textures/" target="_blank" rel="noopener noreferrer" className="text-champagne-ink hover:underline">Solar System Scope</a>
          {', '}
          <a href="https://creativecommons.org/licenses/by/4.0/" target="_blank" rel="noopener noreferrer" className="text-champagne-ink hover:underline">CC BY 4.0</a>
          {'. '}
          {t('about.creditsChanges')}
        </p>
      </article>
    </div>
  );
}
