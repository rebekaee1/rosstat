import { useCallback, useEffect, useMemo, useState } from 'react';
import Chip from './Chip';
import ChipGroup, { OverflowChipGroup } from './ChipGroup';
import { track, events } from '../lib/track';
import { useLocale, useT } from '../i18n';
import { pickerLabel, pickerHintKey } from '../lib/pickerLabels';
import { PickerCard, PickerLabel, PickerHint } from './PickerParts';
import { modeSummaryText, useViewModeSummary } from './viewModesContext';
import {
  defaultModeForWorldGroup,
  expandedGroupForWorldMode,
  groupModesFromApi,
} from '../lib/worldViewModes';

function aggregatedModeHint(item, t) {
  if (item.disabled) return t('world.mode.hint.unavailable');
  if (item.official) return undefined;
  const src = item.aggregation?.source_frequency;
  if (src === 'weekly') return t('world.mode.hint.derivedWeekly');
  if (src === 'daily') return t('world.mode.hint.derivedDaily');
  const policy = item.aggregation?.policy;
  if (policy === 'sum') return t('world.mode.hint.sum');
  if (policy === 'last') return t('world.mode.hint.last');
  if (policy === 'mean') return t('world.mode.hint.mean');
  return t('world.mode.hint.derived');
}

/**
 * Двухуровневый переключатель мировой карточки.
 * Визуально = российские макрокарточки (не segmented-control «быстрых» страниц).
 */
export default function WorldViewModePicker({
  modes,
  currentMode,
  onChange,
  trackContext,
  title,
  compact = false,
}) {
  const t = useT();
  const { locale } = useLocale();
  const sectionTitle = title || t('w3.picker.showAs');
  const groups = useMemo(() => {
    const raw = groupModesFromApi(modes);
    return raw.map((g) => ({
      ...g,
      rawLabel: g.label,
      label: locale !== 'en' && g.label === 'Уровень' ? 'Значения' : pickerLabel(g.label, locale),
      modes: g.modes?.map((m) => ({
        ...m,
        label: pickerLabel(m.label, locale),
        hint: aggregatedModeHint(m, t),
      })),
    }));
  }, [modes, locale, t]);
  const [expandedGroup, setExpandedGroup] = useState(
    () => expandedGroupForWorldMode(groups, currentMode),
  );

  useEffect(() => {
    setExpandedGroup(expandedGroupForWorldMode(groups, currentMode));
  }, [groups, currentMode]);

  const trackMode = useCallback((mode, groupId) => {
    track(events.CHART_MODE_CHANGE, {
      mode,
      viewGroup: groupId,
      indicator: trackContext?.code,
      indicatorCategory: trackContext?.category,
      world: true,
    });
  }, [trackContext?.code, trackContext?.category]);

  const onTopClick = (group) => {
    if (group.leafMode) {
      setExpandedGroup(group.id);
      onChange(group.leafMode);
      trackMode(group.leafMode, group.id);
      return;
    }
    setExpandedGroup(group.id);
    const currentInGroup = group.modes?.some(
      (m) => !m.disabled && m.mode === currentMode,
    );
    if (!currentInGroup) {
      const next = defaultModeForWorldGroup(groups, group.id);
      if (next) {
        onChange(next);
        trackMode(next, group.id);
      }
    }
  };

  const onSubClick = (groupId, item) => {
    if (item.disabled) return;
    onChange(item.mode);
    trackMode(item.mode, groupId);
  };

  const expanded = groups.find((g) => g.id === expandedGroup && !g.leafMode);
  const subModes = expanded?.modes ?? [];
  const activeTopGroup = expandedGroupForWorldMode(groups, currentMode);

  const activeGroup = groups.find((g) => g.id === activeTopGroup);
  const hintKey = pickerHintKey(activeGroup?.rawLabel);
  const visibleSub = subModes.filter((item) => !item.disabled);
  const currentSub = visibleSub.length > 1 ? visibleSub.find((item) => item.mode === currentMode) : null;
  const nothingToPick = groups.length === 0 || (groups.length <= 1 && (groups[0]?.modes?.length ?? 0) <= 1);
  useViewModeSummary(
    'mode', 20,
    nothingToPick ? '' : modeSummaryText(activeGroup?.label, currentSub?.label),
  );

  if (nothingToPick) return null;

  const body = (
    <>
      <PickerLabel>{sectionTitle}</PickerLabel>
      <ChipGroup label={sectionTitle} grid>
        {groups.map((group) => (
          <Chip
            key={group.id}
            active={group.id === activeTopGroup}
            onClick={() => onTopClick(group)}
          >
            {group.label}
          </Chip>
        ))}
      </ChipGroup>
      <PickerHint>{hintKey ? t(hintKey) : null}</PickerHint>
      {visibleSub.length > 1 && (
        <div className="fe-pick-sub">
          <PickerLabel>{t('w3.picker.detail')}</PickerLabel>
          <OverflowChipGroup
            label={expanded?.label}
            dense
            items={visibleSub}
            isActive={(item) => item.mode === currentMode}
            renderChip={(item) => (
              <Chip
                key={`${expanded.id}-${item.mode}`}
                active={item.mode === currentMode}
                title={item.hint || undefined}
                onClick={() => onSubClick(expanded.id, item)}
              >
                {!item.official ? <span aria-hidden="true" className="mr-1 font-normal">≈</span> : null}
                {item.label}
              </Chip>
            )}
          />
          {visibleSub.some((item) => !item.official) ? (
            <PickerHint>{t('x2.picker.derivedNote')}</PickerHint>
          ) : null}
        </div>
      )}
    </>
  );

  if (compact) {
    return <div className="fe-pick-embedded">{body}</div>;
  }

  return <PickerCard className="min-w-0">{body}</PickerCard>;
}
