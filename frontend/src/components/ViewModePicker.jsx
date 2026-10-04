import Chip from './Chip';
import ChipGroup from './ChipGroup';
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
      <p className="mb-3 text-[11px] font-mono uppercase tracking-[0.2em] text-text-tertiary">
        {localizeViewModeLabel(sectionTitle, locale) || sectionTitle}
      </p>
      <ChipGroup label={localizeViewModeLabel(sectionTitle, locale) || sectionTitle}>
        {modes.map((item) => (
          <Chip
            key={item.mode}
            active={currentMode === item.mode}
            onClick={() => {
              onChange(item.mode);
              track(events.CHART_MODE_CHANGE, {
                mode: item.mode,
                indicator: trackContext?.code,
                indicatorCategory: trackContext?.category,
              });
            }}
          >
            {localizeViewModeLabel(item.label, locale)}
          </Chip>
        ))}
      </ChipGroup>
    </section>
  );
}
