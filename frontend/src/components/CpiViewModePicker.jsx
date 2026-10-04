import { useCallback, useEffect, useMemo, useState } from 'react';
import { cn } from '../lib/format';
import Chip from './Chip';
import ChipGroup from './ChipGroup';
import { track, events } from '../lib/track';
import { useLocale, useT } from '../i18n';
import { localizeViewModeLabel } from '../i18n/viewModeLabels';
import {
  cpiTopGroupsForCode,
  defaultSubModeForGroup,
  expandedGroupForMode,
  getTopGroup,
  highlightedTopGroup,
} from '../lib/cpiViewModeGroups';

/**
 * ИПЦ: двухуровневый «Режим инфляции» (вариант A).
 * Верх — семейство; низ — подрежимы с уникальным ?mode= на каждую кнопку.
 */
export default function CpiViewModePicker({
  currentMode,
  onChange,
  trackContext,
  code = null,
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
      const next = defaultSubModeForGroup(group.id, code);
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

  const topGroups = useMemo(() => (
    cpiTopGroupsForCode(code).map((g) => ({
      ...g,
      label: localizeViewModeLabel(g.label, locale),
      modes: g.modes?.map((m) => ({
        ...m,
        label: localizeViewModeLabel(m.label, locale),
      })),
    }))
  ), [code, locale]);
  const expanded = expandedGroup ? getTopGroup(expandedGroup, code) : null;
  const subModes = useMemo(
    () => (expanded?.modes ?? []).map((m) => ({
      ...m,
      label: localizeViewModeLabel(m.label, locale),
    })),
    [expanded, locale],
  );
  const activeTopGroup = highlightedTopGroup(expandedGroup, currentMode);
  const expandedLabel = localizeViewModeLabel(expanded?.label, locale);

  const body = (
    <>
      <p className="mb-3 text-[11px] font-mono uppercase tracking-[0.2em] text-text-tertiary">
        {t('indicator.picker.inflation')}
      </p>
      <ChipGroup label={t('indicator.picker.inflation')}>
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
        <ChipGroup
          label={expandedLabel}
          nowrap={compact}
          className={cn('mt-3 border-t border-border-subtle pt-3', compact && '-mx-1 px-1')}
        >
          {!compact && (
            <span aria-hidden="true" className="w-full text-[11px] font-mono uppercase tracking-[0.15em] text-text-tertiary">
              {expandedLabel}
            </span>
          )}
          {subModes.map((item) => (
            <Chip
              key={`${expanded.id}-${item.mode}`}
              active={!item.disabled && currentMode === item.mode}
              disabled={item.disabled}
              title={item.disabled ? item.hint : undefined}
              onClick={() => onSubClick(expanded.id, item)}
            >
              {item.label}
              {item.disabled && item.hint ? (
                <span className="ml-1 font-normal">{item.hint}</span>
              ) : null}
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
    <section className="mb-8 rounded-[1.5rem] border border-border-subtle bg-surface p-4 shadow-sm">
      {body}
    </section>
  );
}
