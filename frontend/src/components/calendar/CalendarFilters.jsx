import { Filter, X } from 'lucide-react';
import { cn } from '../../lib/format';
import { FOCUS_RING_SURFACE } from '../../lib/uiTokens';
import { useT } from '../../i18n';

function Pill({ active, onClick, children, className }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        FOCUS_RING_SURFACE,
        'px-3 py-1.5 rounded-xl text-sm font-medium transition-all duration-200 whitespace-nowrap',
        active
          ? 'bg-champagne/10 text-champagne border border-champagne/20'
          : 'bg-obsidian-lighter/50 text-text-secondary border border-transparent hover:bg-obsidian-lighter hover:text-text-primary',
        className,
      )}
    >
      {children}
    </button>
  );
}

export default function CalendarFilters({
  source, onSourceChange,
  importance, onImportanceChange,
  period, onPeriodChange,
}) {
  const t = useT();
  const hasFilters = source || importance;

  const sourceOptions = [
    { value: '', label: t('calendar.filter.allSources') },
    { value: 'cbr', label: t('calendar.filter.cbr') },
    { value: 'rosstat', label: t('calendar.filter.rosstat') },
    { value: 'minfin', label: t('calendar.filter.minfin') },
  ];

  const importanceOptions = [
    { value: '', label: t('calendar.filter.anyImportance') },
    { value: '3', label: t('calendar.filter.high') },
    { value: '2,3', label: t('calendar.filter.mediumPlus') },
  ];

  const periodOptions = [
    { value: 'week', label: t('calendar.filter.week') },
    { value: 'month', label: t('calendar.filter.month') },
    { value: 'quarter', label: t('calendar.filter.quarter') },
  ];

  const clearFilters = () => {
    onSourceChange('');
    onImportanceChange('');
  };

  return (
    <div className="sticky top-[4.5rem] z-30 -mx-4 px-4 md:-mx-8 md:px-8 py-3 bg-obsidian/95 backdrop-blur-lg border-b border-border-subtle mb-6">
      <div className="flex flex-wrap items-center gap-2">
        <Filter className="w-4 h-4 text-text-tertiary shrink-0 hidden sm:block" />

        <div className="flex items-center gap-1 overflow-x-auto scrollbar-hide">
          {sourceOptions.map((opt) => (
            <Pill
              key={opt.value || 'all'}
              active={source === opt.value}
              onClick={() => onSourceChange(opt.value)}
            >
              {opt.label}
            </Pill>
          ))}
        </div>

        <span className="hidden sm:inline w-px h-5 bg-border-subtle mx-1" />

        <div className="flex items-center gap-1 overflow-x-auto scrollbar-hide">
          {importanceOptions.map((opt) => (
            <Pill
              key={opt.value || 'any'}
              active={importance === opt.value}
              onClick={() => onImportanceChange(opt.value)}
            >
              {opt.label}
            </Pill>
          ))}
        </div>

        <span className="hidden sm:inline w-px h-5 bg-border-subtle mx-1" />

        <div className="flex items-center gap-1 overflow-x-auto scrollbar-hide">
          {periodOptions.map((opt) => (
            <Pill
              key={opt.value}
              active={period === opt.value}
              onClick={() => onPeriodChange(opt.value)}
            >
              {opt.label}
            </Pill>
          ))}
        </div>

        {hasFilters && (
          <button
            type="button"
            onClick={clearFilters}
            className="inline-flex items-center gap-1 text-xs text-text-tertiary hover:text-text-primary transition-colors ml-auto"
          >
            <X className="w-3 h-3" />
            {t('calendar.filter.clear')}
          </button>
        )}
      </div>
    </div>
  );
}
