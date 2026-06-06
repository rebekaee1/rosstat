import WagesNominalViewModePicker from './WagesNominalViewModePicker';

/** Средняя заработная плата — уровень и динамика. */
export default function WagesNominalIndicatorControls({
  currentMode,
  onChange,
  trackContext,
}) {
  return (
    <WagesNominalViewModePicker
      currentMode={currentMode}
      onChange={onChange}
      trackContext={trackContext}
    />
  );
}
