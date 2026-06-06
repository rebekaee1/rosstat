import RuoniaViewModePicker from './RuoniaViewModePicker';

/** RUONIA — уровень и сглаживание по периодам. */
export default function RuoniaIndicatorControls({
  currentMode,
  onChange,
  trackContext,
}) {
  return (
    <RuoniaViewModePicker
      currentMode={currentMode}
      onChange={onChange}
      trackContext={trackContext}
    />
  );
}
