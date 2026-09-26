import { Info, Database, ExternalLink } from 'lucide-react';
import { useLocale, useT } from '../i18n';
import { localizeSource } from '../i18n/viewModeLabels';
import { footerSourceLinks } from '../lib/footerNav';
import { russiaHomePath, russiaIndicatorPath } from '../lib/sitePaths';
import { isExternalHref, pickExternalHref } from '../lib/sourceLink';
import SourceLink from './SourceLink';

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
  // Внутренний переход — только когда URL источника неизвестен.
  const internalPath = sourcePath && !isExternalHref(sourcePath) ? sourcePath : null;
  let sourceTo = internalPath || (indicator?.code ? russiaIndicatorPath(indicator.code) : russiaHomePath());
  if (!internalPath && (low.includes('росстат') || low.includes('rosstat'))) sourceTo = russiaHomePath();
  if (!internalPath && low.includes('минфин')) sourceTo = russiaIndicatorPath('budget-deficit');
  if (!internalPath && low.includes('банк россии')) sourceTo = russiaIndicatorPath('key-rate');
  const description = content?.description || (locale === 'en'
    ? `${indicator?.name || 'This indicator'} shows the published observations and their dates. Select a view above the chart to inspect its level or change over time.`
    : `${indicator?.name || 'Показатель'}: на графике показаны опубликованные наблюдения и их даты. Режим над графиком позволяет изучить уровень или изменение ряда.`);
  const methodology = content?.methodology || (locale === 'en'
    ? `Source: ${sourceName || 'the listed data provider'}. Forecasts, when available, are shown separately from observations.`
    : `Источник: ${sourceName || 'указанный поставщик данных'}. Прогноз, если он доступен, показан отдельно от фактических значений.`);

  return (
    <section data-block="methodology" className="lg:col-span-1 p-8 rounded-[2rem] bg-obsidian-light border border-border-subtle flex flex-col h-full">
      <div className="flex items-center gap-3 mb-6">
        <Info className="w-4 h-4 text-champagne" />
        <h3 className="text-xs font-mono uppercase tracking-[0.2em] text-text-secondary">
          {t('indicator.methodology')}
        </h3>
      </div>

      <div className="prose prose-sm max-w-none">
        <p className="text-text-secondary leading-relaxed">
          {description}
        </p>
        {methodology && (
          <div className="text-text-tertiary border-l-2 border-champagne/40 pl-4 my-4 text-xs leading-relaxed">
            {methodology}
          </div>
        )}
      </div>

      {indicator?.source ? (
        <div className="mt-auto pt-6 border-t border-border-subtle">
          <SourceLink
            href={externalHref}
            fallbackTo={sourceTo}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-surface border border-border-subtle text-xs font-mono uppercase tracking-widest text-champagne hover:bg-champagne/10 transition-colors lift-hover w-full justify-center"
          >
            <Database className="w-3.5 h-3.5" />
            {sourceLabel}
            {externalHref ? <ExternalLink className="w-3 h-3 ml-auto opacity-50" aria-hidden="true" /> : null}
          </SourceLink>
        </div>
      ) : null}
    </section>
  );
}
