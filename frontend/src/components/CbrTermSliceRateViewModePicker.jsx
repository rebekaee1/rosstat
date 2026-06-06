import { useCallback, useEffect, useState } from 'react';
import { cn } from '../lib/format';
import { track, events } from '../lib/track';
import {
  CBR_TERM_SLICE_TOP_GROUPS,
  expandedGroupForMode,
  getTopGroup,
  highlightedTopGroup,
} from '../lib/cbrTermSliceRateGroups';

const btnCls = (active) => cn(
  'rounded-xl px-3 py-2 text-xs font-medium transition-colors',
  active
    ? 'bg-champagne/15 text-champagne'
    : 'bg-obsidian-lighter text-text-secondary hover:text-champagne',
);

export default function CbrTermSliceRateViewModePicker({
  currentMode,
  onChange,
  trackContext,
  compact = false,
}) {
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

  const expanded = expandedGroup ? getTopGroup(expandedGroup) : null;
  const subModes = expanded?.modes ?? [];
  const activeTopGroup = highlightedTopGroup(expandedGroup, currentMode);

  const body = (
    <>
      <p className="mb-3 text-[10px] font-mono uppercase tracking-[0.2em] text-text-tertiary">
        Режим показателя
      </p>
      <div className="flex flex-wrap gap-2">
        {CBR_TERM_SLICE_TOP_GROUPS.map((group) => {
          const active = group.id === activeTopGroup;
          return (
            <button
              key={group.id}
              type="button"
              onClick={() => onTopClick(group)}
              className={btnCls(active)}
            >
              {group.label}
            </button>
          );
        })}
      </div>
      {subModes.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-2 border-t border-border-subtle pt-3">
          {subModes.map((item) => (
            <button
              key={item.mode}
              type="button"
              className={btnCls(item.mode === currentMode)}
            >
              {item.label}
            </button>
          ))}
        </div>
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
