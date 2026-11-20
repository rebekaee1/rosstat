import { useParams, Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { Download, FileText, ArrowLeft } from 'lucide-react';
import Breadcrumbs from '../components/Breadcrumbs';
import Button from '../components/Button';
import NotFound from './NotFound';
import useDocumentMeta from '../lib/useMeta';
import { getPageSeo } from '../lib/pageMeta';
import { crumb, homeCrumb } from '../lib/breadcrumbs';
import { researchArticlePath, researchPath } from '../lib/sitePaths';
import { useLocale, useT } from '../i18n';
import { fetchResearchArticle, researchDownloadHref } from '../lib/api';
import { track, events } from '../lib/track';
import '../styles/w5-pages.css';
import '../styles/research.css';

/**
 * Статья исследования /research/:slug (20.11.2026, исследования по туризму). Текст, графики, таблицы и источники —
 * из /api/v1/research/{slug}: тот же HTML сервер отдаёт роботам (seo_research.render_research_article_html).
 * HTML собран из текста исследования нашим скриптом и лежит в репозитории, поэтому вставляется как есть.
 */
export default function ResearchArticlePage() {
  const { slug } = useParams();
  const { locale } = useLocale();
  const t = useT();
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['research-article', slug, locale],
    queryFn: ({ signal }) => fetchResearchArticle(slug, { signal }),
    staleTime: 300_000,
  });
  const listSeo = getPageSeo('research', locale) || { h1: t('research.title') };
  useDocumentMeta(data ? { title: data.seo_title, description: data.description, path: researchArticlePath(slug) } : null);
  if (isError && error?.response?.status === 404) return <NotFound />;
  const crumbs = [homeCrumb(), crumb(researchPath(), listSeo.h1)];
  if (data) crumbs.push(crumb(researchArticlePath(slug), data.title));
  const onDownload = () => data && track(events.RESEARCH_DOWNLOAD, { report: data.slug, number: data.number, from: 'article' });
  const release = data ? (locale === 'en' ? data.release_en : data.release) : '';

  return (
    <div className="fe-data-page max-w-4xl mx-auto px-4 md:px-8 pt-24 md:pt-28 pb-12 md:pb-16">
      <Breadcrumbs items={crumbs} className="mb-6" />
      {isLoading && <p className="fe-research-state">{t('research.loading')}</p>}
      {isError && <p className="fe-research-state">{t('research.articleError')}</p>}
      {data && (
        <article className="fe-ra">
          <header className="fe-ra-head fe-reveal">
            <div className="fe-research-kicker">
              {t('research.number', { n: data.number })}
              <span aria-hidden="true"> — </span>
              {t('research.release', { r: release })}
            </div>
            <h1 className="mb-4 font-display text-3xl font-bold leading-tight text-text-primary md:text-4xl">{data.title}</h1>
            <p className="x4-lead" style={{ marginBottom: 0 }}>{data.subtitle}</p>
            <ul className="fe-research-card__figures fe-ra-figures">
              {(data.figures || []).slice(0, 4).map((f) => (
                <li key={f.label} className={`tone-${f.tone || 'base'}`}>
                  <strong>{f.value}</strong>
                  <span>{f.label}</span>
                </li>
              ))}
            </ul>
          </header>
          <div className="fe-ra-body" dangerouslySetInnerHTML={{ __html: data.html }} />
          <aside className="fe-ra-pdf fe-panel">
            <a className="fe-ra-pdf__cover" href={researchDownloadHref(data.slug)} download={data.download_name} onClick={onDownload}
              aria-label={`${t('research.download')}: ${data.title}`}>
              <img src={data.cover} alt="" loading="lazy" width="240" height="340" />
            </a>
            <div className="fe-ra-pdf__body">
              <p className="fe-ra-pdf__title">{t('research.pdfTitle')}</p>
              <p className="fe-ra-pdf__text">{t('research.pdfText')}</p>
              <div className="fe-research-card__actions">
                <Button as="a" href={researchDownloadHref(data.slug)} download={data.download_name} onClick={onDownload} variant="primary">
                  <Download className="h-4 w-4" aria-hidden="true" />
                  {t('research.download')}
                </Button>
                <span className="fe-research-card__meta">
                  <FileText className="h-4 w-4" aria-hidden="true" />
                  <span>{t('research.meta', { pages: data.pages, size: String(data.size_mb).replace('.', locale === 'en' ? '.' : ',') })}</span>
                </span>
              </div>
            </div>
          </aside>
          <p className="fe-ra-back">
            <Link to={researchPath()}>
              <ArrowLeft className="h-4 w-4" aria-hidden="true" />
              {t('research.allStudies')}
            </Link>
          </p>
          <p className="fe-research-footnote">{t('research.footnote')}</p>
        </article>
      )}
    </div>
  );
}
