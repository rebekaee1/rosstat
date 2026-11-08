import { useQuery } from '@tanstack/react-query';
import { Download, FileText, Send, Bot } from 'lucide-react';
import Breadcrumbs from '../components/Breadcrumbs';
import Button from '../components/Button';
import { toolTrail } from '../lib/breadcrumbs';
import useDocumentMeta from '../lib/useMeta';
import { getPageSeo } from '../lib/pageMeta';
import { useLocale, useT } from '../i18n';
import { fetchResearch, researchDownloadHref } from '../lib/api';
import { track, events } from '../lib/track';
import '../styles/w5-pages.css';
import '../styles/research.css';

const TELEGRAM_CHANNEL = 'https://t.me/forecasteconomy';
const TELEGRAM_BOT = 'https://t.me/ForecastEconomyBot?start=site_research';

function formatCount(n, locale) {
  return new Intl.NumberFormat(locale === 'en' ? 'en-US' : 'ru-RU').format(n || 0);
}

function ReportCard({ item, locale, t }) {
  const onDownload = () => track(events.RESEARCH_DOWNLOAD, { report: item.slug, number: item.number });
  return (
    <article id={item.slug} className="fe-research-card fe-panel fe-reveal">
      <a
        className="fe-research-card__cover"
        href={researchDownloadHref(item.slug)}
        download={item.download_name}
        onClick={onDownload}
        aria-label={`${t('research.download')}: ${item.title}`}
      >
        <img src={item.cover} alt="" loading="lazy" width="240" height="340" />
      </a>
      <div className="fe-research-card__body">
        <div className="fe-research-card__kicker">
          {t('research.number', { n: item.number })}
          <span aria-hidden="true"> — </span>
          {(item.topics || []).join(', ')}
        </div>
        <h2 className="fe-research-card__title">{item.title}</h2>
        <p className="fe-research-card__subtitle">{item.subtitle}</p>
        <ul className="fe-research-card__figures">
          {(item.figures || []).slice(0, 4).map((f) => (
            <li key={f.label} className={`tone-${f.tone || 'base'}`}>
              <strong>{f.value}</strong>
              <span>{f.label}</span>
            </li>
          ))}
        </ul>
        <details className="fe-research-card__more">
          <summary>{t('research.more')}</summary>
          <p>{item.annotation}</p>
          <ol>
            {(item.conclusions || []).map((c) => <li key={c}>{c}</li>)}
          </ol>
        </details>
        <div className="fe-research-card__actions">
          <Button
            as="a"
            href={researchDownloadHref(item.slug)}
            download={item.download_name}
            onClick={onDownload}
            variant="primary"
          >
            <Download className="h-4 w-4" aria-hidden="true" />
            {t('research.download')}
          </Button>
          <span className="fe-research-card__meta">
            <FileText className="h-4 w-4" aria-hidden="true" />
            <span>
              {t('research.meta', { pages: item.pages, size: String(item.size_mb).replace('.', locale === 'en' ? '.' : ',') })}
              {', '}
              {t('research.downloads', { n: formatCount(item.downloads, locale) })}
            </span>
          </span>
        </div>
      </div>
    </article>
  );
}

/**
 * «Исследования»: PDF-отчёты к роликам ForecastEconomy. Каталог и счётчики — /api/v1/research,
 * скачивание — через счётчик сервера (302 на статический PDF в /research/files/).
 */
export default function ResearchPage() {
  const { locale } = useLocale();
  const t = useT();
  const seo = getPageSeo('research', locale) || { h1: t('research.title'), title: t('research.title'), description: '', path: '/research' };
  useDocumentMeta({ title: seo.title, description: seo.description, path: seo.path });
  const { data, isLoading, isError } = useQuery({ queryKey: ['research'], queryFn: ({ signal }) => fetchResearch({ signal }), staleTime: 60_000 });
  const release = locale === 'en' ? data?.release_en : data?.release;

  return (
    <div className="fe-data-page max-w-5xl mx-auto px-4 md:px-8 pt-24 md:pt-28 pb-12 md:pb-16">
      <Breadcrumbs items={toolTrail(seo.h1, seo.path)} className="mb-6" />
      <header className="mb-8 fe-reveal">
        <div className="fe-research-kicker">{release ? t('research.release', { r: release }) : ''}</div>
        <h1 className="mb-4 font-display text-3xl font-bold leading-tight text-text-primary md:text-4xl">{seo.h1}</h1>
        <p className="x4-lead" style={{ marginBottom: 0 }}>{t('research.lead')}</p>
        {locale === 'en' && <p className="fe-research-note">{t('research.ruNote')}</p>}
        <div className="fe-research-links">
          <Button as="a" href={TELEGRAM_BOT} target="_blank" rel="noopener noreferrer" variant="secondary">
            <Bot className="h-4 w-4" aria-hidden="true" />
            {t('research.bot')}
          </Button>
          <Button as="a" href={data?.group_url || TELEGRAM_CHANNEL} target="_blank" rel="noopener noreferrer" variant="ghost">
            <Send className="h-4 w-4" aria-hidden="true" />
            {data?.group_url ? t('research.group') : t('research.channel')}
          </Button>
        </div>
      </header>
      {isLoading && <p className="fe-research-state">{t('research.loading')}</p>}
      {isError && <p className="fe-research-state">{t('research.error')}</p>}
      <div className="fe-research-list">
        {(data?.items || []).map((item) => <ReportCard key={item.slug} item={item} locale={locale} t={t} />)}
      </div>
      <p className="fe-research-footnote">{t('research.footnote')}</p>
    </div>
  );
}
