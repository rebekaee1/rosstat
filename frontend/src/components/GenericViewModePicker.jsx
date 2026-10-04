import { useCallback, useEffect, useMemo, useState } from 'react';
import ModeGroupsPicker from './ModeGroupsPicker';
import { track, events } from '../lib/track';
import { useLocale, useT } from '../i18n';
import { pickerLabel } from '../lib/pickerLabels';
import {
  buildViewModeGroups,
  defaultSubModeForGroup,
  expandedGroupForMode,
  highlightedTopGroup,
} from '../lib/viewModeEngine';

/**
 * Config-driven двухуровневый переключатель режимов.
 *
 * Заменяет ~20 рукописных `*ViewModePicker` — структура групп/подрежимов
 * целиком берётся из canonical-конфига (`viewModeEngine.buildViewModeGroups`).
 * Верхний ряд — семантические группы («На конец периода» / «Средняя» /
 * «К прошлому периоду» / «Год к году»); нижний ряд — гранулярности внутри
 * группы (по кварталам / по годам). Leaf-группа (Г/г) — одиночная кнопка.
 */
export default function GenericViewModePicker({
  family,
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
    const raw = buildViewModeGroups(family);
    return raw.map((g) => ({
      ...g,
      rawLabel: g.label,
      label: pickerLabel(g.label, locale),
      modes: g.modes?.map((m) => ({
        ...m,
        label: pickerLabel(m.label, locale),
      })),
    }));
  }, [family, locale]);
  const [expandedGroup, setExpandedGroup] = useState(
    () => expandedGroupForMode(family, currentMode),
  );

  useEffect(() => {
    setExpandedGroup(expandedGroupForMode(family, currentMode));
  }, [family, currentMode]);

  const trackMode = useCallback((mode, groupId) => {
    track(events.CHART_MODE_CHANGE, {
      mode,
      viewGroup: groupId,
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
      const next = defaultSubModeForGroup(family, group.id);
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

  const activeTopGroup = highlightedTopGroup(family, expandedGroup, currentMode);
  const expanded = groups.find((g) => g.id === expandedGroup && !g.leafMode);
  const subModes = expanded?.modes ?? [];

  if (groups.length <= 1 && (groups[0]?.modes?.length ?? 0) <= 1) return null;

  return (
    <ModeGroupsPicker
      title={sectionTitle}
      groups={groups}
      activeGroupId={activeTopGroup}
      onTopClick={onTopClick}
      subModes={subModes}
      subGroupLabel={expanded?.label}
      currentMode={currentMode}
      onSubClick={(item) => onSubClick(expandedGroup, item)}
      compact={compact}
    />
  );
}
