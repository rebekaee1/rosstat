import AutoLoanViewModePicker from './AutoLoanViewModePicker';

/** Автокредиты — один режим, та же позиция над графиком, что у ИЦП. */
export default function AutoLoanIndicatorControls({
  currentMode,
  onChange,
  trackContext,
}) {
  return (
    <AutoLoanViewModePicker
      currentMode={currentMode}
      onChange={onChange}
      trackContext={trackContext}
    />
  );
}
