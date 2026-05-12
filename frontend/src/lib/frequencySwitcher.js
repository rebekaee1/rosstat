/**
 * Pure logic для FrequencySwitcher: маппинг indicator metadata → tab items.
 *
 * Источник правды:
 * - `alternate_frequencies` (от родителя, например quarterly `exports`):
 *   `{"monthly": "exports-monthly"}` — current = primary, alt = secondary.
 * - `primary_indicator_code` (от counterpart, например monthly `exports-monthly`):
 *   "exports" — current = secondary, primary = указанный код.
 *
 * Возвращает array items для render-loop. Если нет данных для switcher
 * (одиночный индикатор без counterpart) — возвращается пустой массив,
 * UI принимает len < 2 → `null` (не рендерит section).
 */

const LABELS = {
  weekly: 'Недельные',
  monthly: 'Месячные',
  quarterly: 'Квартальные',
  yearly: 'Годовые',
  annual: 'Годовые',
};

export function labelForFrequency(freq) {
  if (!freq) return '—';
  return LABELS[freq] || freq;
}

export function buildFrequencyItems({
  currentCode,
  currentFrequency,
  alternateFrequencies,
  primaryIndicatorCode,
}) {
  if (!currentCode) return [];
  const items = [];

  if (alternateFrequencies && Object.keys(alternateFrequencies).length > 0) {
    items.push({
      code: currentCode,
      frequency: currentFrequency,
      label: labelForFrequency(currentFrequency),
      isPrimary: true,
    });
    for (const [freqKey, altCode] of Object.entries(alternateFrequencies)) {
      if (!altCode) continue;
      items.push({
        code: altCode,
        frequency: freqKey,
        label: labelForFrequency(freqKey),
        isPrimary: false,
      });
    }
    return items;
  }

  if (primaryIndicatorCode) {
    items.push({
      code: primaryIndicatorCode,
      frequency: 'quarterly',
      label: labelForFrequency('quarterly'),
      isPrimary: true,
    });
    items.push({
      code: currentCode,
      frequency: currentFrequency,
      label: labelForFrequency(currentFrequency),
      isPrimary: false,
    });
    return items;
  }

  return items;
}
