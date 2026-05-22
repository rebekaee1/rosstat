import ViewModePicker from './ViewModePicker';

/**
 * Backward-compat alias for the legacy name. New code should import
 * `ViewModePicker` directly with an appropriate `title`. Left in place
 * because `IndicatorDetail` still uses this name for CPI pages where
 * the caption "Режим инфляции" is domain-correct.
 */
export default function CpiViewModePicker(props) {
  return <ViewModePicker title="Режим инфляции" {...props} />;
}
