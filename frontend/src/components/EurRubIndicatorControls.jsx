import EurRubViewModePicker from './EurRubViewModePicker';

/** Курс евро EUR/RUB — ежедневный курс и сглаживание по периодам. */
export default function EurRubIndicatorControls({
  currentMode,
  onChange,
  trackContext,
}) {
  return (
    <EurRubViewModePicker
      currentMode={currentMode}
      onChange={onChange}
      trackContext={trackContext}
    />
  );
}
