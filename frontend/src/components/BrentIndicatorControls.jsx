import BrentViewModePicker from './BrentViewModePicker';

/** Нефть Brent — ежедневная цена и сглаживание по периодам. */
export default function BrentIndicatorControls({
  currentMode,
  onChange,
  trackContext,
}) {
  return (
    <BrentViewModePicker
      currentMode={currentMode}
      onChange={onChange}
      trackContext={trackContext}
    />
  );
}
