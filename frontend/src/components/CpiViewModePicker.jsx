import { cn } from '../lib/format';
import { track, events } from '../lib/track';

export default function CpiViewModePicker({
  modes,
  currentMode,
  onChange,
  trackContext,
}) {
  return (
    <section className="mb-8 rounded-[1.5rem] border border-border-subtle bg-surface p-4 shadow-sm">
      <p className="mb-3 text-[10px] font-mono uppercase tracking-[0.2em] text-text-tertiary">
        Режим инфляции
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
