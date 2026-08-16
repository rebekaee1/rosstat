import { useCallback, useEffect, useMemo, useState } from 'react';
import { cn } from '../lib/format';
import { track, events } from '../lib/track';
import { useLocale, useT } from '../i18n';
import { localizeViewModeLabel } from '../i18n/viewModeLabels';
import {
  buildViewModeGroups,
  defaultSubModeForGroup,
  expandedGroupForMode,
  highlightedTopGroup,
} from '../lib/viewModeEngine';

/**
 * Config-driven двухуровневый переключатель режимов.
 *
 * Заменяет ~20 рукописных `*ViewModePicker` — структура групп/подрежимов
 * целиком берётся из canonical-конфига (`viewModeEngine.buildViewModeGroups`).
 * Верхний ряд — семантические группы («На конец периода» / «Средняя» /
 * «К прошлому периоду» / «Год к году»); нижний ряд — гранулярности внутри
 * группы (по кварталам / по годам). Leaf-группа (Г/г) — одиночная кнопка.
 */
const btnCls = (active) => cn(
  'rounded-xl px-3 py-2 text-xs font-medium transition-colors',
  active
    ? 'bg-champagne/15 text-champagne'
    : 'bg-obsidian-lighter text-text-secondary hover:text-champagne',
);

export default function GenericViewModePicker({
  family,
  currentMode,
  onChange,
  trackContext,
  title,
  compact = false,
}) {
  const t = useT();
  const { locale } = useLocale();
  const sectionTitle = title || t('indicator.picker.generic');
  const groups = useMemo(() => {
    const raw = buildViewModeGroups(family);
    return raw.map((g) => ({
      ...g,
      label: localizeViewModeLabel(g.label, locale),
      modes: g.modes?.map((m) => ({
        ...m,
        label: localizeViewModeLabel(m.label, locale),
      })),
    }));
  }, [family, locale]);
  const [expandedGroup, setExpandedGroup] = useState(
    () => expandedGroupForMode(family, currentMode),
  );

  useEffect(() => {
    setExpandedGroup(expandedGroupForMode(family, currentMode));
  }, [family, currentMode]);

  const trackMode = useCallback((mode, groupId) => {
    track(events.CHART_MODE_CHANGE, {
      mode,
      viewGroup: groupId,
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
      const next = defaultSubModeForGroup(family, group.id);
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

  const activeTopGroup = highlightedTopGroup(family, expandedGroup, currentMode);
  const expanded = groups.find((g) => g.id === expandedGroup && !g.leafMode);
  const subModes = expanded?.modes ?? [];

  if (groups.length <= 1 && (groups[0]?.modes?.length ?? 0) <= 1) return null;

  const body = (
    <>
      <p className="mb-3 text-[10px] font-mono uppercase tracking-[0.2em] text-text-tertiary">
        {sectionTitle}
      </p>
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
      {subModes.length > 1 && (
        <div className="mt-3 flex flex-wrap gap-2 border-t border-border-subtle pt-3">
          {subModes.map((item) => (
            <button
              key={item.mode}
              type="button"
              onClick={() => onSubClick(expandedGroup, item)}
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
