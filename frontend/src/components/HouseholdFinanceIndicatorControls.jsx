import VariantGroupPicker from './VariantGroupPicker';
import HouseholdFinanceViewModePicker from './HouseholdFinanceViewModePicker';

/** Кредиты и вклады населения (variant) + помесячно / среднее за период. */
export default function HouseholdFinanceIndicatorControls({
  variantGroup,
  currentCode,
  currentMode,
  onChange,
  trackContext,
}) {
  const modePicker = (
    <HouseholdFinanceViewModePicker
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
        <HouseholdFinanceViewModePicker
          currentMode={currentMode}
          onChange={onChange}
          trackContext={trackContext}
        />
      </div>
    </>
  );
}
