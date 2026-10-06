import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  Database, Calculator, TrendingUp, Globe2, Ban, ShieldAlert, LineChart,
} from 'lucide-react';
import useDocumentMeta from '../lib/useMeta';
import { getPageSeo } from '../lib/pageMeta';
import { russiaCategoryPath, worldRatingPath, WORLD_RATING_DEFAULT_CONCEPT } from '../lib/sitePaths';
import { useLocale, useT } from '../i18n';
import Breadcrumbs from '../components/Breadcrumbs';
import Button from '../components/Button';
import { InfoCard, InfoGrid, InfoMore } from '../components/InfoCard';
import { toolTrail } from '../lib/breadcrumbs';
import { cn } from '../lib/format';
import '../styles/w5-pages.css';
import '../styles/k8-tools.css';
import '../styles/z8-tools.css';

const STEPS = [1, 2, 3, 4];
const SOURCES = ['rosstat', 'cbr', 'minfin', 'imf', 'eurostat', 'us'];
const TOC = [
  ['principles', 'x4.meth.data.title'],
  ['steps', 'x4.meth.how.title'],
  ['read', 'x4.meth.forecast.title'],
  ['countries', 'x4.meth.world.title'],
  ['skip', 'x4.meth.skip.title'],
  ['limits', 'x4.meth.limits.title'],
];

/** Какой раздел сейчас на экране: подсвечивается в оглавлении справа. Без IntersectionObserver остаётся первый. */
function useActiveSection(ids) {
  const [active, setActive] = useState(ids[0]);
  useEffect(() => {
    if (typeof IntersectionObserver === 'undefined') return undefined;
    const seen = new Map();
    const observer = new IntersectionObserver((entries) => {
      entries.forEach((entry) => seen.set(entry.target.id, entry.isIntersecting ? entry.boundingClientRect.top : null));
      const visible = [...seen.entries()].filter(([, top]) => top != null).sort((a, b) => a[1] - b[1]);
      if (visible.length) setActive(visible[0][0]);
    }, { rootMargin: '-110px 0px -55% 0px' });
    ids.forEach((id) => {
      const node = document.getElementById(id);
      if (node) observer.observe(node);
    });
    return () => observer.disconnect();
  }, [ids]);
  return active;
}

/**
 * «Методология»: короткий лид и шесть карточек. На виду — человеческие объяснения в 1–2
 * предложениях; статистические детали (модели, окна обучения, проверка) — под «Подробнее».
 */
