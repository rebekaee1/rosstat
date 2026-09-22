import { Link } from 'react-router-dom';
import { Info, Database } from 'lucide-react';
import { useLocale, useT } from '../i18n';
import { localizeSource } from '../i18n/viewModeLabels';
import { footerSourceLinks } from '../lib/footerNav';
import { russiaHomePath, russiaIndicatorPath } from '../lib/sitePaths';

/**
 * Левая колонка под графиком: текст «Методология» + блок «Источник».
 *
 * Текст методологии режим-зависимый и приходит из resolveViewModeContent /
 * API (generic). Блок источника — ссылка/бейдж в зависимости от URL.
 */
export default function IndicatorMethodologyPanel({ indicator, content }) {
  const t = useT();
  const { locale } = useLocale();
  const sourceName = localizeSource(indicator?.source, locale);
  const sourceLabel = t('indicator.source', { source: sourceName });
  const low = (indicator?.source || '').toLowerCase();
  const named = footerSourceLinks(locale).find((item) => t(item.key).toLowerCase() === low);
  let sourceTo = named?.to || (indicator?.code ? russiaIndicatorPath(indicator.code) : russiaHomePath());
  if (low.includes('росстат') || low.includes('rosstat')) sourceTo = russiaHomePath();
  if (low.includes('минфин')) sourceTo = russiaIndicatorPath('budget-deficit');
  if (low.includes('банк россии')) sourceTo = russiaIndicatorPath('key-rate');

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
          {content?.description}
        </p>
        {content?.methodology && (
          <div className="text-text-tertiary border-l-2 border-champagne/30 pl-4 my-4 font-mono text-[10px] uppercase tracking-wider">
            {content.methodology}
          </div>
        )}
      </div>

      {indicator?.source ? (
        <div className="mt-auto pt-6 border-t border-border-subtle">
          <Link
            to={sourceTo}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-surface border border-border-subtle text-xs font-mono uppercase tracking-widest text-champagne hover:bg-champagne/10 transition-colors lift-hover w-full justify-center"
          >
            <Database className="w-3.5 h-3.5" />
            {sourceLabel}
          </Link>
        </div>
      ) : null}
    </section>
  );
}
