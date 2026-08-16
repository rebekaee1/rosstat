// API-слой регионального блока (bounded context «Регионы России»).
// Отдельно от макро-hooks: своя ось (регион × показатель × год).
import { useQuery } from '@tanstack/react-query';
import api from './api';

const STALE = 10 * 60 * 1000;
const GC = 30 * 60 * 1000;

export function useRegionsLanding() {
  return useQuery({
    queryKey: ['regions-landing'],
    queryFn: ({ signal }) => api.get('/regions', { signal }).then(r => r.data),
    staleTime: STALE,
    gcTime: GC,
  });
}

export function useRegionsCatalog(enabled = true) {
  return useQuery({
    queryKey: ['regions-catalog'],
    queryFn: ({ signal }) => api.get('/regions/catalog', { signal }).then(r => r.data),
    staleTime: STALE,
    gcTime: GC,
    enabled,
  });
}

export function useRegionProfile(slug) {
  return useQuery({
    queryKey: ['region-profile', slug],
    queryFn: ({ signal }) => api.get(`/regions/${slug}`, { signal }).then(r => r.data),
    enabled: !!slug,
    staleTime: STALE,
    gcTime: GC,
  });
}

export function useRegionIndicator(slug, code) {
  return useQuery({
    queryKey: ['region-indicator', slug, code],
    queryFn: ({ signal }) =>
      api.get(`/regions/${slug}/i/${code}`, { signal }).then(r => r.data),
    enabled: !!slug && !!code,
    staleTime: STALE,
    gcTime: GC,
  });
}

/** Значения показателя по всем регионам за последний год — для карты. */
export function useRegionsHeatmap(code, enabled = true) {
  return useQuery({
    queryKey: ['regions-heatmap', code],
    queryFn: ({ signal }) =>
      api.get(`/regions/heatmap/${code}`, { signal }).then(r => r.data),
    enabled: !!code && enabled,
    staleTime: STALE,
    gcTime: GC,
  });
}

/** Значения показателя по всем регионам за ВСЕ годы — для карты-таймлайна. */
export function useRegionsHeatmapSeries(code, enabled = true) {
  return useQuery({
    queryKey: ['regions-heatmap-series', code],
    queryFn: ({ signal }) =>
      api.get(`/regions/heatmap-series/${code}`, { signal }).then(r => r.data),
    enabled: !!code && enabled,
    staleTime: STALE,
    gcTime: GC,
  });
}

/** Форматирование чисел региональных рядов: большие — с разрядами, малые — с дробью. */
export function formatRegionValue(value) {
  if (value == null || Number.isNaN(value)) return '—';
  const abs = Math.abs(value);
  let digits;
  if (abs >= 10000) digits = 0;
  else if (abs >= 100) digits = 1;
  else digits = abs < 1 ? 2 : 1;
  const formatted = value.toLocaleString('ru-RU', {
    minimumFractionDigits: 0,
    maximumFractionDigits: digits,
  });
  return formatted;
}

/**
 * Компактный тик оси Y: большие числа сокращаются («1,2 млн», «120 тыс»),
 * остальные — с разрядными пробелами. Сокращается ЧИСЛО (не единица ряда):
 * ось всегда в единицах индикатора. Пробелы неразрывные — иначе SVG-текст
 * recharts переносит «тыс» на вторую строку и подпись обрезается.
 */
export function formatCompactTick(value, { narrow = false } = {}) {
  if (value == null || !Number.isFinite(Number(value))) return '';
  const num = Number(value);
  const abs = Math.abs(num);
  const short = (v, suffix) => {
    const s = v.toLocaleString('ru-RU', { minimumFractionDigits: 0, maximumFractionDigits: 1 });
    return `${s}\u00A0${suffix}`;
  };
  if (abs >= 1e9) return short(num / 1e9, narrow ? 'млрд' : 'млрд');
  if (abs >= 1e6) return short(num / 1e6, 'млн');
  if (abs >= 1e5) return short(num / 1e3, narrow ? 'т' : 'тыс');
  return num
    .toLocaleString('ru-RU', { maximumFractionDigits: abs < 10 ? 1 : 0 })
    .replace(/\s/g, '\u00A0');
}

