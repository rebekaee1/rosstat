import BtcUsdViewModePicker from './BtcUsdViewModePicker';

/** BTC/USD — дневная цена и сглаживание по периодам. */
export default function BtcUsdIndicatorControls({
  currentMode,
  onChange,
  trackContext,
}) {
  return (
    <BtcUsdViewModePicker
      currentMode={currentMode}
      onChange={onChange}
      trackContext={trackContext}
    />
  );
}
