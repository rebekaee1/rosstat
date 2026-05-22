import { cn } from '../lib/format';
import { track, events } from '../lib/track';

/**
 * Generic in-page view-mode switcher used on indicator pages where a
 * single domain concept can be viewed in several aggregations or
 * transformations (e.g. Level / YoY % / QoQ % / Cumulative index).
 *
 * The component is purely presentational — it doesn't know what each
 * mode means; the parent owns `currentMode` state and decides which
 * series to plot. Replaces the older CPI-specific `CpiViewModePicker`
 * (kept for backward compat where still referenced).
 *
 * Props:
 *   title         — caption above the buttons (e.g. "Режим", "Аггрегация").
 *   modes         — [{ mode: 'level', label: 'Уровень' }, ...]
 *   currentMode   — id of the active mode.
 *   onChange      — (mode) => void.
 *   trackContext  — { code, category } for telemetry; optional.
 */
export default function ViewModePicker({
  title = 'Режим',
  modes,
  currentMode,
  onChange,
  trackContext,
}) {
  return (
    <section className="mb-8 rounded-[1.5rem] border border-border-subtle bg-surface p-4 shadow-sm">
      <p className="mb-3 text-[10px] font-mono uppercase tracking-[0.2em] text-text-tertiary">
        {title}
      </p>
      <div className="flex flex-wrap gap-2">
        {modes.map((item) => (
          <button
            key={item.mode}
            type="button"
            onClick={() => {
              onChange(item.mode);
              track(events.CHART_MODE_CHANGE, {
                mode: item.mode,
                indicator: trackContext?.code,
                indicatorCategory: trackContext?.category,
              });
            }}
            className={cn(
              'rounded-xl px-3 py-2 text-xs font-medium transition-colors',
              currentMode === item.mode
                ? 'bg-champagne/15 text-champagne'
                : 'bg-obsidian-lighter text-text-secondary hover:text-champagne'
            )}
          >
            {item.label}
          </button>
        ))}
      </div>
    </section>
  );
}
