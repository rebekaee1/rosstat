import { Link } from 'react-router-dom';
import {
  Database, Globe2, TrendingUp, Users, Gift, ShieldAlert, Mail,
} from 'lucide-react';
import SourceLink from '../components/SourceLink';
import Button from '../components/Button';
import { InfoCard, InfoGrid } from '../components/InfoCard';
import useDocumentMeta from '../lib/useMeta';
import { getPageSeo } from '../lib/pageMeta';
import { useLocale, useT } from '../i18n';
import { track, events } from '../lib/track';
import { footerSourceLinks } from '../lib/footerNav';
import Breadcrumbs from '../components/Breadcrumbs';
import { toolTrail } from '../lib/breadcrumbs';
import '../styles/w5-pages.css';

const CONTACT_EMAIL = 'rebeka.ee@yandex.ru';

/**
 * «О проекте»: короткий лид и карточки-разделы с иконками. Каждая карточка — одна мысль в 1–2
 * предложениях; страница читается за полминуты, без жаргона.
 */
export default function About() {
  const { locale } = useLocale();
  const t = useT();
  const seo = getPageSeo('about', locale);
  useDocumentMeta({
    title: seo.title,
    description: seo.description,
    path: seo.path,
  });

  const sources = footerSourceLinks(locale);
  const andWord = locale === 'en' ? 'and' : 'и';

  return (
    <div className="fe-data-page max-w-3xl mx-auto px-4 md:px-8 pt-24 md:pt-28 pb-12 md:pb-16">
      <Breadcrumbs items={toolTrail(seo.h1, seo.path)} className="mb-6" />

      <header className="mb-8 fe-reveal">
        <h1 className="mb-4 font-display text-3xl font-bold leading-tight text-text-primary md:text-4xl">
          {seo.h1}
        </h1>
        <p className="x4-lead" style={{ marginBottom: 0 }}>{t('x4.about.lead')}</p>
      </header>

      <InfoGrid>
        <InfoCard icon={Database} title={t('x4.about.sources.title')} id="what">
          <p>{t('x4.about.sources.body')}</p>
          <p>
            {sources.map((item, i) => {
              const link = (
                <SourceLink key={item.key} href={item.href}>
                  {t(item.key)}
                </SourceLink>
              );
              if (i === 0) return link;
              if (i === sources.length - 1) return <span key={item.key}> {andWord} {link}</span>;
              return <span key={item.key}>, {link}</span>;
            })}
            .
          </p>
        </InfoCard>

        <InfoCard icon={Globe2} title={t('x4.about.inside.title')}>
          <p>{t('x4.about.inside.body')}</p>
        </InfoCard>

        <InfoCard icon={TrendingUp} title={t('x4.about.forecast.title')} id="different">
          <p>{t('x4.about.forecast.body')}</p>
          <p><Link to="/methodology">{t('x4.about.forecast.link')}</Link></p>
        </InfoCard>

        <InfoCard icon={Users} title={t('x4.about.audience.title')} id="audience">
          <p>{t('x4.about.audience.body')}</p>
        </InfoCard>

        <InfoCard icon={Gift} title={t('x4.about.free.title')}>
          <p>{t('x4.about.free.body')}</p>
        </InfoCard>

        <InfoCard icon={ShieldAlert} title={t('x4.about.limits.title')} id="trust">
          <p>{t('x4.about.limits.body')}</p>
        </InfoCard>

        <InfoCard icon={Mail} title={t('x4.about.contact.title')} wide>
          <p>{t('x4.about.contact.body')}</p>
          <div className="pt-1">
            <Button
              as="a"
              href={`mailto:${CONTACT_EMAIL}`}
              variant="secondary"
              onClick={() => track(events.CONTACT_EMAIL)}
              aria-label={t('x4.about.contact.aria')}
            >
              <Mail className="h-4 w-4" aria-hidden="true" />
              {t('x4.about.contact.cta')}
            </Button>
          </div>
        </InfoCard>
      </InfoGrid>

      {/* Благодарности — всегда одной строкой с текстом: заголовок без содержимого пугает. */}
      <p id="credits" className="x4-credits">
        <strong>{t('about.creditsTitle')}.</strong>
        {' '}
        {t('w5.about.credits.before')}
        {' '}
        <a href="https://www.solarsystemscope.com/textures/" target="_blank" rel="noopener noreferrer">Solar System Scope</a>
        {', '}
        <a href="https://creativecommons.org/licenses/by/4.0/" target="_blank" rel="noopener noreferrer">CC BY 4.0</a>
        .
      </p>
    </div>
  );
}
