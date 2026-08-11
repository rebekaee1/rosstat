import { useCallback, useEffect, useMemo, useState } from 'react';
import { cn } from '../lib/format';
import { track, events } from '../lib/track';
import {
  defaultModeForWorldGroup,
  expandedGroupForWorldMode,
  groupModesFromApi,
} from '../lib/worldViewModes';

const btnCls = (active) => cn(
  'rounded-lg px-3.5 py-2 text-xs font-medium transition-all',
  active
    ? 'bg-white text-text-primary shadow-sm ring-1 ring-black/[0.04]'
    : 'text-text-secondary hover:bg-white/70 hover:text-text-primary',
);

const btnDisabledCls = 'cursor-not-allowed opacity-45 hover:text-text-secondary';

/**
 * Двухуровневый переключатель мировой карточки (эталон — CpiViewModePicker).
 * Верх — тип представления; низ — частота. Недоступные ячейки видны, но disabled
 * (как у ИПЦ): пользователь видит матрицу полноты, а не «пропавшую» кнопку.
 */
export default function WorldViewModePicker({
  modes,
  currentMode,
  onChange,
  trackContext,
  title = 'Режим показателя',
  compact = false,
}) {
  const groups = useMemo(() => groupModesFromApi(modes), [modes]);
  const [expandedGroup, setExpandedGroup] = useState(
    () => expandedGroupForWorldMode(groups, currentMode),
  );

  useEffect(() => {
    setExpandedGroup(expandedGroupForWorldMode(groups, currentMode));
  }, [groups, currentMode]);

  const trackMode = useCallback((mode, groupId) => {
    track(events.CHART_MODE_CHANGE, {
      mode,
      viewGroup: groupId,
      indicator: trackContext?.code,
      indicatorCategory: trackContext?.category,
      world: true,
    });
  }, [trackContext?.code, trackContext?.category]);

  const onTopClick = (group) => {
    if (group.leafMode) {
      setExpandedGroup(group.id);
      onChange(group.leafMode);
      trackMode(group.leafMode, group.id);
      return;
    }
    setExpandedGroup(group.id);
    const currentInGroup = group.modes?.some(
      (m) => !m.disabled && m.mode === currentMode,
    );
    if (!currentInGroup) {
      const next = defaultModeForWorldGroup(groups, group.id);
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

  if (groups.length === 0) return null;
  if (groups.length <= 1 && (groups[0]?.modes?.length ?? 0) <= 1) return null;

  const expanded = groups.find((g) => g.id === expandedGroup && !g.leafMode);
  const subModes = expanded?.modes ?? [];
  const activeTopGroup = expandedGroupForWorldMode(groups, currentMode);

  const body = (
    <>
      <p className="mb-3 text-[10px] font-mono uppercase tracking-[0.2em] text-champagne">
        {title}
      </p>
      <div className="inline-flex max-w-full flex-wrap gap-1 rounded-xl bg-obsidian-light p-1">
        {groups.map((group) => (
          <button
            key={group.id}
            type="button"
            onClick={() => onTopClick(group)}
            className={btnCls(group.id === activeTopGroup)}
          >
            {group.label}
          </button>
        ))}
      </div>
      {subModes.length > 0 && (
        <div
          className={cn(
            'mt-4 gap-1 rounded-xl bg-obsidian-light p-1',
            compact
              ? 'flex overflow-x-auto pb-0.5 -mx-1 px-1 scrollbar-thin'
              : 'flex flex-wrap',
          )}
        >
          {subModes.map((item) => (
            <button
              key={`${expanded.id}-${item.mode}`}
              type="button"
              disabled={item.disabled}
              title={item.disabled ? item.hint : (!item.official ? 'Пересчёт от другого ряда' : undefined)}
              onClick={() => onSubClick(expanded.id, item)}
              className={cn(
                btnCls(!item.disabled && item.mode === currentMode),
                item.disabled && btnDisabledCls,
                compact && 'shrink-0',
              )}
            >
              {item.label}
              {item.disabled && item.hint ? (
                <span className="ml-1.5 inline-block h-1.5 w-1.5 rounded-full bg-text-tertiary/50 align-middle" aria-label={item.hint} />
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
    <section className="mb-8 rounded-[1.5rem] border border-border-subtle bg-surface p-4 shadow-[0_12px_35px_rgba(35,30,16,0.04)] sm:p-5">
      {body}
    </section>
  );
}
