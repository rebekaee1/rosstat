import { Info, Database, ExternalLink } from 'lucide-react';
import { useLocale, useT } from '../i18n';
import { localizeSource } from '../i18n/viewModeLabels';
import { footerSourceLinks } from '../lib/footerNav';
import { isExternalHref, pickExternalHref } from '../lib/sourceLink';
import SourceLink from './SourceLink';
import '../styles/indicator-russia.css';
import '../styles/x2-indicator.css';

/**
 * Левая колонка под графиком: текст «Методология» + блок «Источник».
 *
 * Текст методологии режим-зависимый и приходит из resolveViewModeContent /
 * API (generic). Блок источника — ссылка/бейдж в зависимости от URL.
 */
export default function IndicatorMethodologyPanel({ indicator, content, sourcePath }) {
  const t = useT();
  const { locale } = useLocale();
  const sourceName = localizeSource(indicator?.source, locale);
  const sourceLabel = t('indicator.source', { source: sourceName });
  const low = (indicator?.source || '').toLowerCase();
  const named = footerSourceLinks(locale).find((item) => t(item.key).toLowerCase() === low);
  // Реальный адрес источника ряда: sourcePath (world-страницы), source_url из
  // API, затем официальный сайт ведомства по имени. Внешний — в новой вкладке.
  const externalHref = pickExternalHref(sourcePath, indicator?.source_url, named?.href);
  // Внутренний переход — только если вызывающая страница передала страницу
  // самого источника. Ссылка на Россию/текущую карточку маскировала отсутствие URL.
  const internalPath = sourcePath && !isExternalHref(sourcePath) ? sourcePath : null;
  const description = content?.description || (locale === 'en'
    ? `${indicator?.name || 'This indicator'} shows the published observations and their dates. Select a view above the chart to inspect its level or change over time.`
    : `${indicator?.name || 'Показатель'}: на графике показаны опубликованные наблюдения и их даты. Режим над графиком позволяет изучить уровень или изменение ряда.`);
  const methodology = content?.methodology || (locale === 'en'
    ? `Source: ${sourceName || 'the listed data provider'}. Forecasts, when available, are shown separately from observations.`
    : `Источник: ${sourceName || 'указанный поставщик данных'}. Прогноз, если он доступен, показан отдельно от фактических значений.`);

  return (
    <section data-block="methodology" className="fe-reveal fe-reveal--free fe-info-card" style={{ '--fe-duration': '0.35s', '--fe-rise': '10px' }}>
      <div className="fe-info-card__head">
        <Info className="h-4 w-4 text-champagne-ink" aria-hidden="true" />
        <h3 className="fe-info-card__title">{t('indicator.methodology')}</h3>
      </div>

      <div className="fe-info-card__text">
        <div>{description}</div>
        {methodology && (
          <details className="fe-more">
            <summary className="fe-more__summary">{t('w3.method.more')}</summary>
            <div className="fe-more__body">{methodology}</div>
          </details>
        )}
      </div>

      {indicator?.source ? (
        <div className="fe-info-card__foot">
          <SourceLink
            href={externalHref}
            fallbackTo={internalPath}
            className="fe-btn fe-btn--secondary fe-press fe-info-card__source"
            textClassName="fe-info-card__source-text"
          >
            <Database className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
            <span className="min-w-0 whitespace-normal break-words text-left leading-snug">{sourceLabel}</span>
            {externalHref ? <ExternalLink className="ml-auto h-3 w-3 shrink-0 opacity-60" aria-hidden="true" /> : null}
          </SourceLink>
        </div>
      ) : null}
    </section>
  );
}
