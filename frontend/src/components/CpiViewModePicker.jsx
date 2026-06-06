import { useCallback, useEffect, useState } from 'react';
import { cn } from '../lib/format';
import { track, events } from '../lib/track';
import {
  CPI_TOP_GROUPS,
  defaultSubModeForGroup,
  expandedGroupForMode,
  getTopGroup,
  highlightedTopGroup,
  topGroupForMode,
} from '../lib/cpiViewModeGroups';

const btnCls = (active) => cn(
  'rounded-xl px-3 py-2 text-xs font-medium transition-colors',
  active
    ? 'bg-champagne/15 text-champagne'
    : 'bg-obsidian-lighter text-text-secondary hover:text-champagne',
);

const btnDisabledCls = 'cursor-not-allowed opacity-45 hover:text-text-secondary';

/**
 * ИПЦ: двухуровневый «Режим инфляции» (вариант A).
 * Верх — семейство; низ — подрежимы с уникальным ?mode= на каждую кнопку.
 */
export default function CpiViewModePicker({
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
      const next = defaultSubModeForGroup(group.id);
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

  const expanded = expandedGroup ? getTopGroup(expandedGroup) : null;
  const subModes = expanded?.modes ?? [];
  const activeTopGroup = highlightedTopGroup(expandedGroup, currentMode);

  const body = (
    <>
      <p className="mb-3 text-[10px] font-mono uppercase tracking-[0.2em] text-text-tertiary">
        Режим инфляции
      </p>
      <div className="flex flex-wrap gap-2">
        {CPI_TOP_GROUPS.map((group) => {
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
        <div
          className={cn(
            'mt-3 gap-2 border-t border-border-subtle pt-3',
            compact
              ? 'flex overflow-x-auto pb-0.5 -mx-1 px-1 scrollbar-thin'
              : 'flex flex-wrap',
          )}
        >
          {!compact && (
            <span className="w-full text-[10px] font-mono uppercase tracking-[0.15em] text-text-tertiary">
              {expanded.label}
            </span>
          )}
          {subModes.map((item) => (
            <button
              key={`${expanded.id}-${item.mode}`}
              type="button"
              disabled={item.disabled}
              title={item.disabled ? item.hint : undefined}
              onClick={() => onSubClick(expanded.id, item)}
              className={cn(
                btnCls(!item.disabled && currentMode === item.mode),
                item.disabled && btnDisabledCls,
                compact && 'shrink-0',
              )}
            >
              {item.label}
              {item.disabled && item.hint ? (
                <span className="ml-1 text-[10px] opacity-70">{item.hint}</span>
              ) : null}
            </button>
          ))}
        </div>
      )}
    </>
  );

  if (compact) {
    return (
      <div className="border-t border-border-subtle pt-4">
        {body}
      </div>
    );
  }

  return (
    <section className="mb-8 rounded-[1.5rem] border border-border-subtle bg-surface p-4 shadow-sm">
      {body}
    </section>
  );
}

export { topGroupForMode, expandedGroupForMode };
