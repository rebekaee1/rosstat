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
      <section className="mb-6 space-y-4 rounded-[1.5rem] border border-border-subtle bg-surface p-4 shadow-sm md:hidden">
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
