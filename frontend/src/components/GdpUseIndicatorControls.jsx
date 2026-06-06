import VariantGroupPicker from './VariantGroupPicker';
import GdpUseViewModePicker from './GdpUseViewModePicker';

/** Компоненты ВВП по использованию (variant) + поквартально / среднее по годам. */
export default function GdpUseIndicatorControls({
  variantGroup,
  currentCode,
  currentMode,
  onChange,
  trackContext,
}) {
  const modePicker = (
    <GdpUseViewModePicker
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
        <GdpUseViewModePicker
          currentMode={currentMode}
          onChange={onChange}
          trackContext={trackContext}
        />
      </div>
    </>
  );
}
