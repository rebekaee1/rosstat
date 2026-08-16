import { cn } from '../lib/format';
import { track, events } from '../lib/track';
import { useLocale, useT } from '../i18n';
import { localizeViewModeLabel } from '../i18n/viewModeLabels';

/**
 * Generic in-page view-mode switcher used on indicator pages where a
 * single domain concept can be viewed in several aggregations or
 * transformations (e.g. Level / YoY % / QoQ % / Cumulative index).
 */
export default function ViewModePicker({
  title,
  modes,
  currentMode,
  onChange,
  trackContext,
}) {
  const t = useT();
  const { locale } = useLocale();
  const sectionTitle = title || t('indicator.picker.mode');
  return (
    <section className="mb-8 rounded-[1.5rem] border border-border-subtle bg-surface p-4 shadow-sm">
      <p className="mb-3 text-[10px] font-mono uppercase tracking-[0.2em] text-text-tertiary">
        {localizeViewModeLabel(sectionTitle, locale) || sectionTitle}
      </p>
      <div className="flex flex-wrap gap-2">
        {modes.map((item) => (
          <button
            key={item.mode}
            type="button"
            onClick={() => {
              onChange(item.mode);
              track(events.CHART_MODE_CHANGE, {
                mode: item.mode,
                indicator: trackContext?.code,
                indicatorCategory: trackContext?.category,
              });
            }}
            className={cn(
              'rounded-xl px-3 py-2 text-xs font-medium transition-colors',
              currentMode === item.mode
                ? 'bg-champagne/15 text-champagne'
                : 'bg-obsidian-lighter text-text-secondary hover:text-champagne'
            )}
          >
            {localizeViewModeLabel(item.label, locale)}
          </button>
        ))}
      </div>
    </section>
  );
}
