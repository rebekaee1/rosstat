import { Link } from 'react-router-dom';
import {
  Database, LineChart, GitBranch, ShieldCheck, RefreshCw, AlertTriangle,
  Sigma, Ban, Eye,
} from 'lucide-react';
import useDocumentMeta from '../lib/useMeta';
import { getPageSeo } from '../lib/pageMeta';
import { useLocale, useT } from '../i18n';

const CARD = 'rounded-2xl bg-surface border border-border-subtle p-5 md:p-6';
const H2 = 'font-display text-2xl md:text-3xl font-bold text-text-primary mb-4 leading-tight';
const P = 'text-text-secondary leading-relaxed';

function Step({ n, title, children }) {
  return (
    <li className="relative pl-14 pb-8 last:pb-0">
      <span className="absolute left-0 top-0 flex items-center justify-center w-10 h-10 rounded-full bg-champagne/10 border border-champagne/30 text-champagne font-display font-bold">
        {n}
      </span>
      <h3 className="text-base font-semibold text-text-primary mb-2">{title}</h3>
      <p className={`${P} text-[15px]`}>{children}</p>
    </li>
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

  const skipItems = [
    ['meth.skip.1title', 'meth.skip.1body'],
    ['meth.skip.2title', 'meth.skip.2body'],
    ['meth.skip.3title', 'meth.skip.3body'],
  ];

  return (
    <div className="max-w-4xl mx-auto px-4 md:px-8 pt-24 md:pt-28 pb-20 md:pb-24">
      <p className="text-[10px] uppercase tracking-[0.3em] text-champagne font-semibold mb-4">
        {t('meth.eyebrow')}
      </p>
      <h1 className="font-display text-3xl md:text-5xl font-bold text-text-primary mb-6 leading-[1.1]">
        {seo.h1}
      </h1>
      <p className="text-lg text-text-secondary leading-relaxed mb-4">
        {t('meth.intro.p1')}
      </p>
      <p className={`${P} mb-4`}>
        {t('meth.intro.p2')}
      </p>
      <p className={`${P} mb-12`}>
        {t('meth.intro.p3')}
      </p>

      <section className="mb-16">
        <h2 className={H2}>{t('meth.principlesTitle')}</h2>
        <div className="grid sm:grid-cols-2 gap-4">
          <div className={CARD}>
            <Database className="w-6 h-6 text-champagne mb-3" />
            <h3 className="font-semibold text-text-primary mb-1.5">{t('meth.p.officialTitle')}</h3>
            <p className={`${P} text-[14px]`}>{t('meth.p.officialBody')}</p>
          </div>
          <div className={CARD}>
            <Sigma className="w-6 h-6 text-champagne mb-3" />
            <h3 className="font-semibold text-text-primary mb-1.5">{t('meth.p.reproTitle')}</h3>
            <p className={`${P} text-[14px]`}>{t('meth.p.reproBody')}</p>
          </div>
          <div className={CARD}>
            <ShieldCheck className="w-6 h-6 text-champagne mb-3" />
            <h3 className="font-semibold text-text-primary mb-1.5">{t('meth.p.uncertTitle')}</h3>
            <p className={`${P} text-[14px]`}>{t('meth.p.uncertBody')}</p>
          </div>
          <div className={CARD}>
            <Ban className="w-6 h-6 text-champagne mb-3" />
            <h3 className="font-semibold text-text-primary mb-1.5">{t('meth.p.limitsTitle')}</h3>
            <p className={`${P} text-[14px]`}>{t('meth.p.limitsBody')}</p>
          </div>
        </div>
      </section>

      <section className="mb-16">
        <h2 className={H2}>{t('meth.stepsTitle')}</h2>
        <p className={`${P} mb-8`}>{t('meth.stepsIntro')}</p>
        <ol className="relative">
          <Step n="1" title={t('meth.step.1title')}>{t('meth.step.1body')}</Step>
          <Step n="2" title={t('meth.step.2title')}>{t('meth.step.2body')}</Step>
          <Step n="3" title={t('meth.step.3title')}>{t('meth.step.3body')}</Step>
          <Step n="4" title={t('meth.step.4title')}>{t('meth.step.4body')}</Step>
        </ol>
      </section>

      <section className="mb-16">
        <h2 className={H2}>{t('meth.worldTitle')}</h2>
        <p className={`${P} mb-4`}>{t('meth.world.p1')}</p>
        <p className={`${P} mb-4`}>{t('meth.world.p2')}</p>
        <p className={P}>{t('meth.world.p3')}</p>
      </section>

      <section className="mb-16">
        <h2 className={H2}>{t('meth.updateTitle')}</h2>
        <div className="grid sm:grid-cols-2 gap-4">
          <div className={CARD}>
            <RefreshCw className="w-6 h-6 text-champagne mb-3" />
            <h3 className="font-semibold text-text-primary mb-1.5">{t('meth.update.modelTitle')}</h3>
            <p className={`${P} text-[14px]`}>{t('meth.update.modelBody')}</p>
          </div>
          <div className={CARD}>
            <GitBranch className="w-6 h-6 text-champagne mb-3" />
            <h3 className="font-semibold text-text-primary mb-1.5">{t('meth.update.derivedTitle')}</h3>
            <p className={`${P} text-[14px]`}>{t('meth.update.derivedBody')}</p>
          </div>
        </div>
      </section>

      <section className="mb-16">
        <h2 className={H2}>{t('meth.skipTitle')}</h2>
        <p className={`${P} mb-6`}>{t('meth.skipIntro')}</p>
        <ul className="space-y-3">
          {skipItems.map(([titleKey, bodyKey]) => (
            <li key={titleKey} className="flex gap-3 items-start rounded-2xl bg-surface border border-border-subtle p-4">
              <Ban className="w-5 h-5 text-text-tertiary shrink-0 mt-0.5" />
              <span className="text-[14px] text-text-secondary leading-relaxed">
                <strong className="text-text-primary">{t(titleKey)}.</strong> {t(bodyKey)}
              </span>
            </li>
          ))}
        </ul>
        <p className={`${P} mt-6 text-[14px]`}>{t('meth.skipOutro')}</p>
      </section>

      <section className="mb-16">
        <h2 className={H2}>{t('meth.readTitle')}</h2>
        <div className="flex gap-3 items-start rounded-2xl bg-surface border border-border-subtle p-5 mb-4">
          <Eye className="w-5 h-5 text-champagne shrink-0 mt-0.5" />
          <div className="text-[14px] text-text-secondary leading-relaxed space-y-2">
            <p>{t('meth.read.p1')}</p>
            <p>{t('meth.read.p2')}</p>
          </div>
        </div>
      </section>

      <section className="mb-12">
        <h2 className={H2}>{t('meth.disclaimerTitle')}</h2>
        <div className="flex gap-3 items-start rounded-2xl bg-surface border border-border-subtle p-5">
          <AlertTriangle className="w-5 h-5 text-champagne shrink-0 mt-0.5" />
          <div className="text-[15px] text-text-secondary leading-relaxed space-y-3">
            <p>{t('meth.disclaimer.p1')}</p>
            <p>{t('meth.disclaimer.p2')}</p>
          </div>
        </div>
      </section>

      <div className="flex flex-wrap gap-3">
        <Link
          to="/"
          className="inline-flex items-center gap-2 px-5 py-2.5 rounded-full bg-champagne text-obsidian font-semibold text-sm hover:bg-champagne/90 transition-colors"
        >
          <LineChart className="w-4 h-4" />
          {t('meth.cta.indicators')}
        </Link>
        <Link
          to="/about"
          className="inline-flex items-center gap-2 px-5 py-2.5 rounded-full border border-border-subtle text-text-secondary font-semibold text-sm hover:text-text-primary hover:border-champagne/40 transition-colors"
        >
          {t('meth.cta.about')}
        </Link>
      </div>
    </div>
  );
}
