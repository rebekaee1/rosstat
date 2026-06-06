import UnemploymentViewModePicker from './UnemploymentViewModePicker';

/** Уровень безработицы — помесячно / квартальное среднее / 12М среднее. */
export default function UnemploymentIndicatorControls({
  currentMode,
  onChange,
  trackContext,
}) {
  return (
    <UnemploymentViewModePicker
      currentMode={currentMode}
      onChange={onChange}
      trackContext={trackContext}
    />
  );
}
