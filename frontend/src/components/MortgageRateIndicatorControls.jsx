import MortgageRateViewModePicker from './MortgageRateViewModePicker';

/** Ипотека — один режим уровня ставки (без variant-среза). */
export default function MortgageRateIndicatorControls({
  currentMode,
  onChange,
  trackContext,
}) {
  return (
    <MortgageRateViewModePicker
      currentMode={currentMode}
      onChange={onChange}
      trackContext={trackContext}
    />
  );
}
