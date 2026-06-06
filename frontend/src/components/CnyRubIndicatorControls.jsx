import CnyRubViewModePicker from './CnyRubViewModePicker';

/** Курс юаня CNY/RUB — ежедневный курс и сглаживание по периодам. */
export default function CnyRubIndicatorControls({
  currentMode,
  onChange,
  trackContext,
}) {
  return (
    <CnyRubViewModePicker
      currentMode={currentMode}
      onChange={onChange}
      trackContext={trackContext}
    />
  );
}