/**
 * Ширина оси Y под самые длинные подписи ряда — чтобы «148,5 тыс» не
 * обрезалось узкой осью (фикс 2026-07-05, скрин руководителя).
 * narrow=true — бюджет под короткие суффиксы («т» вместо «тыс») на мобилке.
 */
export function compactTickAxisWidth(values, { narrow = false } = {}) {
  const nums = (values || []).filter((v) => v != null && Number.isFinite(Number(v)));
  if (!nums.length) return narrow ? 40 : 52;
  const longest = Math.max(
    formatCompactTick(Math.max(...nums), { narrow }).length,
    formatCompactTick(Math.min(...nums), { narrow }).length,
  );
  const minW = narrow ? 34 : 40;
  const maxW = narrow ? 44 : 80;
  return Math.max(minW, Math.min(maxW, Math.round(longest * (narrow ? 6.2 : 6.8)) + (narrow ? 8 : 12)));
}

/** Русское склонение: pluralRu(471, ['показатель','показателя','показателей']). */
export function pluralRu(n, [one, few, many]) {
  const abs = Math.abs(n) % 100;
  const d = abs % 10;
  if (abs > 10 && abs < 20) return many;
  if (d === 1) return one;
  if (d >= 2 && d <= 4) return few;
  return many;
}

/** Короткая единица для компактных подписей. */
export function shortUnit(unit = '') {
  const u = unit.trim().toLowerCase();
  const map = [
    [/^миллионов рублей/, 'млн ₽'],
    [/^миллиардов рублей/, 'млрд ₽'],
    [/^тысяч рублей/, 'тыс ₽'],
    [/^рублей/, '₽'],
    [/^тысяч человек/, 'тыс чел.'],
    [/^миллионов человек/, 'млн чел.'],
    [/^человек/, 'чел.'],
    [/^% к предыдущему году/, '% г/г'],
    [/^в процентах к предыдущему году/, '% г/г'],
    [/^в процентах/, '%'],
    [/^процентов/, '%'],
    [/^%$/, '%'],
    [/^тысяч гектаров/, 'тыс га'],
    [/^тысяч тонн/, 'тыс т'],
    [/^миллионов тонн/, 'млн т'],
    [/^миллиардов киловатт-часов/, 'млрд кВт·ч'],
    [/^тысяч м2/, 'тыс м²'],
    [/^тысяч квадратных метров/, 'тыс м²'],
    [/^м2/, 'м²'],
    [/^центнеров с одного гектара/, 'ц/га'],
    [/^километров/, 'км'],
    [/^штук/, 'шт.'],
  ];
  for (const [re, short] of map) {
    if (re.test(u)) return short;
  }
  return unit.length > 26 ? '' : unit;
}

/** Дельта к прошлому году: направление и текст.
 *
 * В-20 (CTO-аудит 2026-07-06): при отрицательной базе или переходе через ноль
 * процент нечитаем (сальдо −5 → +5 это не «+200%») — бейдж не показываем.
 */
export function yearDelta(value, prevValue) {
  if (value == null || prevValue == null || prevValue === 0) return null;
  if (prevValue < 0 || value < 0) return null;
  const pct = ((value - prevValue) / Math.abs(prevValue)) * 100;
  if (!Number.isFinite(pct)) return null;
  return { pct, up: pct > 0.005, down: pct < -0.005 };
}

// Публичные SPA-пути регионального блока (ADR-0013). API выше — /api/v1/regions*.
export {
  regionHubPath,
  regionPath,
  regionIndicatorPath,
  regionMapPath,
  regionRatingPath,
  regionVsPath,
} from './sitePaths';

