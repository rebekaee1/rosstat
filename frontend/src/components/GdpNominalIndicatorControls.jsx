import GdpNominalViewModePicker from './GdpNominalViewModePicker';

/** Номинальный ВВП — уровень, темпы, годовой итог. */
export default function GdpNominalIndicatorControls({
  currentMode,
  onChange,
  trackContext,
}) {
  return (
    <GdpNominalViewModePicker
      currentMode={currentMode}
      onChange={onChange}
      trackContext={trackContext}
    />
  );
}
