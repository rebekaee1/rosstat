import { useCallback } from 'react';
import Chip from './Chip';
import ChipGroup from './ChipGroup';
import { track, events } from '../lib/track';
import { useT } from '../i18n';
import {
  DEATHS_TOP_GROUPS,
  highlightedTopGroup,
} from '../lib/deathsViewModeGroups';

export default function DeathsViewModePicker({
  currentMode,
  onChange,
  trackContext,
  compact = false,
}) {
  const t = useT();
  const trackMode = useCallback((mode, groupId) => {
    track(events.CHART_MODE_CHANGE, {
      mode,
      deathsViewGroup: groupId,
      indicator: trackContext?.code,
      indicatorCategory: trackContext?.category,
    });
  }, [trackContext?.code, trackContext?.category]);

  const activeTopGroup = highlightedTopGroup(null, currentMode);

  const body = (
    <>
      <p className="mb-3 text-[11px] font-mono uppercase tracking-[0.2em] text-text-tertiary">
        {t('indicator.picker.mode')}
      </p>
      <ChipGroup label={t('indicator.picker.mode')}>
        {DEATHS_TOP_GROUPS.map((group) => {
          const active = group.id === activeTopGroup;
          return (
            <Chip
              key={group.id}
              active={active}
              onClick={() => {
                onChange(group.leafMode);
                trackMode(group.leafMode, group.id);
              }}
            >
              {group.label}
            </Chip>
          );
        })}
      </ChipGroup>
    </>
  );

  if (compact) {
    return <div className="space-y-2">{body}</div>;
  }

  return (
    <section className="mb-6 rounded-[1.5rem] border border-border-subtle bg-surface p-4 shadow-sm">
      {body}
    </section>
  );
}
