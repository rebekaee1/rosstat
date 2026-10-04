import SourceLink from '../components/SourceLink';
import SectionNav from '../components/SectionNav';
import useDocumentMeta from '../lib/useMeta';
import { getPageSeo } from '../lib/pageMeta';
import { useLocale, useT } from '../i18n';
import { track, events } from '../lib/track';
import { footerSourceLinks } from '../lib/footerNav';
import Breadcrumbs from '../components/Breadcrumbs';
import { toolTrail } from '../lib/breadcrumbs';
import '../styles/w5-pages.css';

/** «О проекте»: короткие секции с якорями вместо одной стены текста. Тексты прежние, структура новая. */
export default function About() {
  const { locale } = useLocale();
  const t = useT();
  const seo = getPageSeo('about', locale);
  useDocumentMeta({
    title: seo.title,
    description: seo.description,
    path: seo.path,
  });

  const nav = [
    { id: 'what', label: t('w5.about.nav.what') },
    { id: 'audience', label: t('w5.about.nav.audience') },
    { id: 'different', label: t('about.diffTitle') },
    { id: 'trust', label: t('w5.about.nav.trust') },
    { id: 'credits', label: t('about.creditsTitle') },
  ];
  const sources = footerSourceLinks(locale);
  const andWord = locale === 'en' ? 'and' : 'и';

  return (
    <div className="fe-data-page max-w-3xl mx-auto px-4 md:px-8 pt-24 md:pt-28 pb-20 md:pb-24">
      <Breadcrumbs items={toolTrail(seo.h1, seo.path)} className="mb-6" />

      <header className="mb-6 fe-reveal">
        <p className="w5-eyebrow mb-3">{t('about.eyebrow')}</p>
        <h1 className="mb-4 font-display text-3xl font-bold leading-tight text-text-primary md:text-4xl">
          {seo.h1}
        </h1>
        <p className="w5-lead" style={{ marginBottom: 0 }}>{t('about.intro.p1')}</p>
      </header>

      <SectionNav items={nav} />

      <section id="what" className="w5-section fe-panel">
        <h2 className="w5-section__title">{t('w5.about.what.title')}</h2>
        <p>
          {t('about.intro.p2before')}
          {' '}
          {sources.map((item, i) => {
            const link = (
              <SourceLink key={item.key} href={item.href} className="text-champagne-ink hover:underline">
                {t(item.key)}
              </SourceLink>
            );
            if (i === 0) return link;
            if (i === sources.length - 1) return <span key={item.key}> {andWord} {link}</span>;
            return <span key={item.key}>, {link}</span>;
          })}
          {' '}
          {t('about.intro.p2after')}
          {' '}
          <strong className="text-text-primary">{t('about.intro.forecast')}</strong>
          {' '}
          {t('about.intro.p2end')}
        </p>
      </section>

      <section id="audience" className="w5-section fe-panel">
        <h2 className="w5-section__title">{t('about.audienceTitle')}</h2>
        <ul className="w5-ticks">
          <li>{t('about.audience.1')}</li>
          <li>{t('about.audience.2')}</li>
          <li>{t('about.audience.3')}</li>
          <li>{t('about.audience.4')}</li>
          <li>
            <span>
              {t('about.audience.5before')}
              {' '}
              <strong className="text-text-primary">{t('about.audience.5strong')}</strong>
              {t('about.audience.5after')}
            </span>
          </li>
        </ul>
      </section>

      <section id="different" className="w5-section fe-panel">
        <h2 className="w5-section__title">{t('about.diffTitle')}</h2>
        <div className="w5-duo">
          <div className="w5-duo__item">
            <strong>{t('about.diff.1strong')}</strong>
            <span>{t('about.diff.1')}</span>
          </div>
          <div className="w5-duo__item">
            <strong>{t('about.diff.2strong')}</strong>
            <span>{t('about.diff.2')}</span>
          </div>
        </div>
      </section>

      <section id="trust" className="w5-section fe-panel">
        <h2 className="w5-section__title">{t('about.trustTitle')}</h2>
        <p>
          {t('about.trust.1before')}
          {' '}
          <strong className="text-text-primary">{t('about.trust.1strong')}</strong>
          {' '}
          {t('about.trust.1after')}
        </p>
        <p>
          {t('about.trust.2')}
          {' '}
          <a href="mailto:rebeka.ee@yandex.ru" onClick={() => track(events.CONTACT_EMAIL)}>
            rebeka.ee@yandex.ru
          </a>
          .
        </p>
      </section>

      <section id="credits" className="w5-section fe-panel">
        <h2 className="w5-section__title">{t('about.creditsTitle')}</h2>
        <p>
          {t('w5.about.credits.before')}
          {' '}
          <a href="https://www.solarsystemscope.com/textures/" target="_blank" rel="noopener noreferrer">Solar System Scope</a>
          {', '}
          <a href="https://creativecommons.org/licenses/by/4.0/" target="_blank" rel="noopener noreferrer">CC BY 4.0</a>
          .
        </p>
      </section>
    </div>
  );
}
