import GoldPriceViewModePicker from './GoldPriceViewModePicker';

/** Учётная цена золота — ежедневно и сглаживание по периодам. */
export default function GoldPriceIndicatorControls({
  currentMode,
  onChange,
  trackContext,
}) {
  return (
    <GoldPriceViewModePicker
      currentMode={currentMode}
      onChange={onChange}
      trackContext={trackContext}
    />
  );
}
