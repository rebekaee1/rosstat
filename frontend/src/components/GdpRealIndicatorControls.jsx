import GdpRealViewModePicker from './GdpRealViewModePicker';

/** Реальный ВВП — уровень, темпы, годовой итог. */
export default function GdpRealIndicatorControls({
  currentMode,
  onChange,
  trackContext,
}) {
  return (
    <GdpRealViewModePicker
      currentMode={currentMode}
      onChange={onChange}
      trackContext={trackContext}
    />
  );
}
