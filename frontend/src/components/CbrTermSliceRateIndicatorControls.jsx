import VariantGroupPicker from './VariantGroupPicker';
import CbrTermSliceRateViewModePicker from './CbrTermSliceRateViewModePicker';

/** Срок (variant) + «уровень ставки» — как состав и режим у ИПЦ. */
export default function CbrTermSliceRateIndicatorControls({
  variantGroup,
  currentCode,
  currentMode,
  onChange,
  trackContext,
}) {
  const modePicker = (
    <CbrTermSliceRateViewModePicker
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
        <CbrTermSliceRateViewModePicker
          currentMode={currentMode}
          onChange={onChange}
          trackContext={trackContext}
        />
      </div>
    </>
  );
}
