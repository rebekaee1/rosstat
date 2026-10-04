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
import '../styles/world.css';

/** Названия групп режимов для человека: «Значения», «Изменение за год», а не «Уровень» и «К году». */
const HUMAN_GROUP_KEY = {
  'Уровень': 'w2.mode.level',
  'К прошлому периоду': 'w2.mode.step',
  'К году': 'w2.mode.yoy',
  'Индекс': 'w2.mode.index',
};

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
 * Выбор вида показателя: «Показать как» (значения, изменение, индекс) и «Как часто» (по годам, кварталам, месяцам).
 * Недоступные варианты («нет официального ряда») не показываются: они только занимали место.
 * Один вариант выбора — нет и выбора: блок скрывается.
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
  const sectionTitle = title || t('w2.mode.title');
  const groups = useMemo(() => {
    const raw = groupModesFromApi(modes);
    return raw.map((g) => ({
      ...g,
      label: HUMAN_GROUP_KEY[g.id] ? t(HUMAN_GROUP_KEY[g.id]) : localizeViewModeLabel(g.label, locale),
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
  const availableCount = (group) => (group.modes || []).filter((item) => !item.disabled).length;
  if (groups.length <= 1 && availableCount(groups[0]) <= 1) return null;

  const expanded = groups.find((g) => g.id === expandedGroup && !g.leafMode);
  const subModes = (expanded?.modes ?? []).filter((item) => !item.disabled);
  const activeTopGroup = expandedGroupForWorldMode(groups, currentMode);

  const body = (
    <>
      {groups.length > 1 && (
        <>
          <p className="w2-label">{sectionTitle}</p>
          <ChipGroup label={sectionTitle} className="fe-chip-row--mscroll">
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
        </>
      )}
      {subModes.length > 1 && (
        <div className={cn(groups.length > 1 && 'mt-3 border-t border-border-subtle pt-3')}>
          <p className="w2-label">{t('w2.mode.period')}</p>
          <ChipGroup
            label={t('w2.mode.period')}
            nowrap={compact}
            className={cn('fe-chip-row--mscroll', compact && '-mx-1 px-1')}
          >
            {subModes.map((item) => (
              <Chip
                key={`${expanded.id}-${item.mode}`}
                className="fe-chip--wrap shrink-0"
                active={item.mode === currentMode}
                title={item.hint || undefined}
                onClick={() => onSubClick(expanded.id, item)}
              >
                {item.label}
                {!item.official ? (
                  <span className="ml-1 font-normal">{t('world.mode.badge.derived')}</span>
                ) : null}
              </Chip>
            ))}
          </ChipGroup>
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
    <section className="mb-6 min-w-0 rounded-3xl border border-border-subtle bg-surface p-4 shadow-sm sm:mb-8 sm:p-5">
      {body}
    </section>
  );
}
