import VariantGroupPicker from './VariantGroupPicker';
import CpiViewModePicker from './CpiViewModePicker';

/**
 * Состав ИПЦ + режим инфляции: на мобиле — одна карточка (меньше скролла),
 * на md+ — два отдельных блока как раньше.
 */
export default function CpiIndicatorControls({
  variantGroup,
  currentCode,
  currentMode,
  onChange,
  trackContext,
}) {
  const modePicker = (
    <CpiViewModePicker
      currentMode={currentMode}
      onChange={onChange}
      trackContext={trackContext}
      code={currentCode}
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
        <CpiViewModePicker
          currentMode={currentMode}
          onChange={onChange}
          trackContext={trackContext}
          code={currentCode}
        />
      </div>
    </>
  );
}
