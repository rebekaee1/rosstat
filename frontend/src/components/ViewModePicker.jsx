import Chip from './Chip';
import { OverflowChipGroup } from './ChipGroup';
import { track, events } from '../lib/track';
import { useLocale, useT } from '../i18n';
import { pickerLabel } from '../lib/pickerLabels';
import { PickerCard, PickerLabel } from './PickerParts';

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
  const sectionTitle = title || t('w3.picker.showAs');
  return (
    <PickerCard>
      <PickerLabel>{pickerLabel(sectionTitle, locale) || sectionTitle}</PickerLabel>
      <OverflowChipGroup
        label={pickerLabel(sectionTitle, locale) || sectionTitle}
        grid
        items={modes}
        isActive={(item) => currentMode === item.mode}
        renderChip={(item) => (
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
            {pickerLabel(item.label, locale)}
          </Chip>
        )}
      />
    </PickerCard>
  );
}
