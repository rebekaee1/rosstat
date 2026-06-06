import UsdRubViewModePicker from './UsdRubViewModePicker';

/** Курс доллара USD/RUB — ежедневный курс и сглаживание по периодам. */
export default function UsdRubIndicatorControls({
  currentMode,
  onChange,
  trackContext,
}) {
  return (
    <UsdRubViewModePicker
      currentMode={currentMode}
      onChange={onChange}
      trackContext={trackContext}
    />
  );
}
