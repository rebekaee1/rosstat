import { Link } from 'react-router-dom';
import { cn } from '../lib/format';
import { track, events } from '../lib/track';
import { buildFrequencyItems } from '../lib/frequencySwitcher';
import {
  russiaIndicatorPath,
} from '../lib/sitePaths';

/**
 * Frequency-switcher между парами индикаторов разной частоты.
 *
 * Источник правды — `IndicatorDetail.alternate_frequencies` (для родителя
 * quarterly: `{monthly: "<code>-monthly"}`) или `primary_indicator_code`
 * (для monthly counterpart). Backend API возвращает оба поля (см. `IndicatorRead`).
 *
 * Архитектура — URL-based: каждая частота имеет собственный URL и SSR canonical,
 * SEO-friendly. Switcher = два router Link, не state. Визуально работает как
 * tabs над графиком (рядом с VariantGroupPicker / CpiViewModePicker).
 */
export default function FrequencySwitcher({
  currentCode,
  currentFrequency,
  alternateFrequencies,
  primaryIndicatorCode,
  indicatorCategory,
}) {
  const items = buildFrequencyItems({
    currentCode,
    currentFrequency,
    alternateFrequencies,
    primaryIndicatorCode,
  });
  if (items.length < 2) return null;

  return (
    <section className="mb-8 rounded-[1.5rem] border border-border-subtle bg-surface p-4 shadow-sm">
      <p className="mb-3 text-[10px] font-mono uppercase tracking-[0.2em] text-text-tertiary">
        Периодичность
      </p>
      <div className="flex flex-wrap gap-2">
        {items.map((item) => {
          const active = item.code === currentCode;
          return (
            <Link
              key={item.frequency}
              to={russiaIndicatorPath(item.code)}
              onClick={() => {
                if (active) return;
                track(events.FREQUENCY_SWITCH, {
                  from: currentCode,
                  to: item.code,
                  fromFrequency: currentFrequency,
                  toFrequency: item.frequency,
                  indicatorCategory,
                });
              }}
              className={cn(
                'rounded-xl px-4 py-2 text-xs font-medium transition-colors',
                active
                  ? 'bg-champagne/15 text-champagne'
                  : 'bg-obsidian-lighter text-text-secondary hover:text-champagne'
              )}
            >
              {item.label}
            </Link>
          );
        })}
      </div>
    </section>
  );
}
