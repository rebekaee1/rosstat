import useDocumentMeta from '../lib/useMeta';
import { getPageSeo } from '../lib/pageMeta';
import { useLocale, useT } from '../i18n';
import { track, trackOutbound, events } from '../lib/track';

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
    <div className="max-w-3xl mx-auto px-4 md:px-8 pt-24 md:pt-28 pb-20 md:pb-24">
      <article className="prose prose-sm max-w-none">
        <p className="text-[10px] uppercase tracking-[0.3em] text-champagne font-semibold mb-4">
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
          <a href="https://rosstat.gov.ru" className="text-champagne hover:underline" target="_blank" rel="noopener noreferrer" onClick={() => trackOutbound('https://rosstat.gov.ru')}>{t('footer.rosstat')}</a>,
          {' '}
          <a href="https://cbr.ru" className="text-champagne hover:underline" target="_blank" rel="noopener noreferrer" onClick={() => trackOutbound('https://cbr.ru')}>{t('footer.cbr')}</a>,
          {' '}
          <a href="https://minfin.gov.ru" className="text-champagne hover:underline" target="_blank" rel="noopener noreferrer" onClick={() => trackOutbound('https://minfin.gov.ru')}>{t('footer.minfin')}</a>
          {' '}
          {locale === 'en' ? 'and' : 'и'}
          {' '}
          <a href="https://ec.europa.eu/eurostat" className="text-champagne hover:underline" target="_blank" rel="noopener noreferrer" onClick={() => trackOutbound('https://ec.europa.eu/eurostat')}>{t('footer.eurostat')}</a>
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
          <a href="mailto:rebeka.ee@yandex.ru" className="text-champagne hover:underline" onClick={() => track(events.CONTACT_EMAIL)}>
            rebeka.ee@yandex.ru
          </a>
          .
        </p>
      </article>
    </div>
  );
}
