import { Link } from 'react-router-dom';
import {
  Database, LineChart, GitBranch, ShieldCheck, RefreshCw, AlertTriangle,
  Sigma, Ban, Eye, Globe2,
} from 'lucide-react';
import useDocumentMeta from '../lib/useMeta';
import { getPageSeo } from '../lib/pageMeta';
import { russiaCategoryPath, worldRatingPath, WORLD_RATING_DEFAULT_CONCEPT } from '../lib/sitePaths';
import { useLocale, useT } from '../i18n';
import Breadcrumbs from '../components/Breadcrumbs';
import SectionNav from '../components/SectionNav';
import Button from '../components/Button';
import { toolTrail } from '../lib/breadcrumbs';
import '../styles/w5-pages.css';

/** Короткое изложение шага + «Подробнее» для тех, кому нужна статистическая деталь. */
function Step({ n, title, summary, children, moreLabel }) {
  return (
    <li className="w5-step">
      <span className="w5-step__n" aria-hidden="true">{n}</span>
      <div>
        <h3 className="w5-step__title">{title}</h3>
        <p className="w5-step__sum">{summary}</p>
        <details className="w5-more-inline">
          <summary>{moreLabel}</summary>
          <div><p>{children}</p></div>
        </details>
      </div>
    </li>
  );
}

function More({ label, children }) {
  return (
    <details className="w5-more-inline">
      <summary>{label}</summary>
      <div>{children}</div>
    </details>
  );
}

