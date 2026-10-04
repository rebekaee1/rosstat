import { useCallback, useEffect, useMemo, useState } from 'react';
import ModeGroupsPicker from './ModeGroupsPicker';
import { track, events } from '../lib/track';
import { useLocale, useT } from '../i18n';
import { pickerLabel } from '../lib/pickerLabels';
import {
  UNEMPLOYMENT_TOP_GROUPS,
  defaultSubModeForGroup,
  expandedGroupForMode,
  getTopGroup,
  highlightedTopGroup,
} from '../lib/unemploymentViewModeGroups';

export default function UnemploymentViewModePicker({
  currentMode,
  onChange,
  trackContext,
  compact = false,
}) {
  const t = useT();
  const { locale } = useLocale();
  const [expandedGroup, setExpandedGroup] = useState(
    () => expandedGroupForMode(currentMode),
  );

  useEffect(() => {
    setExpandedGroup(expandedGroupForMode(currentMode));
  }, [currentMode]);

  const trackMode = useCallback((mode, groupId) => {
    track(events.CHART_MODE_CHANGE, {
      mode,
      unemploymentViewGroup: groupId,
      indicator: trackContext?.code,
      indicatorCategory: trackContext?.category,
    });
  }, [trackContext?.code, trackContext?.category]);

  const onTopClick = (group) => {
    if (group.leafMode) {
      setExpandedGroup(null);
      onChange(group.leafMode);
      trackMode(group.leafMode, group.id);
      return;
    }
    setExpandedGroup(group.id);
    const subModes = group.modes ?? [];
    const currentInGroup = subModes.some((m) => m.mode === currentMode);
    if (!currentInGroup) {
      const next = defaultSubModeForGroup(group.id);
      if (next) {
        onChange(next);
        trackMode(next, group.id);
      }
    }
  };

  const onSubClick = (groupId, item) => {
    onChange(item.mode);
    trackMode(item.mode, groupId);
  };

  const topGroups = useMemo(() => (
    UNEMPLOYMENT_TOP_GROUPS.map((g) => ({
      ...g,
      rawLabel: g.label,
      label: pickerLabel(g.label, locale),
      modes: g.modes?.map((m) => ({
        ...m,
        label: pickerLabel(m.label, locale),
      })),
    }))
  ), [locale]);
  const expanded = expandedGroup ? getTopGroup(expandedGroup) : null;
  const subModes = useMemo(
    () => (expanded?.modes ?? []).map((m) => ({
      ...m,
      label: pickerLabel(m.label, locale),
    })),
    [expanded, locale],
  );
  const activeTopGroup = highlightedTopGroup(expandedGroup, currentMode);

  const picker = (
    <ModeGroupsPicker
      title={t('w3.picker.showAs')}
      groups={topGroups}
      activeGroupId={activeTopGroup}
      onTopClick={onTopClick}
      subModes={subModes}
      subGroupLabel={pickerLabel(expanded?.label, locale)}
      currentMode={currentMode}
      onSubClick={(item) => onSubClick(expandedGroup, item)}
      compact={compact}
    />
  );

  return picker;
}
