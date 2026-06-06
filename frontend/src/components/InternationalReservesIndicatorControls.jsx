import InternationalReservesViewModePicker from './InternationalReservesViewModePicker';

/** Международные резервы: еженедельно / среднее за период. */
export default function InternationalReservesIndicatorControls({
  currentMode,
  onChange,
  trackContext,
}) {
  return (
    <InternationalReservesViewModePicker
      currentMode={currentMode}
      onChange={onChange}
      trackContext={trackContext}
    />
  );
}
