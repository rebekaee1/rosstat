import { useCallback, useEffect, useMemo, useState } from 'react';
import Chip from './Chip';
import ChipGroup from './ChipGroup';
import { track, events } from '../lib/track';
import { useLocale, useT } from '../i18n';
import { localizeViewModeLabel } from '../i18n/viewModeLabels';
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

  const topGroups = useMemo(() => (
    UNEMPLOYMENT_TOP_GROUPS.map((g) => ({
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
        {t('indicator.picker.mode')}
      </p>
      <ChipGroup label={t('indicator.picker.mode')}>
        {topGroups.map((group) => (
          <Chip
            key={group.id}
            active={group.id === activeTopGroup}
            onClick={() => onTopClick(group)}
          >
            {group.label}
          </Chip>
        ))}
      </ChipGroup>
      {subModes.length > 0 && (
        <ChipGroup label={localizeViewModeLabel(expanded?.label, locale)} className="mt-3 border-t border-border-subtle pt-3">
          {subModes.map((item) => (
            <Chip
              key={item.mode}
              active={item.mode === currentMode}
              onClick={() => {
                onChange(item.mode);
                trackMode(item.mode, expandedGroup);
              }}
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
