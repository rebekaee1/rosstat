import { useCallback, useEffect, useMemo, useState } from 'react';
import { cn } from '../lib/format';
import Chip from './Chip';
import ChipGroup from './ChipGroup';
import { track, events } from '../lib/track';
import { useLocale, useT } from '../i18n';
import { localizeViewModeLabel } from '../i18n/viewModeLabels';
import {
  defaultModeForWorldGroup,
  expandedGroupForWorldMode,
  groupModesFromApi,
} from '../lib/worldViewModes';

function aggregatedModeHint(item, t) {
  if (item.disabled) return t('world.mode.hint.unavailable');
  if (item.official) return undefined;
  const src = item.aggregation?.source_frequency;
  if (src === 'weekly') return t('world.mode.hint.derivedWeekly');
  if (src === 'daily') return t('world.mode.hint.derivedDaily');
  const policy = item.aggregation?.policy;
  if (policy === 'sum') return t('world.mode.hint.sum');
  if (policy === 'last') return t('world.mode.hint.last');
  if (policy === 'mean') return t('world.mode.hint.mean');
  return t('world.mode.hint.derived');
}

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
        hint: aggregatedModeHint(m, t),
      })),
    }));
  }, [modes, locale, t]);
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
      <p className="mb-3 text-[11px] font-mono uppercase tracking-[0.2em] text-text-tertiary">
        {sectionTitle}
      </p>
      {/* Как CpiViewModePicker: wrap, не горизонтальный скролл —
          иначе подпись «Уровень» (w-full) выталкивает частоты за край. */}
      <ChipGroup label={sectionTitle}>
        {groups.map((group) => (
          <Chip
            key={group.id}
            className="fe-chip--wrap shrink-0"
            active={group.id === activeTopGroup}
            onClick={() => onTopClick(group)}
          >
            {group.label}
          </Chip>
        ))}
      </ChipGroup>
      {subModes.length > 0 && (
        <ChipGroup
          label={expanded?.label}
          nowrap={compact}
          className={cn('mt-3 border-t border-border-subtle pt-3', compact && '-mx-1 px-1')}
        >
          {!compact && (
            <span aria-hidden="true" className="mb-0 w-full text-[11px] font-mono uppercase tracking-[0.15em] text-text-tertiary">
              {expanded.label}
            </span>
          )}
          {subModes.map((item) => (
            <Chip
              key={`${expanded.id}-${item.mode}`}
              className="fe-chip--wrap shrink-0"
              active={!item.disabled && item.mode === currentMode}
              disabled={item.disabled}
              title={item.hint || undefined}
              onClick={() => onSubClick(expanded.id, item)}
            >
              {item.label}
              {item.disabled && item.hint ? (
                <span className="ml-1 font-normal">{item.hint}</span>
              ) : (!item.official && !item.disabled ? (
                <span className="ml-1 font-normal">{t('world.mode.badge.derived')}</span>
              ) : null)}
            </Chip>
          ))}
        </ChipGroup>
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
