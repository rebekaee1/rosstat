import { useCallback } from 'react';
import ModeGroupsPicker from './ModeGroupsPicker';
import { track, events } from '../lib/track';
import { useT } from '../i18n';
import {
  DEATHS_TOP_GROUPS,
  highlightedTopGroup,
} from '../lib/deathsViewModeGroups';

export default function DeathsViewModePicker({
  currentMode,
  onChange,
  trackContext,
  compact = false,
}) {
  const t = useT();
  const trackMode = useCallback((mode, groupId) => {
    track(events.CHART_MODE_CHANGE, {
      mode,
      deathsViewGroup: groupId,
      indicator: trackContext?.code,
      indicatorCategory: trackContext?.category,
    });
  }, [trackContext?.code, trackContext?.category]);

  const activeTopGroup = highlightedTopGroup(null, currentMode);

  return (
    <ModeGroupsPicker
      title={t('w3.picker.showAs')}
      groups={DEATHS_TOP_GROUPS}
      activeGroupId={activeTopGroup}
      onTopClick={(group) => {
        onChange(group.leafMode);
        trackMode(group.leafMode, group.id);
      }}
      compact={compact}
    />
  );
}