export default function Methodology() {
  const { locale } = useLocale();
  const t = useT();
  const seo = getPageSeo('methodology', locale);
  useDocumentMeta({
    title: seo.title,
    description: seo.description,
    path: seo.path,
  });

  const more = t('w5.meth.more');
  const nav = [
    { id: 'principles', label: t('meth.principlesTitle') },
    { id: 'steps', label: t('w5.meth.nav.steps') },
    { id: 'countries', label: t('w5.meth.nav.countries') },
    { id: 'rating', label: t('w5.meth.nav.rating') },
    { id: 'update', label: t('w5.meth.nav.update') },
    { id: 'skip', label: t('meth.skipTitle') },
    { id: 'read', label: t('w5.meth.nav.read') },
    { id: 'limits', label: t('meth.disclaimerTitle') },
  ];
  const principles = [
    [Database, 'meth.p.officialTitle', 'meth.p.officialBody'],
    [Sigma, 'meth.p.reproTitle', 'meth.p.reproBody'],
    [ShieldCheck, 'meth.p.uncertTitle', 'meth.p.uncertBody'],
    [Ban, 'meth.p.limitsTitle', 'meth.p.limitsBody'],
  ];
  const skipItems = [
    ['meth.skip.1title', 'meth.skip.1body'],
    ['meth.skip.2title', 'meth.skip.2body'],
    ['meth.skip.3title', 'meth.skip.3body'],
  ];

  return (
    <div className="fe-data-page max-w-3xl mx-auto px-4 md:px-8 pt-24 md:pt-28 pb-20 md:pb-24">
      <Breadcrumbs items={toolTrail(seo.h1, seo.path)} className="mb-6" />

      <header className="mb-6 fe-reveal">
        <p className="w5-eyebrow mb-3">{t('meth.eyebrow')}</p>
        <h1 className="mb-4 font-display text-3xl font-bold leading-[1.1] text-text-primary md:text-5xl">
          {seo.h1}
        </h1>
        <p className="w5-lead" style={{ marginBottom: 0 }}>{t('meth.intro.p1')}</p>
        <More label={t('w5.meth.moreApproach')}>
          <p>{t('meth.intro.p2')}</p>
          <p>{t('meth.intro.p3')}</p>
        </More>
      </header>

      <SectionNav items={nav} />

      <section id="principles" className="w5-section fe-panel">
        <h2 className="w5-section__title">{t('meth.principlesTitle')}</h2>
        <div className="w5-duo">
          {principles.map(([Icon, titleKey, bodyKey]) => (
            <div key={titleKey} className="w5-duo__item">
              <Icon className="mb-2 h-5 w-5 text-champagne-ink" aria-hidden="true" />
              <strong>{t(titleKey)}</strong>
              <span>{t(bodyKey)}</span>
            </div>
          ))}
        </div>
      </section>

      <section id="steps" className="w5-section fe-panel">
        <h2 className="w5-section__title">{t('meth.stepsTitle')}</h2>
        <p>{t('w5.meth.stepsLead')}</p>
        <ol className="w5-steps mt-4">
          <Step n="1" title={t('meth.step.1title')} summary={t('w5.meth.step.1sum')} moreLabel={more}>{t('meth.step.1body')}</Step>
          <Step n="2" title={t('meth.step.2title')} summary={t('w5.meth.step.2sum')} moreLabel={more}>{t('meth.step.2body')}</Step>
          <Step n="3" title={t('meth.step.3title')} summary={t('w5.meth.step.3sum')} moreLabel={more}>{t('meth.step.3body')}</Step>
          <Step n="4" title={t('meth.step.4title')} summary={t('w5.meth.step.4sum')} moreLabel={more}>{t('meth.step.4body')}</Step>
        </ol>
      </section>

      <section id="countries" className="w5-section fe-panel">
        <h2 className="w5-section__title">{t('meth.worldTitle')}</h2>
        <p>{t('meth.world.p1')}</p>
        <More label={more}>
          <p>{t('meth.world.p2')}</p>
          <p>{t('meth.world.p3')}</p>
        </More>
      </section>

      <section id="rating" className="w5-section fe-panel">
        <h2 className="w5-section__title">{t('meth.worldRankTitle')}</h2>
        <p>
          <Globe2 className="mr-2 inline h-5 w-5 align-text-bottom text-champagne-ink" aria-hidden="true" />
          {t('meth.worldRank.p1')}
        </p>
        <More label={more}>
          <p>{t('meth.worldRank.p2')}</p>
        </More>
        <p className="mt-3">
          <Link
            to={locale === 'en'
              ? worldRatingPath(WORLD_RATING_DEFAULT_CONCEPT)
              : russiaCategoryPath('gdp')}
          >
            {t('meth.worldRank.link')}
          </Link>
        </p>
      </section>

      <section id="update" className="w5-section fe-panel">
        <h2 className="w5-section__title">{t('meth.updateTitle')}</h2>
        <div className="w5-duo">
          <div className="w5-duo__item">
            <RefreshCw className="mb-2 h-5 w-5 text-champagne-ink" aria-hidden="true" />
            <strong>{t('meth.update.modelTitle')}</strong>
            <span>{t('meth.update.modelBody')}</span>
          </div>
          <div className="w5-duo__item">
            <GitBranch className="mb-2 h-5 w-5 text-champagne-ink" aria-hidden="true" />
            <strong>{t('meth.update.derivedTitle')}</strong>
            <span>{t('meth.update.derivedBody')}</span>
          </div>
        </div>
      </section>

      <section id="skip" className="w5-section fe-panel">
        <h2 className="w5-section__title">{t('meth.skipTitle')}</h2>
        <p>{t('meth.skipIntro')}</p>
        <ul className="mt-4 grid gap-3">
          {skipItems.map(([titleKey, bodyKey]) => (
            <li key={titleKey} className="w5-note">
              <Ban className="mt-0.5 h-5 w-5 shrink-0 text-text-secondary" aria-hidden="true" />
              <span>
                <strong className="text-text-primary">{t(titleKey)}.</strong> {t(bodyKey)}
              </span>
            </li>
          ))}
        </ul>
        <p className="mt-4 text-sm">{t('meth.skipOutro')}</p>
      </section>

      <section id="read" className="w5-section fe-panel">
        <h2 className="w5-section__title">{t('meth.readTitle')}</h2>
        <div className="w5-note">
          <Eye className="mt-0.5 h-5 w-5 shrink-0 text-champagne-ink" aria-hidden="true" />
          <div className="space-y-2">
            <p style={{ margin: 0 }}>{t('meth.read.p1')}</p>
            <p style={{ margin: 0 }}>{t('meth.read.p2')}</p>
          </div>
        </div>
      </section>

      <section id="limits" className="w5-section fe-panel">
        <h2 className="w5-section__title">{t('meth.disclaimerTitle')}</h2>
        <div className="w5-note">
          <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-champagne-ink" aria-hidden="true" />
          <div className="space-y-2">
            <p style={{ margin: 0 }}>{t('meth.disclaimer.p1')}</p>
            <p style={{ margin: 0 }}>{t('meth.disclaimer.p2')}</p>
          </div>
        </div>
      </section>

      <div className="flex flex-wrap gap-3">
        <Button as={Link} to="/">
          <LineChart className="h-4 w-4" aria-hidden="true" />
          {t('meth.cta.indicators')}
        </Button>
        <Button as={Link} to="/about" variant="secondary">
          {t('meth.cta.about')}
        </Button>
      </div>
    </div>
  );
}
