import { useCallback, useEffect, useMemo, useState } from 'react';
import { cn } from '../lib/format';
import { track, events } from '../lib/track';
import { useLocale, useT } from '../i18n';
import { localizeViewModeLabel } from '../i18n/viewModeLabels';
import {
  defaultModeForWorldGroup,
  expandedGroupForWorldMode,
  groupModesFromApi,
} from '../lib/worldViewModes';

/** Эталон кнопок — CpiViewModePicker / GenericViewModePicker (Россия). */
const btnCls = (active) => cn(
  'max-w-full shrink-0 whitespace-normal rounded-xl px-3 py-2 text-center text-xs font-medium leading-snug transition-colors',
  active
    ? 'bg-champagne/15 text-champagne'
    : 'bg-obsidian-lighter text-text-secondary hover:text-champagne',
);

const btnDisabledCls = 'cursor-not-allowed opacity-45 hover:text-text-secondary';

/**
 * Двухуровневый переключатель мировой карточки.
 * Визуально = российские макрокарточки (не segmented-control «быстрых» страниц).
 */
export default function WorldViewModePicker({
  modes,
  currentMode,
  onChange,
  trackContext,
  title,
  compact = false,
}) {
  const t = useT();
  const { locale } = useLocale();
  const sectionTitle = title || t('indicator.picker.mode');
  const groups = useMemo(() => {
    const raw = groupModesFromApi(modes);
    return raw.map((g) => ({
      ...g,
      label: localizeViewModeLabel(g.label, locale),
      modes: g.modes?.map((m) => ({
        ...m,
        label: localizeViewModeLabel(m.label, locale),
        hint: localizeViewModeLabel(m.hint, locale),
      })),
    }));
  }, [modes, locale]);
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
      <p className="mb-3 text-[10px] font-mono uppercase tracking-[0.2em] text-text-tertiary">
        {sectionTitle}
      </p>
      {/* Как CpiViewModePicker: wrap, не горизонтальный скролл —
          иначе подпись «Уровень» (w-full) выталкивает частоты за край. */}
      <div className="flex flex-wrap gap-2">
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
            'mt-3 gap-2 border-t border-border-subtle pt-3',
            compact
              ? 'flex overflow-x-auto overscroll-x-contain pb-0.5 -mx-1 px-1 scrollbar-hide'
              : 'flex flex-wrap',
          )}
        >
          {!compact && (
            <span className="mb-0 w-full text-[10px] font-mono uppercase tracking-[0.15em] text-text-tertiary">
              {expanded.label}
            </span>
          )}
          {subModes.map((item) => (
            <button
              key={`${expanded.id}-${item.mode}`}
              type="button"
              disabled={item.disabled}
              title={item.disabled ? item.hint : (!item.official ? t('indicator.picker.derivedRecalc') : undefined)}
              onClick={() => onSubClick(expanded.id, item)}
              className={cn(
                btnCls(!item.disabled && item.mode === currentMode),
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
    <section className="mb-6 min-w-0 rounded-[1.25rem] border border-border-subtle bg-surface p-3.5 shadow-sm sm:mb-8 sm:rounded-[1.5rem] sm:p-5">
      {body}
    </section>
  );
}
