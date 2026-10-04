import { useCallback, useEffect, useMemo, useState } from 'react';
import ModeGroupsPicker from './ModeGroupsPicker';
import { track, events } from '../lib/track';
import { useLocale, useT } from '../i18n';
import { pickerLabel } from '../lib/pickerLabels';
import {
  cpiTopGroupsForCode,
  defaultSubModeForGroup,
  expandedGroupForMode,
  getTopGroup,
  highlightedTopGroup,
} from '../lib/cpiViewModeGroups';

/**
 * ИПЦ: двухуровневый «Режим инфляции» (вариант A).
 * Верх — семейство; низ — подрежимы с уникальным ?mode= на каждую кнопку.
 */
export default function CpiViewModePicker({
  currentMode,
  onChange,
  trackContext,
  code = null,
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
      cpiViewGroup: groupId,
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
    const currentInGroup = subModes.some(
      (m) => !m.disabled && m.mode === currentMode,
    );
    if (!currentInGroup) {
      const next = defaultSubModeForGroup(group.id, code);
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

  const topGroups = useMemo(() => (
    cpiTopGroupsForCode(code).map((g) => ({
      ...g,
      rawLabel: g.label,
      label: pickerLabel(g.label, locale),
      modes: g.modes?.map((m) => ({
        ...m,
        label: pickerLabel(m.label, locale),
      })),
    }))
  ), [code, locale]);
  const expanded = expandedGroup ? getTopGroup(expandedGroup, code) : null;
  const subModes = useMemo(
    () => (expanded?.modes ?? []).map((m) => ({
      ...m,
      label: pickerLabel(m.label, locale),
    })),
    [expanded, locale],
  );
  const activeTopGroup = highlightedTopGroup(expandedGroup, currentMode);
  const expandedLabel = pickerLabel(expanded?.label, locale);

  const picker = (
    <ModeGroupsPicker
      title={t('w3.picker.showInflation')}
      groups={topGroups}
      activeGroupId={activeTopGroup}
      onTopClick={onTopClick}
      subModes={subModes}
      subGroupLabel={expandedLabel}
      currentMode={currentMode}
      onSubClick={(item) => onSubClick(expanded?.id ?? expandedGroup, item)}
      compact={compact}
    />
  );

  if (compact) return <div className="fe-pick-embedded">{picker}</div>;
  return picker;
}
