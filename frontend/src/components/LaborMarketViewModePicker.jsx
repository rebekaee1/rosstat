import { useCallback, useEffect, useState } from 'react';
import { cn } from '../lib/format';
import { track, events } from '../lib/track';
import {
  LABOR_MARKET_TOP_GROUPS,
  defaultSubModeForGroup,
  expandedGroupForMode,
  getTopGroup,
  highlightedTopGroup,
} from '../lib/laborMarketViewModeGroups';

const btnCls = (active) => cn(
  'rounded-xl px-3 py-2 text-xs font-medium transition-colors',
  active
    ? 'bg-champagne/15 text-champagne'
    : 'bg-obsidian-lighter text-text-secondary hover:text-champagne',
);

export default function LaborMarketViewModePicker({
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
      laborMarketViewGroup: groupId,
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

  const expanded = expandedGroup ? getTopGroup(expandedGroup) : null;
  const subModes = expanded?.modes ?? [];
  const activeTopGroup = highlightedTopGroup(expandedGroup, currentMode);

  const body = (
    <>
      <p className="mb-3 text-[10px] font-mono uppercase tracking-[0.2em] text-text-tertiary">
        Режим показателя
      </p>
      <div className="flex flex-wrap gap-2">
        {LABOR_MARKET_TOP_GROUPS.map((group) => {
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
              onClick={() => onSubClick(expanded.id, item)}
              className={btnCls(item.mode === currentMode)}
            >
              {item.label}
            </button>
          ))}
        </div>
      )}
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
