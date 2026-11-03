import { ChevronDown } from 'lucide-react';
import { useLocale } from '../../i18n';

const TOPICS = [
  ['Безработица по возрасту и полу', 'Unemployment by age and sex', /^unemployment-(?:youth|age-25-54|age-55-64)(?:-women|-men)?$|^unemployment-(?:women|men)$/],
  ['Занятость по возрасту', 'Employment by age', /^employment-rate-(?:youth|age-25-54|age-55-64)$/],
  ['Рабочая сила по возрасту', 'Labour force by age', /^labor-force-(?:youth|age-25-54|age-55-64)$/],
  ['Длительность безработицы', 'Unemployment duration', /^(?:long|short)-term-unemployed$/],
  ['Неполная занятость', 'Part-time employment', /^part-time-employed$/],
  ['Регистрация в службе занятости', 'Registration with employment services', /^registered-unemployment-share(?:-quarterly)?$/],
  ['Образование безработных', 'Education of unemployed people', /^unemployed-higher-education-share(?:-annual)?$/],
];

export function hasLaborBreakdowns(indicators) {
  return indicators.some(({ code }) => TOPICS.some(([, , pattern]) => pattern.test(code)));
}

export default function LaborIndicatorGroups({ indicators, gridClass, renderIndicator, expandAll }) {
  const { locale } = useLocale();
  const grouped = TOPICS.map(([ru, en, pattern]) => ({
    title: locale === 'en' ? en : ru,
    items: indicators.filter(({ code }) => pattern.test(code)),
  })).filter(({ items }) => items.length > 0);
  const groupedCodes = new Set(grouped.flatMap(({ items }) => items.map(({ code }) => code)));
  const headline = indicators.find(({ code }) => code === 'unemployment');
  const overview = indicators.filter(({ code }) => code !== 'unemployment' && !groupedCodes.has(code));
  if (headline) overview.unshift(headline);

  return (
    <div data-block="labor-indicator-groups">
      {overview.length > 0 && <div className={gridClass}>{overview.map(renderIndicator)}</div>}
      {grouped.length > 0 && (
        <section className="mt-6">
          <h3 className="mb-3 text-lg font-semibold text-text-primary">
            {locale === 'en' ? 'Breakdowns by topic' : 'Разрезы по темам'}
          </h3>
          <div className="grid items-start gap-2.5">
            {grouped.map(({ title, items }) => (
              <details key={title} open={expandAll || undefined} className="group min-w-0 rounded-2xl fe-glass-lite">
                <summary className="flex min-h-12 cursor-pointer list-none items-center gap-3 px-4 py-3 text-sm font-semibold text-text-primary [&::-webkit-details-marker]:hidden">
                  <span className="min-w-0 flex-1">{title}</span>
                  <span className="shrink-0 tabular-nums text-text-secondary">{items.length}</span>
                  <ChevronDown aria-hidden="true" size={16} className="shrink-0 text-text-secondary group-open:rotate-180" />
                </summary>
                <div className="px-3 pb-3">
                  <div className={gridClass}>{items.map(renderIndicator)}</div>
                </div>
              </details>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
