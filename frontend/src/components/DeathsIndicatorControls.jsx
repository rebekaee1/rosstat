import VariantGroupPicker from './VariantGroupPicker';
import DeathsViewModePicker from './DeathsViewModePicker';

/** Смертемость (variant) + за год / г/г. */
export default function DeathsIndicatorControls({
  variantGroup,
  currentCode,
  currentMode,
  onChange,
  trackContext,
}) {
  const modePicker = (
    <DeathsViewModePicker
      currentMode={currentMode}
      onChange={onChange}
      trackContext={trackContext}
      compact
    />
  );

  if (!variantGroup) {
    return modePicker;
  }

  return (
    <>
      <section className="fe-pick-card fe-pick-card--stack md:hidden">
        <VariantGroupPicker group={variantGroup} currentCode={currentCode} embedded />
        {modePicker}
      </section>
      <div className="hidden md:contents">
        <VariantGroupPicker group={variantGroup} currentCode={currentCode} />
        <DeathsViewModePicker
          currentMode={currentMode}
          onChange={onChange}
          trackContext={trackContext}
        />
      </div>
    </>
  );
}
