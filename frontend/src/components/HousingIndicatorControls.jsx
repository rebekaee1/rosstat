import VariantGroupPicker from './VariantGroupPicker';
import HousingViewModePicker from './HousingViewModePicker';

/**
 * Рынок жилья (первичное/вторичное) + режим динамики цен — как CpiIndicatorControls.
 */
export default function HousingIndicatorControls({
  variantGroup,
  currentCode,
  currentMode,
  onChange,
  trackContext,
}) {
  const modePicker = (
    <HousingViewModePicker
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
        <HousingViewModePicker
          currentMode={currentMode}
          onChange={onChange}
          trackContext={trackContext}
        />
      </div>
    </>
  );
}
