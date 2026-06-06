import KeyRateViewModePicker from './KeyRateViewModePicker';

/** Ключевая ставка — режим уровня и сглаживание (без variant-среза). */
export default function KeyRateIndicatorControls({
  currentMode,
  onChange,
  trackContext,
}) {
  return (
    <KeyRateViewModePicker
      currentMode={currentMode}
      onChange={onChange}
      trackContext={trackContext}
    />
  );
}