export default function Methodology() {
  const { locale } = useLocale();
  const t = useT();
  const active = useActiveSection(TOC.map(([id]) => id));
  const seo = getPageSeo('methodology', locale);
  useDocumentMeta({
    title: seo.title,
    description: seo.description,
    path: seo.path,
  });

  const more = t('w5.meth.more');
  const skipItems = [
    ['meth.skip.1title', 'meth.skip.1body'],
    ['meth.skip.2title', 'meth.skip.2body'],
    ['meth.skip.3title', 'meth.skip.3body'],
  ];

  return (
    <div className="fe-data-page fe-gutter fe-z8-meth pt-24 md:pt-28 pb-12 md:pb-16">
      <Breadcrumbs items={toolTrail(seo.h1, seo.path)} className="mb-6" />

      <header className="fe-z8-meth__head fe-reveal">
        <div>
          <h1 className="fe-z8-meth__title">{seo.h1}</h1>
          <p className="x4-lead" style={{ marginBottom: 0 }}>{t('x4.meth.lead')}</p>
        </div>
        <div className="fe-z8-meth__cta">
          <Button as={Link} to="/">
            <LineChart className="h-4 w-4" aria-hidden="true" />
            {t('meth.cta.indicators')}
          </Button>
          <Button as={Link} to="/about" variant="secondary">
            {t('meth.cta.about')}
          </Button>
        </div>
      </header>

      <div className="fe-z8-meth__layout">
      <div className="fe-z8-meth__main">
      <InfoGrid className="fe-z8-meth__cards">
        <InfoCard icon={Database} title={t('x4.meth.data.title')} id="principles" wide>
          <p>{t('x4.meth.data.body')}</p>
          <ul className="fe-z8-sources" aria-label={t('z8.meth.sourcesAria')}>
            {SOURCES.map((id) => (
              <li key={id} className="fe-z8-source">
                <span className="fe-z8-source__badge" aria-hidden="true">{t(`z8.meth.src.${id}.badge`)}</span>
                <span className="fe-z8-source__text">
                  <strong>{t(`z8.meth.src.${id}.name`)}</strong>
                  <span>{t(`z8.meth.src.${id}.desc`)}</span>
                </span>
              </li>
            ))}
          </ul>
          <InfoMore label={more}>
            <p>{t('meth.p.officialBody')}</p>
            <p>{t('meth.p.reproBody')}</p>
            <p>{t('meth.step.1body')}</p>
          </InfoMore>
        </InfoCard>

        <InfoCard icon={Calculator} title={t('x4.meth.how.title')} id="steps" wide>
          <ol className="x4-mini-steps">
            {STEPS.map((n) => (
              <li key={n}>
                <strong>{t(`x4.meth.step.${n}.title`)}</strong>
                {t(`w5.meth.step.${n}sum`)}
              </li>
            ))}
          </ol>
          <InfoMore label={more}>
            {STEPS.map((n) => (
              <div key={n}>
                <p><strong className="text-text-primary">{t(`meth.step.${n}title`)}.</strong></p>
                <p>{t(`meth.step.${n}body`)}</p>
              </div>
            ))}
            <InfoMore label={t('z2.meth.expertLabel')}>
              <p>{t('z2.meth.expertBody')}</p>
            </InfoMore>
          </InfoMore>
        </InfoCard>

        <InfoCard icon={TrendingUp} title={t('x4.meth.forecast.title')} id="read">
          <p>{t('x4.meth.forecast.body')}</p>
          <InfoMore label={more}>
            <p>{t('meth.read.p1')}</p>
            <p>{t('meth.read.p2')}</p>
            <p>{t('meth.update.modelBody')}</p>
            <p>{t('meth.update.derivedBody')}</p>
          </InfoMore>
        </InfoCard>

        <InfoCard icon={Globe2} title={t('x4.meth.world.title')} id="countries">
          <p>{t('x4.meth.world.body')}</p>
          <InfoMore label={more}>
            <p>{t('meth.world.p1')}</p>
            <p>{t('meth.world.p2')}</p>
            <p>{t('meth.world.p3')}</p>
            <p>{t('meth.worldRank.p1')}</p>
            <p>{t('meth.worldRank.p2')}</p>
            <p>
              <Link
                to={locale === 'en'
                  ? worldRatingPath(WORLD_RATING_DEFAULT_CONCEPT)
                  : russiaCategoryPath('gdp')}
              >
                {t('meth.worldRank.link')}
              </Link>
            </p>
          </InfoMore>
        </InfoCard>

        <InfoCard icon={Ban} title={t('x4.meth.skip.title')} id="skip">
          <p>{t('x4.meth.skip.body')}</p>
          <InfoMore label={more}>
            <p>{t('meth.skipIntro')}</p>
            {skipItems.map(([titleKey, bodyKey]) => (
              <p key={titleKey}>
                <strong className="text-text-primary">{t(titleKey)}.</strong>
                {' '}
                {t(bodyKey)}
              </p>
            ))}
            <p>{t('meth.skipOutro')}</p>
          </InfoMore>
        </InfoCard>

        <InfoCard icon={ShieldAlert} title={t('x4.meth.limits.title')} id="limits">
          <p>{t('x4.meth.limits.body')}</p>
          <InfoMore label={more}>
            <p>{t('meth.disclaimer.p1')}</p>
            <p>{t('meth.disclaimer.p2')}</p>
            <p>{t('meth.p.limitsBody')}</p>
          </InfoMore>
        </InfoCard>
      </InfoGrid>
      </div>

      <nav className="fe-z8-meth__toc" aria-label={t('z8.meth.tocAria')}>
        <p className="fe-z8-meth__toc-title">{t('z8.meth.toc')}</p>
        <ol>
          {TOC.map(([id, key]) => (
            <li key={id}>
              <a href={`#${id}`} className={cn(active === id && 'is-active')} aria-current={active === id ? 'location' : undefined}>
                {t(key)}
              </a>
            </li>
          ))}
        </ol>
      </nav>
      </div>
    </div>
  );
}
