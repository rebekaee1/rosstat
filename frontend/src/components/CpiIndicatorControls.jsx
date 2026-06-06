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
        <CpiViewModePicker
          currentMode={currentMode}
          onChange={onChange}
          trackContext={trackContext}
        />
      </div>
    </>
  );
}
