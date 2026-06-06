import PpiViewModePicker from './PpiViewModePicker';

/** ИЦП — только режимы (без variant-среза). */
export default function PpiIndicatorControls({
  currentMode,
  onChange,
  trackContext,
}) {
  return (
    <PpiViewModePicker
      currentMode={currentMode}
      onChange={onChange}
      trackContext={trackContext}
    />
  );
}
