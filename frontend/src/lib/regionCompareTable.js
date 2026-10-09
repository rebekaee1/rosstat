/**
 * Таблица «несколько регионов × главные показатели» (круг 11, F). Чистые функции над уже загруженными срезами карты.
 * Победитель строки отмечается только там, где у показателя есть смысл «лучше/хуже»; у численности отметки нет.
 */

/** Сколько регионов можно сравнивать сразу. */
export const COMPARE_MAX = 5;

/**
 * @param {Array<{ code: string, label: string, betterIsLow?: boolean, neutral?: boolean }>} metrics
 * @param {Array<object|undefined>} heats ответы heatmap в том же порядке, что metrics
 * @param {string[]} slugs выбранные регионы
 * @returns {Array<{ code: string, label: string, unit: string, cells: Array<{ slug: string, value: number|null }>, leader: string|null }>}
 */
export function buildCompareRows(metrics, heats, slugs) {
  return metrics.map((metric, index) => {
    const heat = heats[index];
    const values = new Map((heat?.values || []).map((row) => [row.slug, Number(row.value)]));
    const cells = slugs.map((slug) => {
      const value = values.get(slug);
      return { slug, value: Number.isFinite(value) ? value : null };
    });
    let leader = null;
    if (!metric.neutral) {
      const withValue = cells.filter((cell) => cell.value != null);
      if (withValue.length >= 2) {
        const best = withValue.reduce((acc, cell) => {
          if (metric.betterIsLow) return cell.value < acc.value ? cell : acc;
          return cell.value > acc.value ? cell : acc;
        });
        // Ничья не отмечается: победитель должен быть один.
        if (withValue.filter((cell) => cell.value === best.value).length === 1) leader = best.slug;
      }
    }
    return {
      code: metric.code,
      label: metric.label,
      unit: heat?.indicator?.unit || '',
      year: heat?.year ?? null,
      cells,
      leader,
    };
  });
}

/** Добавить или убрать регион из набора (не больше `max`); порядок добавления сохраняется. */
export function toggleCompareSlug(list, slug, max = 5) {
  if (list.includes(slug)) return list.filter((item) => item !== slug);
  if (list.length >= max) return list;
  return [...list, slug];
}
