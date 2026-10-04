import { useCallback, useEffect, useMemo, useState } from 'react';
import Chip from './Chip';
import ChipGroup from './ChipGroup';
import { track, events } from '../lib/track';
import { useLocale, useT } from '../i18n';
import { localizeViewModeLabel } from '../i18n/viewModeLabels';
import {
  CBR_TERM_SLICE_TOP_GROUPS,
  expandedGroupForMode,
  getTopGroup,
  highlightedTopGroup,
} from '../lib/cbrTermSliceRateGroups';

export default function CbrTermSliceRateViewModePicker({
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
      cbrTermSliceViewGroup: groupId,
      indicator: trackContext?.code,
      indicatorCategory: trackContext?.category,
    });
  }, [trackContext?.code, trackContext?.category]);

  const onTopClick = (group) => {
    if (group.leafMode) {
      setExpandedGroup(null);
      onChange(group.leafMode);
      trackMode(group.leafMode, group.id);
    }
  };

  const topGroups = useMemo(() => (
    CBR_TERM_SLICE_TOP_GROUPS.map((g) => ({
      ...g,
      label: localizeViewModeLabel(g.label, locale),
    }))
  ), [locale]);
  const expanded = expandedGroup ? getTopGroup(expandedGroup) : null;
  const subModes = expanded?.modes ?? [];
  const activeTopGroup = highlightedTopGroup(expandedGroup, currentMode);

  const body = (
    <>
      <p className="mb-3 text-[11px] font-mono uppercase tracking-[0.2em] text-text-tertiary">
        {t('indicator.picker.mode')}
      </p>
      <ChipGroup label={t('indicator.picker.mode')}>
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
            <Chip key={item.mode} active={item.mode === currentMode}>
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
