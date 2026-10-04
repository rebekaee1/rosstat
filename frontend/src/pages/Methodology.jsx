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
import '../styles/w5-pages.css';

const STEPS = [1, 2, 3, 4];

/**
 * «Методология»: короткий лид и шесть карточек. На виду — человеческие объяснения в 1–2
 * предложениях; статистические детали (модели, окна обучения, проверка) — под «Подробнее».
 */
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
  const skipItems = [
    ['meth.skip.1title', 'meth.skip.1body'],
    ['meth.skip.2title', 'meth.skip.2body'],
    ['meth.skip.3title', 'meth.skip.3body'],
  ];

  return (
    <div className="fe-data-page max-w-3xl mx-auto px-4 md:px-8 pt-24 md:pt-28 pb-12 md:pb-16">
      <Breadcrumbs items={toolTrail(seo.h1, seo.path)} className="mb-6" />

      <header className="mb-8 fe-reveal">
        <h1 className="mb-4 font-display text-3xl font-bold leading-[1.1] text-text-primary md:text-5xl">
          {seo.h1}
        </h1>
        <p className="x4-lead" style={{ marginBottom: 0 }}>{t('x4.meth.lead')}</p>
      </header>

      <InfoGrid>
        <InfoCard icon={Database} title={t('x4.meth.data.title')} id="principles">
          <p>{t('x4.meth.data.body')}</p>
          <InfoMore label={more}>
            <p>{t('meth.p.officialBody')}</p>
            <p>{t('meth.p.reproBody')}</p>
            <p>{t('meth.step.1body')}</p>
          </InfoMore>
        </InfoCard>

        <InfoCard icon={Calculator} title={t('x4.meth.how.title')} id="steps">
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
          </InfoMore>
        </InfoCard>

        <InfoCard icon={TrendingUp} title={t('x4.meth.forecast.title')} id="read">
          <p>{t('x4.meth.forecast.body')}</p>
          <InfoMore label={more}>
            <p>{t('meth.read.p1')}</p>
            <p>{t('meth.read.p2')}</p>
            <p>{t('meth.update.modelBody')}</p>
            <p>{t('meth.update.derivedBody')}</p>
            <p>{t('meth.p.uncertBody')}</p>
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
