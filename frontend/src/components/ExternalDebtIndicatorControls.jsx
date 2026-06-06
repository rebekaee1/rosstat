import ExternalDebtViewModePicker from './ExternalDebtViewModePicker';

/** Внешний долг: поквартально / среднее по годам. */
export default function ExternalDebtIndicatorControls({
  currentMode,
  onChange,
  trackContext,
}) {
  return (
    <ExternalDebtViewModePicker
      currentMode={currentMode}
      onChange={onChange}
      trackContext={trackContext}
    />
  );
}
