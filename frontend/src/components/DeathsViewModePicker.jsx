import { useCallback } from 'react';
import { cn } from '../lib/format';
import { track, events } from '../lib/track';
import {
  DEATHS_TOP_GROUPS,
  highlightedTopGroup,
} from '../lib/deathsViewModeGroups';

const btnCls = (active) => cn(
  'rounded-xl px-3 py-2 text-xs font-medium transition-colors',
  active
    ? 'bg-champagne/15 text-champagne'
    : 'bg-obsidian-lighter text-text-secondary hover:text-champagne',
);

export default function DeathsViewModePicker({
  currentMode,
  onChange,
  trackContext,
  compact = false,
}) {
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
      <p className="mb-3 text-[10px] font-mono uppercase tracking-[0.2em] text-text-tertiary">
        Режим показателя
      </p>
      <div className="flex flex-wrap gap-2">
        {DEATHS_TOP_GROUPS.map((group) => {
          const active = group.id === activeTopGroup;
          return (
            <button
              key={group.id}
              type="button"
              onClick={() => {
                onChange(group.leafMode);
                trackMode(group.leafMode, group.id);
              }}
              className={btnCls(active)}
            >
              {group.label}
            </button>
          );
        })}
      </div>
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
