import ChipGroup, { ChipLink } from './ChipGroup';
import { track, events } from '../lib/track';
import { buildFrequencyItems } from '../lib/frequencySwitcher';
import {
  russiaIndicatorPath,
} from '../lib/sitePaths';
import { useT } from '../i18n';

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
function frequencyLabel(t, freq, fallback) {
  if (!freq) return '—';
  const key = `indicator.freq.${freq}`;
  return t(key, fallback);
}

export default function FrequencySwitcher({
  currentCode,
  currentFrequency,
  alternateFrequencies,
  primaryIndicatorCode,
  indicatorCategory,
}) {
  const t = useT();
  const items = buildFrequencyItems({
    currentCode,
    currentFrequency,
    alternateFrequencies,
    primaryIndicatorCode,
  });
  if (items.length < 2) return null;

  return (
    <section className="mb-8 rounded-[1.5rem] border border-border-subtle bg-surface p-4 shadow-sm">
      <p className="mb-3 text-[11px] font-mono uppercase tracking-[0.2em] text-text-tertiary">
        {t('indicator.picker.frequency')}
      </p>
      <ChipGroup label={t('indicator.picker.frequency')}>
        {items.map((item) => {
          const active = item.code === currentCode;
          return (
            <ChipLink
              key={item.frequency}
              active={active}
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
            >
              {frequencyLabel(t, item.frequency, item.label)}
            </ChipLink>
          );
        })}
      </ChipGroup>
    </section>
  );
}
