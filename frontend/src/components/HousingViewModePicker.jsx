import { useCallback, useEffect, useMemo, useState } from 'react';
import Chip from './Chip';
import ChipGroup from './ChipGroup';
import { track, events } from '../lib/track';
import { useLocale, useT } from '../i18n';
import { localizeViewModeLabel } from '../i18n/viewModeLabels';
import {
  HOUSING_TOP_GROUPS,
  defaultSubModeForGroup,
  expandedGroupForMode,
  getTopGroup,
  highlightedTopGroup,
} from '../lib/housingViewModeGroups';

/**
 * Цены на жильё: двухуровневый переключатель (как CpiViewModePicker).
 */
export default function HousingViewModePicker({
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
      housingViewGroup: groupId,
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
    HOUSING_TOP_GROUPS.map((g) => ({
      ...g,
      label: localizeViewModeLabel(g.label, locale),
      modes: g.modes?.map((m) => ({
        ...m,
        label: localizeViewModeLabel(m.label, locale),
      })),
    }))
  ), [locale]);
  const expanded = expandedGroup ? getTopGroup(expandedGroup) : null;
  const subModes = useMemo(
    () => (expanded?.modes ?? []).map((m) => ({
      ...m,
      label: localizeViewModeLabel(m.label, locale),
    })),
    [expanded, locale],
  );
  const activeTopGroup = highlightedTopGroup(expandedGroup, currentMode);

  const body = (
    <>
      <p className="mb-3 text-[11px] font-mono uppercase tracking-[0.2em] text-text-tertiary">
        {t('indicator.picker.housing')}
      </p>
      <ChipGroup label={t('indicator.picker.housing')}>
        {topGroups.map((group) => {
          const active = group.id === activeTopGroup;
          return (
            <Chip
              key={group.id}
              active={active}
              onClick={() => onTopClick(group)}
            >
              {group.label}
            </Chip>
          );
        })}
      </ChipGroup>
      {subModes.length > 0 && (
        <ChipGroup label={localizeViewModeLabel(expanded?.label, locale)} className="mt-3 border-t border-border-subtle pt-3">
          {subModes.map((item) => (
            <Chip
              key={item.mode}
              active={item.mode === currentMode}
              onClick={() => onSubClick(expandedGroup, item)}
            >
              {item.label}
            </Chip>
          ))}
        </ChipGroup>
      )}
    </>
  );

  if (compact) return body;

  return (
    <section className="mb-8 rounded-[1.5rem] border border-border-subtle bg-surface p-4 shadow-sm">
      {body}
    </section>
  );
}
