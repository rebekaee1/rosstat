import UnemploymentViewModePicker from './UnemploymentViewModePicker';

/** Безработица — только режимы (без variant-среза). */
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
